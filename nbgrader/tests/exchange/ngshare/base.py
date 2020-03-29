from logging import getLogger
from pathlib import Path
import re

import pytest
from requests import PreparedRequest
import requests_mock as rq_mock
from requests_mock import Mocker

from nbgrader.coursedir import CourseDirectory
from nbgrader.exchange.ngshare.exchange import Exchange
import ngshare_mock
from ngshare_mock import MockNgshare


class TestExchange():
    course_id = 'abc101'
    assignment_id = 'ps1'
    student_id = 'student_1'
    notebook_id = 'p1'
    mock_ngshare = MockNgshare()
    test_failed = False
    test_completed = False

    def _init_cache_dir(self, tmpdir_factory):
        return Path(tmpdir_factory.mktemp('nbgrader_cache')).absolute()

    def _init_course_dir(self, tmpdir_factory):
        return Path(tmpdir_factory.mktemp(self.course_id)).absolute()

    def _mock_all(self, request: PreparedRequest, content):
        getLogger().fatal('The request "%s" has not been mocked yet.',
                          request.url)
        content.status_code = 404
        return ''

    def _mock_get_assignment(self):
        url = re.compile('^{}{}$'.format(self.base_url,
                         ngshare_mock.url_suffix_get_assignment))
        self.requests_mock.get(url, json=self.mock_ngshare.mock_get_assignment)

    def _mock_post_submission(self):
        url = re.compile('^{}{}$'.format(self.base_url,
                         ngshare_mock.url_suffix_post_submission))
        self.requests_mock.post(
            url, json=self.mock_ngshare.mock_post_submission)

    def _new_exchange_object(self, cls, course_id, assignment_id, student_id):
        assert issubclass(cls, Exchange)
        cls.cache = str(self.cache_dir)
        coursedir = CourseDirectory()
        coursedir.root = str(self.course_dir)
        coursedir.course_id = course_id
        coursedir.assignment_id = assignment_id
        obj = cls(coursedir=coursedir)
        obj.username = student_id
        return obj

    @property
    def files_path(self) -> Path:
        return Path(__file__).parent.parent / 'files'

    @pytest.fixture(autouse=True)
    def init(self, requests_mock: Mocker, tmpdir_factory):
        self.course_dir = self._init_course_dir(tmpdir_factory)
        self.cache_dir = self._init_cache_dir(tmpdir_factory)
        self.requests_mocker = requests_mock

    @pytest.fixture(autouse=True)
    def mock_ngshare_requests(self, requests_mock: Mocker):
        host = Exchange.ngshare_url
        api_prefix = '/api'
        self.base_url = host + api_prefix
        self.requests_mock = requests_mock
        self.mock_ngshare.base_url = self.base_url

        requests_mock.register_uri(rq_mock.ANY, rq_mock.ANY,
                                   text=self._mock_all)

        self._mock_get_assignment()
        self._mock_post_submission()
        # TODO: Mock other requests.
