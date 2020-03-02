import base64
import os
from stat import (
    S_IRUSR, S_IWUSR, S_IXUSR,
    S_IRGRP, S_IWGRP, S_IXGRP,
    S_IROTH, S_IWOTH, S_IXOTH
)
import json

import requests
from textwrap import dedent
from traitlets import Bool

from nbgrader.exchange.abc import ExchangeSubmit as ABCExchangeSubmit
from .exchange import Exchange
from nbgrader.utils import find_all_notebooks


class ExchangeSubmit(Exchange, ABCExchangeSubmit):

    def _get_assignment_notebooks(self, course_id, assignment_id):
        """
        Returns a list of relative paths for all files in the assignment.
        """
        url = self.ngshare_url + '/api/assignment/{}/{}'.format(course_id,
            assignment_id)
        params = {'user': self.username, 'list_only': 'true'}

        response = requests.get(url, params=params)

        self.check_response(response)

        return [x['path'] for x in response.json()['files']]

    # TODO: Change to a general solution for all exchange classes.
    def check_response(self, response):
        """
        Raises exceptions if the server response is not good.
        """
        if response.status_code != requests.codes.ok:
            raise RuntimeError('HTTP status code {}'.format(response.status_code))
        elif not response.json()['success']:
            raise RuntimeError(response.json()['message'])


    def init_src(self):
        if self.path_includes_course:
            root = os.path.join(self.coursedir.course_id, self.coursedir.assignment_id)
            other_path = os.path.join(self.coursedir.course_id, "*")
        else:
            root = self.coursedir.assignment_id
            other_path = "*"
        self.src_path = os.path.abspath(os.path.join(self.assignment_dir, root))
        self.coursedir.assignment_id = os.path.split(self.src_path)[-1]
        if not os.path.isdir(self.src_path):
            self._assignment_not_found(self.src_path, os.path.abspath(other_path))

    def init_dest(self):
        if self.coursedir.course_id == '':
            self.fail("No course id specified. Re-run with --course flag.")

        self.cache_path = os.path.join(self.cache, self.coursedir.course_id)
        if self.coursedir.student_id != '*':
            self.fail('Submitting assignments with an explicit student ID is not possible with ngshare.')
        else:
            self.ngshare_url = 'http://172.17.0.1:11111' # TODO
            student_id = os.environ['USER'] # TODO: Get from JupyterHub.
            self.username = student_id
        if self.add_random_string:
            random_str = base64.urlsafe_b64encode(os.urandom(9)).decode('ascii')
            self.assignment_filename = '{}+{}+{}+{}'.format(
                student_id, self.coursedir.assignment_id, self.timestamp, random_str)
        else:
            self.assignment_filename = '{}+{}+{}'.format(
                student_id, self.coursedir.assignment_id, self.timestamp)

    def check_filename_diff(self):
        try:
            released_notebooks = self._get_assignment_notebooks(
                self.coursedir.course_id, self.coursedir.assignment_id)
        except Exception as e:
            self.log.warning('Unable to get list of assignment files. Reason: "{}"'
                .format(e))
            released_notebooks = []
        submitted_notebooks = find_all_notebooks(self.src_path)

        # Look for missing notebooks in submitted notebooks
        missing = False
        release_diff = list()
        for filename in released_notebooks:
            if filename in submitted_notebooks:
                release_diff.append("{}: {}".format(filename, 'FOUND'))
            else:
                missing = True
                release_diff.append("{}: {}".format(filename, 'MISSING'))

        # Look for extra notebooks in submitted notebooks
        extra = False
        submitted_diff = list()
        for filename in submitted_notebooks:
            if filename in released_notebooks:
                submitted_diff.append("{}: {}".format(filename, 'OK'))
            else:
                extra = True
                submitted_diff.append("{}: {}".format(filename, 'EXTRA'))

        if missing or extra:
            diff_msg = (
                "Expected:\n\t{}\nSubmitted:\n\t{}".format(
                    '\n\t'.join(release_diff),
                    '\n\t'.join(submitted_diff),
                )
            )
            if missing and self.strict:
                self.fail(
                    "Assignment {} not submitted. "
                    "There are missing notebooks for the submission:\n{}"
                    "".format(self.coursedir.assignment_id, diff_msg)
                )
            else:
                self.log.warning(
                    "Possible missing notebooks and/or extra notebooks "
                    "submitted for assignment {}:\n{}"
                    "".format(self.coursedir.assignment_id, diff_msg)
                )

    def encode_dir(self, path): # TODO: Remove.
        return []

    def post_submission(self, src_path):
        encoded_dir = self.encode_dir(src_path)
        timestamp_content = base64.encodebytes(self.timestamp.encode()).decode()
        encoded_dir.append({'path': 'timestamp.txt', 'content': timestamp_content})

        url = self.ngshare_url + '/api/submission/{}/{}'.format(
            self.coursedir.course_id, self.coursedir.assignment_id)
        data = {'user': self.username, 'files': json.dumps(encoded_dir)}

        response = requests.post(url, data=data)
        self.check_response(response)

    def copy_files(self):
        if self.add_random_string:
            cache_path = os.path.join(self.cache_path, self.assignment_filename.rsplit('+', 1)[0])
        else:
            cache_path = os.path.join(self.cache_path, self.assignment_filename)

        self.log.info("Source: {}".format(self.src_path))

        # copy to the real location
        self.check_filename_diff()
        try:
            self.post_submission(self.src_path)
        except Exception as e:
            self.log.error('Failed to submit. Reason: "{}"'.format(e))
            return

        # also copy to the cache
        if not os.path.isdir(self.cache_path):
            os.makedirs(self.cache_path)
        self.do_copy(self.src_path, cache_path)
        with open(os.path.join(cache_path, "timestamp.txt"), "w") as fh:
            fh.write(self.timestamp)

        self.log.info("Submitted as: {} {} {}".format(
            self.coursedir.course_id, self.coursedir.assignment_id, str(self.timestamp)
        ))
