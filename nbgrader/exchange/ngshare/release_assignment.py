import os
import shutil
from stat import (
    S_IRUSR, S_IWUSR, S_IXUSR,
    S_IRGRP, S_IWGRP, S_IXGRP,
    S_IROTH, S_IWOTH, S_IXOTH,
    S_ISGID, ST_MODE
)

from traitlets import Bool

from nbgrader.exchange.abc import ExchangeReleaseAssignment as ABCExchangeReleaseAssignment
from nbgrader.exchange.ngshare import Exchange

import requests
import base64
import json


class ExchangeReleaseAssignment(Exchange, ABCExchangeReleaseAssignment):

    force = Bool(False, help="Force overwrite existing files in the exchange.").tag(config=True)

    def _load_config(self, cfg, **kwargs):
        if 'ExchangeRelease' in cfg:
            self.log.warning(
                "Use ExchangeReleaseAssignment in config, not ExchangeRelease. Outdated config:\n%s",
                '\n'.join(
                    'ExchangeRelease.{key} = {value!r}'.format(key=key, value=value)
                    for key, value in cfg.ExchangeRelease.items()
                )
            )
            cfg.ExchangeReleaseAssignment.merge(cfg.ExchangeRelease)
            del cfg.ExchangeRelease

        super(ExchangeReleaseAssignment, self)._load_config(cfg, **kwargs)

    def ensure_root(self):
        pass

    def _encode_assignment(self):
        assignment = []

        for subdir, dirs, files in os.walk(self.src_path):
            for filename in files:
                filepath = subdir + os.sep + filename
                data_read =  open(filepath, "r").read()
                data_bytes = data_read.encode("utf-8")
                encoded = base64.b64encode(data_bytes)
                content = 'amtsCg==' + str(encoded)
                file_map = {"path": filepath, "content": content}

                assignment.append(file_map)
        return assignment


    def _post_assignment(self):
        if self.coursedir.course_id == '':
            self.fail("No course id specified. Re-run with --course flag.")
        url = self.ngshare_url + '/api/assignment/{}/{}'.format(self.coursedir.course_id, self.coursedir.assignment_id)

        data = {'files': json.dumps(self.assignment)}
        r = requests.post(url = url, data = data)
        self.log.info(r.content)


    def init_src(self):
        self.ngshare_url = 'http://172.17.0.3:11111/' #need to get IP address of container
        self.src_path = self.coursedir.format_path(self.coursedir.release_directory, '.', self.coursedir.assignment_id)

        if not os.path.isdir(self.src_path):
            source = self.coursedir.format_path(self.coursedir.source_directory, '.', self.coursedir.assignment_id)
            if os.path.isdir(source):
                # Looks like the instructor forgot to assign
                self.fail("Assignment found in '{}' but not '{}', run `nbgrader generate_assignment` first.".format(
                    source, self.src_path))
            else:
                self._assignment_not_found(
                    self.src_path,
                    self.coursedir.format_path(self.coursedir.release_directory, '.', '*'))

        self.assignment = self._encode_assignment()
        self._post_assignment()

    def init_dest(self):
        pass


    def copy_files(self):
        pass

