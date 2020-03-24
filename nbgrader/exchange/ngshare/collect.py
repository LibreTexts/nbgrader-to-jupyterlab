import os
import shutil
import sys
from collections import defaultdict
import base64

from nbgrader.exchange.abc import ExchangeCollect as ABCExchangeCollect
from .exchange import Exchange

from nbgrader.utils import parse_utc

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

        response = self.ngshare_api_get("/submission/{}/{}/{}".format(
                    course_id, assignment_id, student_id))
        if response is None:
            self.log.error('An error occurred downloading a submission.')
            return None

        timestamp = response['timestamp']
        files = response['files']
        files.append({'path': 'timestamp.txt', 'content':
                      base64.encodebytes(timestamp.encode()).decode()})
        return {'timestamp': timestamp, 'files': files}

    def _get_submission_list(self, course_id, assignment_id):
        """
        Returns a list of submission entries. Each entry is a dictionary
        containing the "student_id" and "timestamp".
        """
        response = self.ngshare_api_get('/submissions/{}/{}'.format(course_id, assignment_id))
        if response is None:
            return None

        return [{'student_id': x['student_id'],
                 'timestamp': parse_utc(x['timestamp'])}
                for x in response['submissions']]

    def _sort_by_timestamp(self, records):
        return sorted(records, key=lambda item: item['timestamp'], reverse=True)

    def init_src(self):
        if self.coursedir.course_id == '':
            self.fail("No course id specified. Re-run with --course flag.")

        try:
            records = self._get_submission_list(self.coursedir.course_id,
                                                self.coursedir.assignment_id)
        except Exception as e:
            self.fail('Failed to list submissions. Reason: {}'.format(e))
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
                if submission is None:
                    continue
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
        self.decode_dir(src, dest)
