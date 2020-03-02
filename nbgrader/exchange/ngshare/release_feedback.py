import os
import shutil
import glob
import re
from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IWGRP, S_IXGRP, S_IXOTH, S_ISGID
import base64
import json

import requests

from nbgrader.exchange.abc import ExchangeReleaseFeedback as ABCExchangeReleaseFeedback
from .exchange import Exchange
from nbgrader.utils import notebook_hash, make_unique_key


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
            timestamp = open(os.path.join(feedback_dir, 'timestamp.txt')).read()

            self.log.info("Releasing feedback for student '{}' on assignment '{}/{}/{}' ({})".format(
                student_id, self.coursedir.course_id, self.coursedir.assignment_id, notebook_id, timestamp))
            self.post_feedback(html_file, student_id, timestamp)
            self.log.info('Feedback released.')

    def post_feedback(self, feedback_file, student_id, timestamp):
        url = self.ngshare_url + '/api/feedback/{}/{}/{}'.format(
            self.coursedir.course_id, self.coursedir.assignment_id, student_id)
        files = json.dumps([self.encode_file(feedback_file)])
        random_str = '4' # xkcd 221
        data = {'user': self.username, 'timestamp': timestamp,
                'random': random_str, 'files': files}

        response = requests.post(url, data=data)
        self.check_response(response)

    # TODO: Consider moving into Exchange.
    def encode_file(self, filename):
        with open(filename, 'rb') as f:
            content = f.read()
        return {'path': filename, 'content':
                base64.encodebytes(content).decode()}
