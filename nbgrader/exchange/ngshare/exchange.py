#!/usr/bin/python
import os
import datetime
import sys
import shutil
import glob
import requests

from textwrap import dedent

from traitlets import Unicode, Bool, default
from jupyter_core.paths import jupyter_data_dir

from nbgrader.exchange.abc import Exchange as ABCExchange
from nbgrader.exchange import ExchangeError
from nbgrader.utils import check_directory, ignore_patterns, self_owned
import base64
import json

class Exchange(ABCExchange):

    username = os.environ['JUPYTERHUB_USER']

    @property
    def ngshare_url(self):
        if 'PROXY_PUBLIC_SERVICE_HOST' in os.environ:
            # we are in a kubernetes environment, so dns based service discovery should work
            # assuming the service is called ngshare, which it should
            return "http://proxy-public/services/ngshare"
        else:
            # TODO: maybe expose this in the nbgrader configs?
            # for now, keeping the original url to not break docker testing setup
            return 'http://172.17.0.3:11111'  # need to get IP address of container

    prefix = '/api'

    def _ngshare_api_check_error(self, response, url):
        if response.status_code != requests.codes.ok:
            self.log.error("ngshare service returned invalid status code %d, this should never happen.",response.status_code)
        response = response.json()
        if not response['success']:
            if 'message' not in response:
                self.log.error("ngshare endpoint %s returned failure without an error message.", url)
            else:
                self.log.error("ngshare endpoint %s returned failure: %s", url, response['message'])
            return None
        return response

    def ngshare_api_get(self, url, params=None):
        try:
            response = requests.get(self.ngshare_url + url, params=params,
                headers={'Authorization': 'token ' + os.environ['JUPYTERHUB_API_TOKEN']})
        except Exception as e:
            self.log.exception("An error occured when querying the ngshare endpoint %s", url)
            return None
        return self._ngshare_api_check_error(response, url)

    def ngshare_api_post(self, url, data, params=None):
        try:
            response = requests.post(self.ngshare_url + url, data=data, params=params,
                headers={'Authorization': 'token ' + os.environ['JUPYTERHUB_API_TOKEN']})
        except Exception as e:
            self.log.exception("An error occured when sending a POST request to the ngshare endpoint %s", url)
            return None
        return self._ngshare_api_check_error(response, url)

    def ngshare_api_delete(self, url, params=None):
        try:
            response = requests.delete(self.ngshare_url + url, params=params,
                headers={'Authorization': 'token ' + os.environ['JUPYTERHUB_API_TOKEN']})
        except Exception as e:
            self.log.exception("An error occured when sending a DELETE request to the ngshare endpoint %s", url)
            return None
        return self._ngshare_api_check_error(response, url)

    assignment_dir = Unicode('.',
                             help=dedent("""
            Local path for storing student assignments.  Defaults to '.'
            which is normally Jupyter's notebook_dir.
            """)).tag(config=True)

    root = Unicode('/srv/nbgrader/exchange',
                   help='The nbgrader exchange directory writable to everyone. MUST be preexisting.'
                   ).tag(config=True)

    cache = Unicode('',
                    help='Local cache directory for nbgrader submit and nbgrader list. Defaults to $JUPYTER_DATA_DIR/nbgrader_cache'
                    ).tag(config=True)

    @default('cache')
    def _cache_default(self):
        return os.path.join(jupyter_data_dir(), 'nbgrader_cache')

    path_includes_course = Bool(False,
                                help=dedent("""
            Whether the path for fetching/submitting  assignments should be
            prefixed with the course name. If this is `False`, then the path
            will be something like `./ps1`. If this is `True`, then the path
            will be something like `./course123/ps1`.
            """)).tag(config=True)

    def set_perms(self, dest, fileperms, dirperms):
        all_dirs = []
        for (dirname, _, filenames) in os.walk(dest):
            for filename in filenames:
                os.chmod(os.path.join(dirname, filename), fileperms)
            all_dirs.append(dirname)

        for dirname in all_dirs[::-1]:
            os.chmod(dirname, dirperms)

    def decode_dir(self, src_dir, dest_dir, ignore=None):
        '''
       decode an encoded directory tree and saw the decoded files to des
       src_dir: en encoded directory tree
       dest: destination directory path for decoded files
       ignore: a function that returns true if the file should be ignored,
       false otherwise. This function takes as arguments the file directory path,
       file name, and file size in KB.
       '''
        #check if the destination directory exists
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)

        for src_file in src_dir:
            src_path = src_file['path']
            path_components = os.path.split(src_path)
            dir_name = path_components[0]
            file_name = path_components[1]

            if ignore:
                if ignore(dir_name, file_name, file_size):
                    continue

            dest_path = os.path.join(dest_dir, file_name)
            # the file could be in a subdirectory, check if directory exists
            if not os.path.exists(dir_name) and dir_name != '':
                subdir = os.path.join(dest_dir, dir_name)
                if not os.path.exists(subdir):
                    os.mkdir(subdir)
                dest_path = os.path.join(subdir, file_name)

            self.log.info('Decoding: {}'.format(dest_path))
            decoded_content = base64.b64decode(src_file['content'])
            file_size = len(decoded_content)
     
            with open(dest_path, 'wb') as d:
                d.write(decoded_content)

    def encode_dir(self, src_dir, ignore=None):
        encoded_files = []
        for (subdir, dirs, files) in os.walk(src_dir):
            for file_name in files:
                file_path = subdir + os.sep + file_name
                data_bytes = open(file_path, 'rb').read()
                if ignore:
                    if ignore(subdir, file_name, len(data_bytes)):
                        continue
                
                # check if you have a subdir
                sub_dir = subdir.split(os.sep)[-1]
                if sub_dir != self.coursedir.assignment_id:
                    file_path = sub_dir + os.sep + file_name
                else:
                    file_path = file_name

                self.log.info('Encoding: {}'.format(file_path))
                encoded = base64.b64encode(data_bytes)
                content = str(encoded, 'utf-8')
                file_map = {'path': file_path, 'content': content}
                encoded_files.append(file_map)

        dir_tree = {'user': self.username, 'files': json.dumps(encoded_files)}
        return dir_tree

    def init_src(self):
        """Compute and check the source paths for the transfer."""

        raise NotImplementedError

    def init_dest(self):
        """Compute and check the destination paths for the transfer."""

        raise NotImplementedError

    def copy_files(self):
        """Actually do the file transfer."""

        raise NotImplementedError

    def start(self):
        super(Exchange, self).start()

    def _assignment_not_found(self, src_path, other_path):
        msg = 'Assignment not found at: {}'.format(src_path)
        self.log.fatal(msg)
        found = glob.glob(other_path)
        if found:

            # Normally it is a bad idea to put imports in the middle of
            # a function, but we do this here because otherwise fuzzywuzzy
            # prints an annoying message about python-Levenshtein every
            # time nbgrader is run.

            from fuzzywuzzy import fuzz
            scores = sorted([(fuzz.ratio(self.src_path, x), x) for x in
                            found])
            self.log.error('Did you mean: %s', scores[-1][1])

        raise ExchangeError(msg)

    def ensure_directory(self, path, mode):
        """Ensure that the path exists, has the right mode and is self owned."""

        if not os.path.isdir(path):
            os.makedirs(path)

            # For some reason, Python won't create a directory with a mode of 0o733
            # so we have to create and then chmod.

            os.chmod(path, mode)
        else:
            if not self.coursedir.groupshared and not self_owned(path):
                self.fail("You don't own the directory: {}".format(path))

    def do_copy(self, src, dest, log=None):
        """
        Copy the src dir to the dest dir, omitting excluded
        file/directories, non included files, and too large files, as
        specified by the options coursedir.ignore, coursedir.include
        and coursedir.max_file_size.
        """
        shutil.copytree(src, dest,
                        ignore=ignore_patterns(exclude=self.coursedir.ignore,
                                               include=self.coursedir.include,
                                               max_file_size=self.coursedir.max_file_size,
                                               log=self.log))
        # copytree copies access mode too - so we must add go+rw back to it if
        # we are in groupshared.
        if self.coursedir.groupshared:
            for dirname, _, filenames in os.walk(dest):
                # dirs become ug+rwx
                st_mode = os.stat(dirname).st_mode
                if st_mode & 0o2770 != 0o2770:
                    try:
                        os.chmod(dirname, (st_mode|0o2770) & 0o2777)
                    except PermissionError:
                        self.log.warning("Could not update permissions of %s to make it groupshared", dirname)

                for filename in filenames:
                    filename = os.path.join(dirname, filename)
                    st_mode = os.stat(filename).st_mode
                    if st_mode & 0o660 != 0o660:
                        try:
                            os.chmod(filename, (st_mode|0o660) & 0o777)
                        except PermissionError:
                            self.log.warning("Could not update permissions of %s to make it groupshared", filename)
