import base64
from json import loads
from logging import getLogger
from pathlib import Path
import os
import shutil

import pytest
from requests import PreparedRequest

from .base import parse_body, TestExchange
from ....exchange.abc.exchange import ExchangeError
from ....exchange.ngshare.release_assignment import \
    ExchangeReleaseAssignment


class TestExchangeReleaseAssignment(TestExchange):
    def _delete_assignment(self, request: PreparedRequest, context):
        if not self.released:
            return {'success': False, 'message': 'Assignment not found'}
        self.released = False
        return {'success': True}

    def _get_assignments(self, request: PreparedRequest, context):
        if self.released:
            return {'success': True, 'assignments': [self.assignment_id]}
        return {'success': True, 'assignments': []}

    def _mock_requests_release(self):
        '''
        Mocks ngshare's GET assignments, which responds with no assignments,
        and POST assignment, which verifies the request.
        '''
        url = '{}/assignments/{}'.format(self.base_url, self.course_id)
        print(url)
        response = {'success': True, 'assignments': []}
        self.requests_mocker.get(url, json=response)

        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        self.requests_mocker.post(url, json=self._post_assignment)

    def _mock_requests_released(self):
        '''
        Mocks ngshare's GET assignments, which responds with the assignment,
        and POST assignment, which responds with "Assignment already exists".
        '''
        url = '{}/assignments/{}'.format(self.base_url, self.course_id)
        response = {'success': True, 'assignments': [self.assignment_id]}
        self.requests_mocker.get(url, json=response)

        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        response = {'success': False, 'message': 'Assignment already exists'}
        self.requests_mocker.post(url, json=response)

    def _mock_requests_force_rerelease(self):
        '''
        Mocks ngshare's GET assignments, which responds with the assignment if
        DELETE assignment has not been called or no assignment otherwise, POST
        assignment, which responds with "Assignment already exists" if DELETE
        assignment has not been called or success otherwise, and DELETE
        assignment, which notes that the assignment no longer exists.
        '''
        url = '{}/assignments/{}'.format(self.base_url, self.course_id)
        self.requests_mocker.get(url, json=self._get_assignments)

        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        self.requests_mocker.post(url, json=self._post_assignment)

        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        self.requests_mocker.delete(url, json=self._delete_assignment)

    def _new_release_assignment(self, course_id=TestExchange.course_id,
                                assignment_id=TestExchange.assignment_id,
                                student_id=TestExchange.student_id):
        return self._new_exchange_object(ExchangeReleaseAssignment, course_id,
                                         assignment_id, student_id)

    def _post_assignment(self, request: PreparedRequest, context):
        if self.released:
            return {'success': False, 'message': 'Assignment already exists'}

        request = parse_body(request.body)
        try:
            files = loads(request['files'])
            assert len(files) == 1
            notebook_name = self.notebook_id + '.ipynb'
            assert files[0]['path'] == notebook_name
            actual_content = base64.b64decode(files[0]['content'].encode())
            reference_file = self.files_path / 'test.ipynb'
            with open(reference_file, 'rb') as expected_content:
                assert actual_content == expected_content.read()
        except Exception as e:
            self.test_failed = True
            getLogger().error(e)
        self.test_completed = True
        return {'success': True}

    def _prepare_assignment(self):
        assignment_dir = self.course_dir / 'release' / self.assignment_id
        files_dir = Path(__file__).parent.parent / 'files'
        os.makedirs(assignment_dir)
        shutil.copyfile(files_dir / 'test.ipynb',
                        assignment_dir / (self.notebook_id + '.ipynb'))

    @pytest.fixture(autouse=True)
    def init_release_assignment(self):
        self._prepare_assignment()
        self.release_assignment = self._new_release_assignment()

    def test_404(self):
        self.mock_404()
        try:
            self.release_assignment.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        try:
            self.release_assignment.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_no_course_id(self, tmpdir_factory):
        """Does releasing without a course id thrown an error?"""
        self.release_assignment.coursedir.course_id = ''
        with pytest.raises(ExchangeError):
            self.release_assignment.start()

    def test_release(self):
        self.released = False
        self._mock_requests_release()
        self.release_assignment.start()

        assert not self.test_failed
        assert self.test_completed

    def test_rerelease(self):
        self._mock_requests_released()
        with pytest.raises(ExchangeError):
            self.release_assignment.start()

    def test_force_rerelease(self):
        self.released = True
        self._mock_requests_force_rerelease()
        self.release_assignment.force = True
        self.release_assignment.start()
        assert not self.test_failed
        assert self.test_completed
