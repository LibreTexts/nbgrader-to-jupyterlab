import base64
import hashlib
from pathlib import Path
import shutil

import pytest

from base import TestExchange
from nbgrader.auth import Authenticator
from nbgrader.exchange.abc import ExchangeError
from nbgrader.exchange.ngshare.fetch_assignment import ExchangeFetchAssignment


class TestExchangeFetchAssignment(TestExchange):
    def _mock_requests_fetch(self):
        '''
        Mock's ngshare's GET assignment, which responds with the assignment.
        '''
        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        content = None
        with open(self.files_path / 'test.ipynb', 'rb') as notebook:
            content = notebook.read()
        md5 = hashlib.md5()
        md5.update(content)
        checksum = md5.hexdigest()
        content = base64.b64encode(content).decode()
        files = [{'path': self.notebook_id + '.ipynb', 'content': content,
                  'checksum': checksum}]
        response = {'success': True, 'files': files}
        self.requests_mocker.get(url, json=response)

    def _new_fetch_assignment(self, course_id=TestExchange.course_id,
                              assignment_id=TestExchange.assignment_id,
                              student_id=TestExchange.student_id):
        retvalue = self._new_exchange_object(ExchangeFetchAssignment,
                                             course_id, assignment_id,
                                             student_id)

        class DummyAuthenticator(Authenticator):
            def has_access(self, student_id, course_id):
                return True
        retvalue.authenticator = DummyAuthenticator()
        retvalue.assignment_dir = str(self.course_dir.absolute())
        return retvalue

    @pytest.fixture(autouse=True)
    def init_fetch_assignment(self):
        self.fetch_assignment = self._new_fetch_assignment()
        self._mock_requests_fetch()

    def test_404(self):
        self.mock_404()
        try:
            self.fetch_assignment.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        try:
            self.fetch_assignment.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_no_course_id(self):
        self.fetch_assignment.coursedir.course_id = ''
        with pytest.raises(ExchangeError):
            self.fetch_assignment.start()

    def test_fetch(self):
        self.fetch_assignment.start()
        notebook_path = (self.course_dir / self.assignment_id
                         / (self.notebook_id + '.ipynb'))
        assert notebook_path.is_file()
        with open(self.files_path / 'test.ipynb', 'rb') as reference_file, \
                open(notebook_path, 'rb') as actual_file:
            assert actual_file.read() == reference_file.read()

    def test_refetch(self):
        self.fetch_assignment.start()
        with pytest.raises(ExchangeError):
            self.fetch_assignment.start()

    def test_replace(self):
        self.fetch_assignment.start()
        self.fetch_assignment.replace_missing_files = True
        self.fetch_assignment.start()

    def test_replace_no_overwrite(self):
        self.fetch_assignment.start()
        self.fetch_assignment.replace_missing_files = True
        # Make sure files aren't overwritten.
        notebook_path = self.course_dir / self.assignment_id /\
            (self.notebook_id + '.ipynb')
        shutil.copyfile(self.files_path / 'submitted-changed.ipynb',
                        notebook_path)
        with open(notebook_path, 'rb') as file:
            contents1 = file.read()
        self.fetch_assignment.start()
        with open(notebook_path, 'rb') as file:
            contents2 = file.read()
        assert contents1 == contents2

    def test_fetch_multiple_courses(self, tmpdir_factory):
        self.fetch_assignment.start()
        notebook_path = (self.course_dir / self.assignment_id
                         / (self.notebook_id + '.ipynb'))
        assert notebook_path.is_file()

        self.course_id = 'abc102'
        self.course_dir = Path(tmpdir_factory.mktemp(self.course_id))
        self.fetch_assignment = self._new_fetch_assignment(
            course_id=self.course_id)
        self._mock_requests_fetch()
        self.fetch_assignment.start()
        notebook_path = (self.course_dir / self.assignment_id
                         / (self.notebook_id + '.ipynb'))
        assert notebook_path.is_file()
