import base64
import hashlib
import logging
import os
from pathlib import Path
import re
import shutil

from _pytest.logging import LogCaptureFixture
from _pytest.tmpdir import TempdirFactory
import pytest
from requests import PreparedRequest
from textwrap import dedent

from base import parse_body, TestExchange
from nbgrader.auth import Authenticator
from nbgrader.exchange.abc.exchange import ExchangeError
from nbgrader.exchange.ngshare import ExchangeList


class TestExchangeList(TestExchange):
    course_id2 = 'xyz200'
    assignment_id2 = 'ps2'
    timestamp1 = '2000-02-03 12:34:56.789012 UTC'
    timestamp2 = '2001-02-03 12:34:56.789012 UTC'

    def _delete_assignment(self, request: PreparedRequest, context):
        if not self.is_instructor:
            return {'success': False, 'message': 'Permission denied'}
        self.test_completed = True
        return {'success': True}

    def _feedback_content(self):
        reference_file = self.files_path / 'feedback.html'
        with open(reference_file, 'rb') as file:
            return file.read()

    def _fetch(self, course_dir, assignment_id=TestExchange.assignment_id):
        notebook_path = course_dir / assignment_id\
                        / (self.notebook_id + '.ipynb')
        notebook_path.parent.mkdir()
        shutil.copyfile(self.files_path / 'test.ipynb', notebook_path)
        pass

    def _fetch_feedback(self, course_dir, course_id, assignment_id, timestamp):
        feedback_dir = course_dir / assignment_id / 'feedback' / timestamp
        feedback_dir.mkdir(parents=True)
        html_path = feedback_dir / (self.notebook_id + '.html')
        timestamp_path = feedback_dir / 'timestamp.txt'
        shutil.copyfile(self.files_path / 'feedback.html', html_path)
        with open(timestamp_path, 'w') as timestamp_file:
            timestamp_file.write(timestamp)

    def _get_assignment(self, request: PreparedRequest, context):
        content = self._notebook_content()
        md5 = hashlib.md5()
        md5.update(content)
        checksum = md5.hexdigest()
        files = [{'path': self.notebook_id + '.ipynb',
                  'content': base64.b64encode(content).decode(),
                  'checksum': checksum}]
        return {'success': True, 'files': files}

    def _get_assignments(self, request: PreparedRequest, context):
        assignments = [self.assignment_id, self.assignment_id2]
        return {'success': True, 'assignments':
                assignments[:self.num_assignments]}

    def _get_courses(self, request: PreparedRequest, context):
        courses = [self.course_id, self.course_id2]
        return {'success': True, 'courses': courses[:self.num_courses]}

    def _get_feedback(self, request: PreparedRequest, context):
        pattern = re.compile(r'\?[^#]*')
        matches = pattern.findall(request.url)
        if len(matches) == 0 or 'timestamp' not in parse_body(matches[0]):
            print(request)
            return {'success': False, 'message': 'Please supply timestamp'}
        timestamp = parse_body(matches[0])['timestamp']
        if timestamp not in [self.timestamp1, self.timestamp2]:
            return {'success': False, 'message': 'Submission not found'}
        files = []
        if (timestamp == self.timestamp1 and self.num_feedback > 0) or\
                (timestamp == self.timestamp2 and self.num_feedback > 1):
            content = self._feedback_content()
            md5 = hashlib.md5()
            md5.update(content)
            checksum = md5.hexdigest()
            files = [{'path': self.notebook_id + '.html',
                      'content': base64.b64encode(content).decode(),
                      'checksum': checksum}]
        return {'success': True, 'timestamp': timestamp, 'files': files}

    def _get_student_submissions(self, request: PreparedRequest, context):
        submissions = [
            {'student_id': self.student_id, 'timestamp': self.timestamp1},
            {'student_id': self.student_id, 'timestamp': self.timestamp2}]
        return {'success': True,
                'submissions': submissions[:self.num_submissions]}

    def _get_submission(self, request: PreparedRequest, context):
        if not self.is_instructor:
            return {'success': False, 'message': 'Permission denied'}
        return self._get_assignment(request, context)

    def _get_submissions(self, request: PreparedRequest, context):
        return self._get_student_submissions(request, context)

    def _mock_requests_list(self):
        """
        Mocks ngshare's GET courses, GET assignments, GET assignment, DELETE
        assignment, GET submissions GET student's submissions, GET submission,
        and GET feedback.
        """
        url = '{}/courses'.format(self.base_url)
        self.requests_mocker.get(url, json=self._get_courses)

        url = '{}/assignments/{}'.format(self.base_url, self.course_id)
        self.requests_mocker.get(url, json=self._get_assignments)
        url = '{}/assignments/{}'.format(self.base_url, self.course_id2)
        self.requests_mocker.get(url, json=self._get_assignments)

        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        self.requests_mocker.get(url, json=self._get_assignment)
        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id2,
                                           self.assignment_id)
        self.requests_mocker.get(url, json=self._get_assignment)
        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id2)
        self.requests_mocker.get(url, json=self._get_assignment)
        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id2,
                                           self.assignment_id2)
        self.requests_mocker.get(url, json=self._get_assignment)

        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        self.requests_mocker.delete(url, json=self._delete_assignment)

        url = '{}/submissions/{}/{}'.format(self.base_url, self.course_id,
                                            self.assignment_id)
        self.requests_mocker.get(url, json=self._get_submissions)

        url = '{}/submissions/{}/{}/{}'.format(self.base_url, self.course_id,
                                               self.assignment_id,
                                               self.student_id)
        self.requests_mocker.get(url, json=self._get_student_submissions)

        url = '{}/submission/{}/{}/{}'.format(self.base_url, self.course_id,
                                              self.assignment_id,
                                              self.student_id)
        self.requests_mocker.get(url, json=self._get_submission)

        url = '{}/feedback/{}/{}/{}'.format(self.base_url, self.course_id,
                                            self.assignment_id,
                                            self.student_id)
        self.requests_mocker.get(url, json=self._get_feedback)
        url = '{}/feedback/{}/{}/{}'.format(self.base_url, self.course_id,
                                            self.assignment_id2,
                                            self.student_id)
        self.requests_mocker.get(url, json=self._get_feedback)

    def _new_list(self, course_id=TestExchange.course_id,
                  assignment_id=TestExchange.assignment_id,
                  student_id=TestExchange.student_id):
        retvalue = self._new_exchange_object(ExchangeList, course_id,
                                             assignment_id, student_id)

        class DummyAuthenticator(Authenticator):
            def has_access(self, student_id, course_id):
                return True
        retvalue.authenticator = DummyAuthenticator()
        retvalue.assignment_dir = str(self.course_dir.absolute())
        return retvalue

    def _notebook_content(self):
        reference_file = self.files_path / 'test.ipynb'
        with open(reference_file, 'rb') as file:
            return file.read()

    def _read_log(self):
        log_records = ['[{}] {}\n'.format(x.levelname, x.getMessage())
                       for x in self.caplog.get_records('call')]
        self.caplog.clear()
        return ''.join(log_records)

    def _submit(self, course_id=TestExchange.course_id,
                assignment_id=TestExchange.assignment_id,
                timestamp=timestamp1):
        assignment_filename = '{}+{}+{}'.format(self.student_id, assignment_id,
                                                timestamp)
        notebook_path = self.cache_dir / course_id / assignment_filename\
            / (self.notebook_id + '.ipynb')
        timestamp_path = notebook_path.parent / 'timestamp.txt'
        notebook_path.parent.mkdir(parents=True)
        shutil.copyfile(self.files_path / 'test.ipynb', notebook_path)
        with open(timestamp_path, 'w') as timestamp_file:
            timestamp_file.write(timestamp)

    @pytest.fixture(autouse=True)
    def init_submit(self, caplog: LogCaptureFixture,
                    tmpdir_factory: TempdirFactory):
        self.caplog = caplog
        self.course_dir2 = Path(
            tmpdir_factory.mktemp(self.course_id2)).absolute()
        self._mock_requests_list()
        self.list = self._new_list()
        os.chdir(self.course_dir)
        self.caplog.set_level(logging.INFO)
        self.list.coursedir.course_id = '*'
        self.list.coursedir.assignment_id = '*'
        self.num_courses = 1
        self.num_assignments = 0
        self.num_submissions = 0
        self.num_feedback = 0
        self.is_instructor = True

    def test_404(self):
        self.mock_404()
        with pytest.raises(ExchangeError):
            self.list.start()

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        with pytest.raises(ExchangeError):
            self.list.start()

    def test_list_released_2x1_course1(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.start()
        output = self._read_log()
        assert output == dedent(
            """
            [INFO] Released assignments:
            [INFO] {} {}
            """
        ).lstrip().format(self.course_id, self.assignment_id)

    def test_list_released_2x1_course2(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id2
        self.list.start()
        output = self._read_log()
        assert output == dedent(
            """
            [INFO] Released assignments:
            [INFO] {} {}
            """
        ).lstrip().format(self.course_id2, self.assignment_id)

    def test_list_released_2x1(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = '*'
        self.list.start()
        output = self._read_log()
        assert output == dedent(
            """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            """
        ).lstrip().format(self.course_id, self.assignment_id,
                          self.course_id2, self.assignment_id)

    def test_list_released_2x2_assignment1(self):
        self.num_courses = 2
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        output = self._read_log()
        assert output == dedent(
            """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            """
        ).lstrip().format(self.course_id, self.assignment_id,
                          self.course_id2, self.assignment_id)

    def test_list_released_2x2_assignment2(self):
        self.num_courses = 2
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id2
        self.list.start()
        output = self._read_log()
        assert output == dedent(
            """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            """
        ).lstrip().format(self.course_id, self.assignment_id2,
                          self.course_id2, self.assignment_id2)

    def test_list_released_2x2(self):
        self.num_courses = 2
        self.num_assignments = 2
        self.list.start()
        output = self._read_log()
        assert output == dedent(
            """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            [INFO] {} {}
            [INFO] {} {}
            """
        ).lstrip().format(self.course_id, self.assignment_id,
                          self.course_id, self.assignment_id2,
                          self.course_id2, self.assignment_id,
                          self.course_id2, self.assignment_id2)

    def test_list_fetched(self):
        self.num_assignments = 2
        self._fetch(self.course_dir)
        self.list.start()
        output = self._read_log()
        assert output == dedent(
            """
            [INFO] Released assignments:
            [INFO] {} {} (already downloaded)
            [INFO] {} {}
            """
        ).lstrip().format(self.course_id, self.assignment_id,
                          self.course_id, self.assignment_id2,)

    def test_list_remove_outbound(self):
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.remove = True
        self.list.start()
        assert not self.test_failed
        assert self.test_completed

    def test_list_inbound_0(self):
        self.num_assignments = 1
        self.num_submissions = 0
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            """
        ).lstrip()

    def test_list_inbound_1(self):
        self.num_assignments = 1
        self.num_submissions = 1
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1)

    def test_list_inbound_2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_cached_0(self):
        self.num_assignments = 1
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            """
        ).lstrip()

    def test_list_cached_1(self):
        self.num_assignments = 1
        self._submit()
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1)

    def test_list_cached_2(self):
        self.num_assignments = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_remove_cached(self):
        self._submit()
        self._submit(assignment_id=self.assignment_id2,
                     timestamp=self.timestamp2)
        self.is_instructor = False
        self.list.cached = True
        self.list.remove = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        self._read_log()
        self.list.remove = False
        self.list.coursedir.assignment_id = '*'
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id2,
                          self.timestamp2)

    def test_list_cached_and_inbound(self):
        self.is_instructor = False
        self.list.cached = True
        self.list.inbound = True
        with pytest.raises(ExchangeError):
            self.list.start()

    def test_list_feedback_inbound_ready1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_inbound_fetched1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_inbound_modified1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        feedback_path = self.course_dir / self.assignment_id / 'feedback'\
            / self.timestamp1 / (self.notebook_id + '.html')
        # This part is different from the original test because the fetched
        # feedback is modified instead of the outbound one, but the results
        # should be the same.
        with open(feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_inbound_modified1_ready1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        feedback_path = self.course_dir / self.assignment_id / 'feedback'\
            / self.timestamp1 / (self.notebook_id + '.html')
        with open(feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        self.num_feedback = 2
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (feedback ready to be fetched)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_inbound_fetched2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp2)
        self.num_feedback = 2
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (feedback already fetched)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_cached_ready1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_cached_fetched1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_cached_modified1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        feedback_path = self.course_dir / self.assignment_id / 'feedback'\
            / self.timestamp1 / (self.notebook_id + '.html')
        # This part is different from the original test because the fetched
        # feedback is modified instead of the outbound one, but the results
        # should be the same.
        with open(feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_cached_ready2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        feedback_path = self.course_dir / self.assignment_id / 'feedback'\
            / self.timestamp1 / (self.notebook_id + '.html')
        with open(feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        self.num_feedback = 2
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (feedback ready to be fetched)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)

    def test_list_feedback_cached_fetched2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp1)
        self._fetch_feedback(self.course_dir, self.course_id,
                             self.assignment_id, self.timestamp2)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.num_feedback = 2
        self.list.start()
        assert self._read_log() == dedent(
            """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (feedback already fetched)
            """
        ).lstrip().format(self.course_id, self.student_id, self.assignment_id,
                          self.timestamp1, self.course_id, self.student_id,
                          self.assignment_id, self.timestamp2)
