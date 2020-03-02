import os
import glob
import shutil
import sys
from collections import defaultdict
from textwrap import dedent

import requests
from traitlets import Bool

from nbgrader.exchange.abc import ExchangeCollect as ABCExchangeCollect
from .exchange import Exchange

from nbgrader.utils import check_mode, parse_utc

# pwd is for matching unix names with student ide, so we shouldn't import it on
# windows machines
if sys.platform != 'win32':
    import pwd
else:
    pwd = None

def groupby(l, key=lambda x: x):
    d = defaultdict(list)
    for item in l:
        d[key(item)].append(item)
    return d


class ExchangeCollect(Exchange, ABCExchangeCollect):

    def _get_submission(self, course_id, assignment_id, student_id):
        """
        Returns the student's submission. A submission is a dictionary
        containing a "timestamp" and "files" list. Each file in the list is a
        dictionary containing the "path" relative to the assignment root and the
        "content" as an ASCII representation of the base64 encoded bytes.
        """
        url = self.ngshare_url + '/api/submission/{}/{}/{}'.format(
            course_id, assignment_id, student_id)
        params = {'user': self.username}

        try:
            response = requests.get(url, params=params)
        except:
            self.log.error('An error occurred downloading a submission.')
            return None

        if response.status_code != requests.codes.ok or not response.json()['success']:
            self.log.error('An error occurred downloading a submission.')
            return None

        return {'timestamp': response.json()['timestamp'],
                'files': response.json()['files']}

    def _get_submission_list(self, course_id, assignment_id):
        """
        Returns a list of submission entries. Each entry is a dictionary
        containing the "student_id" and "timestamp".
        """
        url = self.ngshare_url + '/api/submissions/{}/{}'.format(
            course_id, assignment_id)
        params = {'user': self.username}

        try:
            response = requests.get(url, params=params)
        except Exception as e:
            self.log.error('An error occurred querying submissions.')
            print(e)
            return []

        if response.status_code != requests.codes.ok or not response.json()['success']:
            return []

        return [{'student_id': x['student_id'], 'timestamp': x['timestamp']}
                for x in response.json()['submissions']]

    def _path_to_record(self, path):
        filename = os.path.split(path)[1]
        # Only split twice on +, giving three components. This allows usernames with +.
        filename_list = filename.rsplit('+', 3)
        if len(filename_list) < 3:
            self.fail("Invalid filename: {}".format(filename))
        username = filename_list[0]
        timestamp = parse_utc(filename_list[2])
        return {'username': username, 'filename': filename, 'timestamp': timestamp}

    def _sort_by_timestamp(self, records):
        return sorted(records, key=lambda item: item['timestamp'], reverse=True)

    def init_src(self):
        if self.coursedir.course_id == '':
            self.fail("No course id specified. Re-run with --course flag.")

        self.ngshare_url = 'http://172.17.0.1:11111' # TODO: Find server address.
        self.username = os.environ['USER'] # TODO: Get from JupyterHub.
        records = self._get_submission_list(self.coursedir.course_id,
            self.coursedir.assignment_id)
        usergroups = groupby(records, lambda item: item['student_id'])
        self.src_records = [self._sort_by_timestamp(v)[0] for v in usergroups.values()]

    def init_dest(self):
        pass

    def copy_files(self):
        if len(self.src_records) == 0:
            self.log.warning("No submissions of '{}' for course '{}' to collect".format(
                self.coursedir.assignment_id,
                self.coursedir.course_id))
        else:
            self.log.info("Processing {} submissions of '{}' for course '{}'".format(
                len(self.src_records),
                self.coursedir.assignment_id,
                self.coursedir.course_id))

        for rec in self.src_records:
            student_id = rec['student_id']

            dest_path = self.coursedir.format_path(self.coursedir.submitted_directory, student_id, self.coursedir.assignment_id)
            if not os.path.exists(os.path.dirname(dest_path)):
                os.makedirs(os.path.dirname(dest_path))

            copy = False
            updating = False
            if os.path.isdir(dest_path):
                existing_timestamp = self.coursedir.get_existing_timestamp(dest_path)
                new_timestamp = rec['timestamp']
                if self.update and (existing_timestamp is None or new_timestamp > existing_timestamp):
                    copy = True
                    updating = True
            else:
                copy = True

            if copy:
                if updating:
                    self.log.info("Updating submission: {} {}".format(student_id, self.coursedir.assignment_id))
                    shutil.rmtree(dest_path)
                else:
                    self.log.info("Collecting submission: {} {}".format(student_id, self.coursedir.assignment_id))
                submission = self._get_submission(self.coursedir.course_id,
                    self.coursedir.assignment_id, student_id)
                self.do_copy(submission['files'], dest_path)
            else:
                if self.update:
                    self.log.info("No newer submission to collect: {} {}".format(
                        student_id, self.coursedir.assignment_id
                    ))
                else:
                    self.log.info("Submission already exists, use --update to update: {} {}".format(
                        student_id, self.coursedir.assignment_id
                    ))

    def do_copy(self, src, dest):
        """
        Repurposed version of Exchange.do_copy.
        """
        self.encode_dir(src, dest)
