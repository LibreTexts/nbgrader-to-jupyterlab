import base64
from json import loads
import hashlib
from logging import getLogger
import os
from pathlib import Path
import re
import shutil

import pytest
from requests import PreparedRequest
import requests_mock as rq_mock

from .base import parse_body, TestExchange
from ....exchange.abc.exchange import ExchangeError
from ....exchange.ngshare import ExchangeSubmit


def get_files_path() -> Path:
    return Path(__file__).parent.parent / 'files'


class TestExchangeSubmit(TestExchange):
    timestamp = 'some timestamp'

    def _mock_request_assignment(self):
        '''
        Mocks ngshare's GET assignment with list_only, which responds with the
        assignment.
        '''
        url = '{}/assignment/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        pattern = re.compile(r'^{}\?.*list_only=true'.format(url))
        content = None
        with open(self.files_path / 'test.ipynb', 'rb') as notebook:
            content = notebook.read()
        md5 = hashlib.md5()
        md5.update(content)
        checksum = md5.hexdigest()
        files = [{'path': self.notebook_id + '.ipynb', 'checksum': checksum}]
        response = {'success': True, 'files': files}
        self.requests_mocker.get(pattern, json=response)

    def _mock_requests_submit(self, extra=False):
        ''' Mock's ngshare's POST submission, which verifies the request. '''
        url = '{}/submission/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        if extra:
            self.requests_mocker.post(url, json=self._post_submission_extra)
        else:
            self.requests_mocker.post(url, json=self._post_submission)

        self._mock_request_assignment()

    def _mock_requests_submit_2(self):
        '''
        Mocks ngshare's POST submission, which verifies the request for the
        second course.
        '''
        url = '{}/submission/{}/{}'.format(self.base_url, self.course_id2,
                                           self.assignment_id)
        self.requests_mocker.post(url, json=self._post_submission)

        self._mock_request_assignment()

    def _mock_requests_submit_size(self):
        '''
        Mocks ngshare's POST submission, which verifies the request has all and
        only the files which are within the file size limit.
        '''
        url = '{}/submission/{}/{}'.format(self.base_url, self.course_id,
                                           self.assignment_id)
        self.requests_mocker.post(url, json=self._post_submission_size)

        self._mock_request_assignment()

    def _new_submit(self, course_id=TestExchange.course_id,
                    assignment_id=TestExchange.assignment_id,
                    student_id=TestExchange.student_id):
        return self._new_exchange_object(ExchangeSubmit, course_id,
                                         assignment_id, student_id)

    def _post_submission(self, request: PreparedRequest, context):
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
        return {'success': True, 'timestamp': self.timestamp}

    def _post_submission_extra(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        try:
            files = loads(request['files'])
            assert len(files) == 2
            assert files[0]['path'] != files[1]['path']
            notebook_name1 = self.notebook_id + '.ipynb'
            notebook_name2 = self.notebook_id2 + '.ipynb'
            reference_file = self.files_path / 'test.ipynb'
            expected_content = None
            with open(reference_file, 'rb') as reference_file:
                expected_content = reference_file.read()
            for file_entry in files:
                assert (file_entry['path'] == notebook_name1 or
                        file_entry['path'] == notebook_name2)
                actual_content = base64.b64decode(files[0]['content'].encode())
                assert actual_content == expected_content
        except Exception as e:
            self.test_failed = True
            getLogger().error(e)
        self.test_completed = True
        return {'success': True, 'timestamp': self.timestamp}

    def _post_submission_size(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        try:
            files = loads(request['files'])
            paths = [x['path'] for x in files]
            assert 'small_file' in paths
            assert 'big_file' not in paths
        except Exception as e:
            self.test_failed = True
            getLogger().error(e)
        self.test_completed = True
        return {'success': True, 'timestamp': self.timestamp}

    def _prepare_submission(self, course_dir,
                            assignment_id=TestExchange.assignment_id,
                            notebook_id=TestExchange.notebook_id):
        course_dir = Path(course_dir).absolute()
        assignment_dir = course_dir / assignment_id
        os.makedirs(assignment_dir)
        shutil.copyfile(self.files_path / 'test.ipynb',
                        assignment_dir / (notebook_id + '.ipynb'))

    @pytest.fixture(autouse=True)
    def init_submit(self):
        self._prepare_submission(self.course_dir)
        self.submit = self._new_submit()
        os.chdir(self.course_dir)

    def test_404(self):
        self.mock_404()
        try:
            self.submit.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        try:
            self.submit.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_no_course_id(self):
        """Does submitting without a course id thrown an error?"""
        self._mock_requests_submit()
        self.submit.coursedir.course_id = ''
        with pytest.raises(ExchangeError):
            self.submit.start()

    def test_submit(self):
        self._mock_requests_submit()
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed

        # Verify cache.
        cache_filename, = os.listdir(self.cache_dir / self.course_id)
        cache_username, cache_assignment, cache_timestamp1 = cache_filename\
            .split("+")[:3]
        assert cache_username == self.student_id
        assert cache_assignment == self.assignment_id
        assert cache_timestamp1 == self.timestamp
        assert Path(self.cache_dir / self.course_id / cache_filename
                    / (self.notebook_id + '.ipynb')).is_file()
        assert Path(self.cache_dir / self.course_id / cache_filename /
                    'timestamp.txt').is_file()
        with open(self.cache_dir / self.course_id / cache_filename
                  / 'timestamp.txt', 'r') as fh:
            assert fh.read() == cache_timestamp1

        # Submit again.
        self.test_failed = False
        self.test_completed = False
        self.timestamp += '_1'
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed

        # Verify cache.
        assert len(os.listdir(self.cache_dir / self.course_id)) == 2
        cache_filename = sorted(os.listdir(self.cache_dir / self.course_id))[1]
        cache_username, cache_assignment, cache_timestamp2 = cache_filename\
            .split("+")[:3]
        assert cache_username == self.student_id
        assert cache_assignment == self.assignment_id
        assert cache_timestamp2 == self.timestamp
        assert Path(self.cache_dir / self.course_id / cache_filename
                    / (self.notebook_id + '.ipynb')).is_file()
        assert Path(self.cache_dir / self.course_id / cache_filename /
                    'timestamp.txt').is_file()
        with open(self.cache_dir / self.course_id / cache_filename
                  / 'timestamp.txt', 'r') as fh:
            assert fh.read() == cache_timestamp2

    def test_submit_extra(self):
        # Add extra notebook.
        self._mock_requests_submit(extra=True)
        self.notebook_id2 = 'p2'
        shutil.copyfile(get_files_path() / 'test.ipynb', self.course_dir /
                        self.assignment_id / (self.notebook_id2 + '.ipynb'))
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed

    def test_submit_extra_strict(self):
        # Add extra notebook and enable strict flag.
        self._mock_requests_submit(extra=True)
        self.notebook_id2 = 'p2'
        shutil.copyfile(get_files_path() / 'test.ipynb', self.course_dir /
                        self.assignment_id / (self.notebook_id2 + '.ipynb'))
        self.submit.strict = True
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed

    def test_submit_missing(self):
        # Missing notebook.
        self._mock_requests_submit()
        self.notebook_id2 = 'p2'
        shutil.move(self.course_dir / self.assignment_id
                    / (self.notebook_id + '.ipynb'), self.course_dir
                    / self.assignment_id / (self.notebook_id2 + '.ipynb'))
        self.submit.start()

    def test_submit_missing_strict(self):
        # Missing notebook and enable strict flag.
        self._mock_requests_submit()
        self.notebook_id2 = 'p2'
        shutil.move(self.course_dir / self.assignment_id
                    / (self.notebook_id + '.ipynb'), self.course_dir
                    / self.assignment_id / (self.notebook_id2 + '.ipynb'))
        self.submit.strict = True
        with pytest.raises(ExchangeError):
            self.submit.start()

    def test_submit_multiple_courses(self, tmpdir_factory):
        self._mock_requests_submit()
        self.course_id2 = 'abc102'
        course_dir2 = Path(tmpdir_factory.mktemp(self.course_id2)).absolute()
        self._prepare_submission(course_dir2)

        # Submit to first course.
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed
        assert len(os.listdir(self.cache_dir / self.course_id)) == 1
        assert not Path(self.cache_dir / self.course_id2).exists()

        # Submit to second course.
        self.requests_mocker.register_uri(rq_mock.ANY, rq_mock.ANY,
                                          text=self._mock_all)
        self._mock_requests_submit_2()
        self.course_dir = course_dir2
        self.submit = self._new_submit(course_id=self.course_id2)
        os.chdir(self.course_dir)
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed
        assert len(os.listdir(self.cache_dir / self.course_id)) == 1
        assert len(os.listdir(self.cache_dir / self.course_id2)) == 1

    def test_submit_exclude(self):
        # Create a file that should be ignored.
        self._mock_requests_submit()
        (self.course_dir / self.assignment_id / 'foo.pyc').touch()
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed

    def test_submit_include(self):
        # Create a file that should be ignored.
        self._mock_requests_submit()
        (self.course_dir / self.assignment_id / 'foo.txt').touch()
        self.submit.coursedir.include = ['*.ipynb']
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed

    def test_submit_file_size(self):
        # Create two files around a 2 KB size limit.
        self._mock_requests_submit_size()
        small_file = (self.course_dir / self.assignment_id / 'small_file')
        big_file = (self.course_dir / self.assignment_id / 'big_file')
        small_file.touch()
        big_file.touch()
        with open(small_file, 'w') as small, open(big_file, 'w') as big:
            small.write('x' * 2000)
            big.write('x' * 2001)
        self.submit.coursedir.max_file_size = 2
        self.submit.start()
        assert not self.test_failed
        assert self.test_completed
