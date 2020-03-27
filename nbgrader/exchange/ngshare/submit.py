import base64
import os
import json

from nbgrader.exchange.abc import ExchangeSubmit as ABCExchangeSubmit
from .exchange import Exchange
from nbgrader.utils import find_all_notebooks, parse_utc


class ExchangeSubmit(Exchange, ABCExchangeSubmit):

    def _get_assignment_notebooks(self, course_id, assignment_id):
        """
        Returns a list of relative paths for all files in the assignment.
        """
        url = '/assignment/{}/{}'.format(course_id, assignment_id)
        params = {'list_only': 'true'}

        response = self.ngshare_api_get(url, params)
        if response is None:
            return None

        return [x['path'] for x in response['files'] if
                os.path.splitext(x['path'])[1] == '.ipynb']

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
            self.fail('Submitting assignments with an explicit student ID is '
                      'not possible with ngshare.')
        else:
            student_id = self.username
        if self.add_random_string:
            random_str = base64.urlsafe_b64encode(os.urandom(9)).decode('ascii')
            self.assignment_filename = '{}+{}+{}+{}'.format(
                student_id, self.coursedir.assignment_id, self.timestamp, random_str)
        else:
            self.assignment_filename = '{}+{}+{}'.format(
                student_id, self.coursedir.assignment_id, self.timestamp)

    def check_filename_diff(self):
        released_notebooks = self._get_assignment_notebooks(
            self.coursedir.course_id, self.coursedir.assignment_id)
        if released_notebooks is None:
            self.log.warning('Unable to get list of assignment files.')
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

    def post_submission(self, src_path):
        encoded_dir = self.encode_dir(src_path)
        url = '/submission/{}/{}'.format(self.coursedir.course_id, self.coursedir.assignment_id)

        response = self.ngshare_api_post(url, encoded_dir)
        if response is None:
            return None
        return response['timestamp']

    def copy_files(self):
        self.log.info("Source: {}".format(self.src_path))

        # copy to the real location
        self.check_filename_diff()
        self.timestamp = self.post_submission(self.src_path)
        if self.timestamp is None:
            self.log.error('Failed to submit.')
            return

        # also copy to the cache
        cache_path = os.path.join(self.cache_path, '{}+{}+{}'.format(
            self.username, self.coursedir.assignment_id, self.timestamp))
        if not os.path.isdir(self.cache_path):
            os.makedirs(self.cache_path)
        self.do_copy(self.src_path, cache_path)
        with open(os.path.join(cache_path, "timestamp.txt"), "w") as fh:
            fh.write(self.timestamp)

        self.log.info("Submitted as: {} {} {}".format(
            self.coursedir.course_id, self.coursedir.assignment_id, str(self.timestamp)
        ))
