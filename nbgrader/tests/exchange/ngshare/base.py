import re

import pytest
import requests_mock as rq_mock

from nbgrader.exchange.ngshare.exchange import Exchange
import ngshare_mock
from ngshare_mock import MockNgshare


class TestExchange():
    mock_ngshare = MockNgshare()

    def _mock_get_assignment(self):
        url = re.compile('^{}{}$'.format(self.base_url,
                         ngshare_mock.url_suffix_get_assignment))
        self.requests_mock.get(url, json=self.mock_ngshare.mock_get_assignment)

    def _mock_post_submission(self):
        url = re.compile('^{}{}$'.format(self.base_url,
                         ngshare_mock.url_suffix_post_submission))
        self.requests_mock.post(
            url, json=self.mock_ngshare.mock_post_submission)

    @pytest.fixture(autouse=True)
    def mock_ngshare_requests(self, requests_mock):
        host = Exchange.ngshare_url
        api_prefix = '/api'
        self.base_url = host + api_prefix
        self.requests_mock = requests_mock
        self.mock_ngshare.base_url = self.base_url

        requests_mock.register_uri(rq_mock.ANY, rq_mock.ANY, status_code=404)

        self._mock_get_assignment()
        self._mock_post_submission()
        # TODO: Mock other requests.
