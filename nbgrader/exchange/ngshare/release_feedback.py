import os
import glob
import re
import base64
import json

import requests

from nbgrader.exchange.abc import ExchangeReleaseFeedback as ABCExchangeReleaseFeedback
from .exchange import Exchange


class ExchangeReleaseFeedback(Exchange, ABCExchangeReleaseFeedback):

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
        student_id = self.coursedir.student_id if self.coursedir.student_id else '*'
        self.src_path = self.coursedir.format_path(
            self.coursedir.feedback_directory, student_id,
            self.coursedir.assignment_id)

    def init_dest(self):
        if self.coursedir.course_id == '':
            self.fail("No course id specified. Re-run with --course flag.")

        self.ngshare_url = 'http://172.17.0.1:11111'
        self.username = os.environ['USER'] # TODO: Get from JupyterHub.

    def copy_files(self):
        if self.coursedir.student_id_exclude:
            exclude_students = set(self.coursedir.student_id_exclude.split(','))
        else:
            exclude_students = set()

        staged_feedback = {}  # Maps student IDs to submissions.
        html_files = glob.glob(os.path.join(self.src_path, "*.html"))
        for html_file in html_files:
            regexp = re.escape(os.path.sep).join([
                self.coursedir.format_path(
                    self.coursedir.feedback_directory,
                    "(?P<student_id>.*)",
                    self.coursedir.assignment_id, escape=True),
                "(?P<notebook_id>.*).html"
            ])

            m = re.match(regexp, html_file)
            if m is None:
                msg = "Could not match '%s' with regexp '%s'" % (html_file, regexp)
                self.log.error(msg)
                continue

            gd = m.groupdict()
            student_id = gd['student_id']
            notebook_id = gd['notebook_id']
            if student_id in exclude_students:
                self.log.debug("Skipping student '{}'".format(student_id))
                continue

            feedback_dir = os.path.split(html_file)[0]
            with open(os.path.join(feedback_dir, 'timestamp.txt')) as\
                    timestamp_file:
                timestamp = timestamp_file.read()

            if student_id not in staged_feedback.keys():
                staged_feedback[student_id] = {}  # Maps timestamp to feedback.
            if timestamp not in staged_feedback[student_id].keys():
                staged_feedback[student_id][timestamp] = []  # List of info.
            staged_feedback[student_id][timestamp].append(
                {'notebook_id': notebook_id, 'path': html_file})

        for student_id, submission in staged_feedback.items():  # Student.
            for timestamp, feedback_info in submission.items():  # Submission.
                self.log.info("Releasing feedback for student '{}' on "
                              "assignment '{}/{}/{}' ({})".format(
                                student_id, self.coursedir.course_id,
                                self.coursedir.assignment_id, notebook_id,
                                timestamp))
                try:
                    self.post_feedback(student_id, timestamp, feedback_info)
                    self.log.info('Feedback released.')
                except Exception as e:
                    self.log.error('Failed to upload feedback to server. '
                                   'Reason: {}' .format(e))

    def post_feedback(self, student_id, timestamp, feedback_info):
        """
        Uploads feedback files for a specific submission.
        ``feedback_info`` - A list of feedback files. Each feedback file is
        represented as a dictionary with a "path" to the local feedback file and
        "notebook_id" of the corresponding notebook.
        """
        url = self.ngshare_url + '/api/feedback/{}/{}/{}'.format(
            self.coursedir.course_id, self.coursedir.assignment_id, student_id)
        files = json.dumps([self.encode_file(x['path'],
                                             '{}.html'.format(x['notebook_id'])
                                             ) for x in feedback_info])
        data = {'user': self.username, 'timestamp': timestamp, 'files': files}

        response = requests.post(url, data=data)
        self.check_response(response)

    # TODO: Consider moving into Exchange.
    def encode_file(self, filesystem_path, assignment_path):
        with open(filesystem_path, 'rb') as f:
            content = f.read()
        return {'path': assignment_path, 'content':
                base64.encodebytes(content).decode()}
