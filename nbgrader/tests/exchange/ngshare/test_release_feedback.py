import base64
from json import loads
from logging import getLogger
from pathlib import Path
import os
import shutil

import pytest
from requests import PreparedRequest

from base import parse_body, TestExchange
from nbgrader.exchange.abc.exchange import ExchangeError
from nbgrader.exchange.ngshare.release_feedback import ExchangeReleaseFeedback


class TestExchangeReleaseFeedback(TestExchange):

    feedback_file = ''
    timestamp = ''

    def _mock_requests_release(self):
        url = '{}/feedback/{}/{}/{}'.format(self.base_url,
                self.course_id, self.assignment_id, self.student_id)
        self.requests_mocker.post(url, json=self._post_feedback)

    def _mock_assignment_not_found(self):
        url = '{}/feedback/{}/{}/{}'.format(self.base_url,
                self.course_id, self.assignment_id, self.student_id)
        response = {'success': False, 'message': 'Assignment not found'}
        self.requests_mocker.post(url, json=response)

    def _post_feedback(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        try:
            timestamp = request['timestamp']
            assert timestamp == self.timestamp
            files = loads(request['files'])
            assert len(files) == 1
            feedback_name = self.notebook_id + '.html'
            assert files[0]['path'] == feedback_name
            actual_content = base64.b64decode(files[0]['content'
                    ].encode())
            reference_file = self.files_path / self.feedback_file
            with open(reference_file, 'rb') as expected_content:
                assert actual_content == expected_content.read()
        except Exception as e:
            self.test_failed = True
            getLogger().error(e)
        self.test_completed = True
        return {'success': True}

    def _new_release_feedback(
        self,
        course_id=TestExchange.course_id,
        assignment_id=TestExchange.assignment_id,
        student_id=TestExchange.student_id,
        ):
        return self._new_exchange_object(ExchangeReleaseFeedback,
                course_id, assignment_id, student_id)

    def _prepare_feedback(self):
        feedback_dir = self.course_dir / 'feedback' / self.student_id \
            / self.assignment_id
        files_dir = Path(__file__).parent.parent / 'files'
        os.makedirs(feedback_dir)
        shutil.copyfile(files_dir / 'feedback.html', feedback_dir
                        / (self.notebook_id + '.html'))
        with open(feedback_dir / 'timestamp.txt', 'w') as f:
            f.write('some_timestamp')

    def _prepare_feedback_2(self):
        feedback_dir = self.course_dir / 'feedback' / self.student_id \
            / self.assignment_id
        files_dir = Path(__file__).parent.parent / 'files'
        shutil.copyfile(files_dir / 'feedback-changed.html',
                        feedback_dir / (self.notebook_id + '.html'))
        with open(feedback_dir / 'timestamp.txt', 'w') as f:
            f.write('some_other_timestamp')

    @pytest.fixture(autouse=True)
    def init_release_feedback(self):
        self._prepare_feedback()
        self.release_feedback = self._new_release_feedback()

    def test_404(self):
        self.mock_404()
        self.release_feedback.start()

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        self.release_feedback.start()

    def test_no_course_id(self, tmpdir_factory):
        """Does releasing without a course id thrown an error?"""

        self.release_feedback.coursedir.course_id = ''
        with pytest.raises(ExchangeError):
            self.release_feedback.start()

    def test_release(self):
        self.feedback_file = 'feedback.html'
        self.timestamp = 'some_timestamp'
        self._mock_requests_release()
        self.release_feedback.start()
        assert not self.test_failed
        assert self.test_completed

    def test_release_assignment_not_found(self):
        self._mock_assignment_not_found()
        with pytest.raises(ExchangeError):
            self.release_feedback.start()

    def test_rerelease(self):
        self.feedback_file = 'feedback.html'
        self.timestamp = 'some_timestamp'
        self._mock_requests_release()
        self.release_feedback.start()
        assert not self.test_failed
        assert self.test_completed

        self.feedback_file = 'feedback-changed.html'
        self.timestamp = 'some_other_timestamp'
        self._prepare_feedback_2()
        self._mock_requests_release()
        self.release_feedback.start()
        assert not self.test_failed
        assert self.test_completed

    def test_release_multiple_students(self):
        feedback_dir1 = self.course_dir / 'feedback' / 'student_2' \
            / self.assignment_id
        feedback_dir2 = self.course_dir / 'feedback' / 'student_1' \
            / self.assignment_id
        self.student_id = 'student_2'
        self._prepare_feedback()
        assert os.path.exists(feedback_dir1)
        assert os.path.exists(feedback_dir2)
        self._mock_requests_release()
        self.release_feedback.start()
