import base64
import os

import pytest
from requests import PreparedRequest

from base import parse_body, TestExchange
from nbgrader.exchange.abc.exchange import ExchangeError
from nbgrader.exchange.ngshare import ExchangeCollect
from nbgrader.utils import parse_utc


class TestExchangeCollect(TestExchange):
    def _get_submission(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        timestamp = None
        try:
            if 'timestamp' in request:
                timestamp = request['timestamp']
            else:
                timestamp = str(2000 + self.num_submissions)\
                    + self.timestamp_template
            time = parse_utc(timestamp)
            assert time.year > 2000 and time.year < 2001 + self.num_submissions
            assert timestamp == str(time.year) + self.timestamp_template
        except Exception:
            return {'success': False, 'message': 'Submission not found'}
        content = base64.b64encode(self._notebook_content()).decode()
        files = [{'path': self.notebook_id + '.ipynb', 'content': content}]
        return {'success': True, 'timestamp': timestamp, 'files': files}

    def _get_submissions(self, request: PreparedRequest, context):
        submissions = []
        for i in range(self.num_submissions):
            timestamp = str(2001 + i) + self.timestamp_template
            submissions.append({'student_id': self.student_id,
                                'timestamp': timestamp})
        return {'success': True, 'submissions': submissions}

    def _mock_requests_collect(self):
        """
        Mock's ngshare's GET submissions, which responds with the submissions,
        and GET submission, which responds with the submission.
        """
        url = '{}/submissions/{}/{}'.format(self.base_url, self.course_id,
                                            self.assignment_id)
        self.requests_mocker.get(url, json=self._get_submissions)

        url = '{}/submission/{}/{}/{}'.format(self.base_url, self.course_id,
                                              self.assignment_id,
                                              self.student_id)
        self.requests_mocker.get(url, json=self._get_submission)

    def _mock_requests_subdir(self, subdirectory, subdirectory_file):
        """
        Mock's ngshare's GET submissions, which responds with the submission,
        and GET submission, which responds with the submission with a
        subdirectory.
        """
        url = '{}/submissions/{}/{}'.format(self.base_url, self.course_id,
                                            self.assignment_id)
        timestamp = '2000' + self.timestamp_template
        submissions = [{'student_id': self.student_id, 'timestamp': timestamp}]
        response = {'success': True, 'submissions': submissions}
        self.requests_mocker.get(url, json=response)

        url = '{}/submission/{}/{}/{}'.format(self.base_url, self.course_id,
                                              self.assignment_id,
                                              self.student_id)
        content1 = base64.b64encode(self._notebook_content()).decode()
        content2 = base64.b64encode(''.encode()).decode()
        path2 = '{}/{}'.format(subdirectory, subdirectory_file)
        files = [{'path': self.notebook_id + '.ipynb', 'content': content1},
                 {'path': path2, 'content': content2}]
        response = {'success': True, 'timestamp': timestamp, 'files': files}
        self.requests_mocker.get(url, json=response)

    def _new_collect(self, course_id=TestExchange.course_id,
                     assignment_id=TestExchange.assignment_id,
                     student_id=TestExchange.student_id):
        return self._new_exchange_object(ExchangeCollect, course_id,
                                         assignment_id, student_id)

    def _notebook_content(self):
        reference_file = self.files_path / 'test.ipynb'
        with open(reference_file, 'rb') as file:
            return file.read()

    @pytest.fixture(autouse=True)
    def init_collect(self):
        self.collect = self._new_collect()
        os.chdir(self.course_dir)

    def submission_dir(self):
        return (self.course_dir / 'submitted' / self.student_id
                / self.assignment_id)

    @property
    def timestamp_template(self):
        return '-12-21 12:34:56.789012 UTC'

    def test_404(self):
        self.mock_404()
        self.collect.start()

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        self.collect.start()

    def test_no_course_id(self):
        """Does collecting without a course id throw an error?"""
        self._mock_requests_collect()
        with pytest.raises(ExchangeError):
            self.collect.start()

    def test_collect_0(self):
        self.num_submissions = 0
        self._mock_requests_collect()
        self.collect.start()
        assert not (self.course_dir / 'submitted').is_dir()

    def test_collect_1(self):
        self.num_submissions = 1
        self._mock_requests_collect()
        self.collect.start()
        notebook = self.submission_dir() / (self.notebook_id + '.ipynb')
        timestamp_path = self.submission_dir() / 'timestamp.txt'
        assert notebook.is_file()
        assert timestamp_path.is_file()
        with open(notebook, 'rb') as notebook_file, open(timestamp_path, 'r')\
                as timestamp_file:
            assert notebook_file.read() == self._notebook_content()
            assert timestamp_file.read() == '2001' + self.timestamp_template

    def test_collect_1_twice(self):
        self.num_submissions = 1
        self._mock_requests_collect()
        self.collect.start()
        self.collect.start()
        timestamp_path = self.submission_dir() / 'timestamp.txt'
        with open(timestamp_path, 'r') as timestamp_file:
            assert timestamp_file.read() == '2001' + self.timestamp_template

    def test_collect_no_update(self):
        self.num_submissions = 1
        self._mock_requests_collect()
        self.collect.start()
        self.num_submissions = 2
        self.collect.start()
        timestamp_path = self.submission_dir() / 'timestamp.txt'
        with open(timestamp_path, 'r') as timestamp_file:
            assert timestamp_file.read() == '2001' + self.timestamp_template

    def test_collect_update(self):
        self.num_submissions = 1
        self._mock_requests_collect()
        self.collect.start()
        self.num_submissions = 2
        self.collect.update = True
        self.collect.start()
        timestamp_path = self.submission_dir() / 'timestamp.txt'
        with open(timestamp_path, 'r') as timestamp_file:
            assert timestamp_file.read() == '2002' + self.timestamp_template

    def test_collect_subdirectories(self):
        subdir = 'foo'
        subfile = 'temp.txt'
        self.num_submissions = 1
        self._mock_requests_subdir(subdir, subfile)
        self.collect.start()
        assert (self.course_dir / 'submitted' / self.student_id
                / self.assignment_id / subdir / subfile).is_file()
