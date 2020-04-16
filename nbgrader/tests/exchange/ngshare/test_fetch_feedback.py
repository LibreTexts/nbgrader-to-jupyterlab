import base64
import hashlib
from pathlib import Path
import os

import pytest

from base import TestExchange
from nbgrader.auth import Authenticator
from nbgrader.exchange.abc import ExchangeError
from nbgrader.exchange.ngshare.fetch_feedback import ExchangeFetchFeedback


class TestExchangeFetchFeedback(TestExchange):

    timestamp = 'some_timestamp'

    def _mock_requests_fetch(self):
        '''
        Mock's ngshare's GET feedback, which responds with the feedback file.
        '''

        url = '{}/feedback/{}/{}/{}'.format(self.base_url,
                self.course_id, self.assignment_id, self.student_id)
        content = None
        with open(self.files_path / 'feedback.html', 'rb') as feedback:
            content = feedback.read()

        md5 = hashlib.md5()
        md5.update(content)
        checksum = md5.hexdigest()
        content = base64.b64encode(content).decode()
        files = [{'path': self.notebook_id + '.html',
                 'content': content, 'checksum': checksum}]

        response = {'success': True, 'timestamp': self.timestamp,
                    'files': files}
        self.requests_mocker.get(url, json=response)

    def _new_fetch_feedback(
        self,
        course_id=TestExchange.course_id,
        assignment_id=TestExchange.assignment_id,
        student_id=TestExchange.student_id,
        ):

        retvalue = self._new_exchange_object(ExchangeFetchFeedback,
                course_id, assignment_id, student_id)

        class DummyAuthenticator(Authenticator):

            def has_access(self, student_id, course_id):
                return True

        retvalue.authenticator = DummyAuthenticator()
        retvalue.assignment_dir = str(self.course_dir.absolute())
        return retvalue

    @pytest.fixture(autouse=True)
    def init_fetch_feedback(self, tmpdir_factory):
        assignment_dir = self.course_dir / self.assignment_id
        os.makedirs(assignment_dir)
        self.fetch_feedback = self._new_fetch_feedback()
        self._mock_requests_fetch()

    def test_404(self):
        self.mock_404()
        self.fetch_feedback.start()

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        self.fetch_feedback.start()

    def test_no_course_id(self):
        self.fetch_feedback.coursedir.course_id = ''
        try:
            self.fetch_feedback.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_bad_student_id(self):
        self.fetch_feedback.coursedir.student_id = '***'
        try:
            self.fetch_feedback.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_fetch(self):

        # set chache folder

        submission_name = '{}+{}+{}'.format(self.student_id,
                self.assignment_id, self.timestamp)
        timestamp_path = self.cache_dir / self.course_id \
            / submission_name
        os.makedirs(timestamp_path)

        timestamp_file = timestamp_path / 'timestamp.txt'
        with open(timestamp_file, 'w') as f:
            f.write(self.timestamp)

        self.fetch_feedback.start()

        feedback_path = self.course_dir / self.assignment_id \
            / 'feedback' / self.timestamp / (self.notebook_id + '.html')
        assert feedback_path.is_file()
        with open(self.files_path / 'feedback.html', 'rb') as \
            reference_file:
            with open(feedback_path, 'rb') as actual_file:
                assert actual_file.read() == reference_file.read()

    def test_wrong_student_id(self):
        self.fetch_feedback.coursedir.student_id = 'xx+xx'

        with pytest.raises(ExchangeError):
            self.fetch_feedback.start()

    def test_fetch_multiple_feedback(self):
        timestamp1 = 'timestamp1'
        timestamp2 = 'timestamp2'

        self.timestamp = timestamp1
        submission_name = '{}+{}+{}'.format(self.student_id,
                self.assignment_id, self.timestamp)
        timestamp_path = self.cache_dir / self.course_id \
            / submission_name
        os.makedirs(timestamp_path)
        timestamp_file = timestamp_path / 'timestamp.txt'
        with open(timestamp_file, 'w') as f:
            f.write(self.timestamp)

        self.fetch_feedback.start()
        self.timestamp = timestamp2
        submission_name = '{}+{}+{}'.format(self.student_id,
                self.assignment_id, self.timestamp)
        timestamp_path = self.cache_dir / self.course_id \
            / submission_name

        os.makedirs(timestamp_path)
        timestamp_file = timestamp_path / 'timestamp.txt'
        with open(timestamp_file, 'w') as f:
            f.write(self.timestamp)

        self.fetch_feedback.start()

        feedback_path1 = self.course_dir / self.assignment_id \
            / 'feedback' / timestamp1 / (self.notebook_id + '.html')
        feedback_path2 = self.course_dir / self.assignment_id \
            / 'feedback' / timestamp2 / (self.notebook_id + '.html')

        assert feedback_path1.is_file()
        assert feedback_path2.is_file()

    def test_fetch_multiple_courses(self, tmpdir_factory):
        submission_name = '{}+{}+{}'.format(self.student_id,
                self.assignment_id, self.timestamp)
        timestamp_path = self.cache_dir / self.course_id \
            / submission_name
        os.makedirs(timestamp_path)
        timestamp_file = timestamp_path / 'timestamp.txt'
        with open(timestamp_file, 'w') as f:
            f.write(self.timestamp)
        self.fetch_feedback.start()
        feedback_path = self.course_dir / self.assignment_id \
            / 'feedback' / self.timestamp / (self.notebook_id + '.html')
        assert feedback_path.is_file()

        self.course_id = 'abc102'
        self.course_dir = Path(tmpdir_factory.mktemp(self.course_id))
        assignment_dir = self.course_dir / self.assignment_id
        os.makedirs(assignment_dir)
        self.fetch_feedback = \
            self._new_fetch_feedback(course_id=self.course_id)
        self.timestamp = 'some_other_timestamp'
        submission_name = '{}+{}+{}'.format(self.student_id,
                self.assignment_id, self.timestamp)
        timestamp_path = self.cache_dir / self.course_id \
            / submission_name
        os.makedirs(timestamp_path)
        timestamp_file = timestamp_path / 'timestamp.txt'
        with open(timestamp_file, 'w') as f:
            f.write(self.timestamp)

        self._mock_requests_fetch()
        self.fetch_feedback.start()
        feedback_path = self.course_dir / self.assignment_id \
            / 'feedback' / self.timestamp / (self.notebook_id + '.html')
        assert feedback_path.is_file()
