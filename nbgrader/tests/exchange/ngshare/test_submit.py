import base64
import datetime
import os
from pathlib import Path
import shutil

import pytest

from base import TestExchange
from nbgrader.exchange.abc.exchange import ExchangeError
from nbgrader.exchange.ngshare import ExchangeSubmit
from nbgrader.utils import parse_utc
from ngshare_mock import Assignment, Course, File


def get_files_path() -> Path:
    return Path(__file__).parent.parent / 'files'


class TestExchangeSubmit(TestExchange):
    def _db_get_submissions(self, course_id=TestExchange.course_id,
                            assignment_id=TestExchange.assignment_id):
        return self.mock_ngshare.courses[course_id].assignments[assignment_id]\
            .submissions

    def _new_submit(self, course_id=TestExchange.course_id,
                    assignment_id=TestExchange.assignment_id,
                    student_id=TestExchange.student_id):
        return self._new_exchange_object(ExchangeSubmit, course_id,
                                         assignment_id, student_id)

    def _populate_ngshare(self, course_id=TestExchange.course_id):
        files = [File(path=(self.notebook_id + '.ipynb'))]
        assignment = Assignment(files=files)
        course = Course()
        course.assignments[self.assignment_id] = assignment
        self.mock_ngshare.courses[course_id] = course

    def _prepare_submission(self, course_dir,
                            assignment_id=TestExchange.assignment_id,
                            notebook_id=TestExchange.notebook_id):
        course_dir = Path(course_dir).absolute()
        assignment_dir = course_dir / assignment_id
        os.makedirs(assignment_dir)
        shutil.copyfile(self.files_path / 'test.ipynb',
                        assignment_dir / (notebook_id + '.ipynb'))

    def test_no_course_id(self):
        """Does submitting without a course id thrown an error?"""
        self.submit.coursedir.course_id = ''
        with pytest.raises(ExchangeError):
            self.submit.start()

    @pytest.fixture(autouse=True)
    def init_submit(self):
        self._prepare_submission(self.course_dir)
        self.submit = self._new_submit()
        self._populate_ngshare()
        os.chdir(self.course_dir)

    def test_submit(self):
        now = datetime.datetime.utcnow()
        self.submit.start()

        # Verify ngshare.
        db_submissions = self.mock_ngshare.courses[self.course_id]\
            .assignments[self.assignment_id].submissions
        assert len(db_submissions) == 1
        db_submission = db_submissions[0]
        assert db_submission.student == self.student_id
        assert parse_utc(db_submission.timestamp) > now
        db_files = db_submission.files
        assert len(db_files) == 1
        db_file = db_files[0]
        assert db_file.path == self.notebook_id + '.ipynb'
        expected_content = None
        with open(self.files_path / 'test.ipynb', 'rb') as nb_file:
            expected_content = nb_file.read()
        assert base64.b64decode(db_file.content.encode()) == expected_content

        # Verify cache.
        cache_filename, = os.listdir(self.cache_dir / self.course_id)
        cache_username, cache_assignment, cache_timestamp1 = cache_filename\
            .split("+")[:3]
        assert cache_username == self.student_id
        assert cache_assignment == self.assignment_id
        assert parse_utc(cache_timestamp1) > now
        assert Path(self.cache_dir / self.course_id / cache_filename
                    / (self.notebook_id + '.ipynb')).is_file()
        assert Path(self.cache_dir / self.course_id / cache_filename /
                    'timestamp.txt').is_file()
        with open(self.cache_dir / self.course_id / cache_filename
                  / 'timestamp.txt', 'r') as fh:
            assert fh.read() == cache_timestamp1

        # Submit again.
        self.submit.username = self.student_id
        now = datetime.datetime.utcnow()
        self.submit.start()

        # Verify ngshare.
        db_submissions = self.mock_ngshare.courses[self.course_id]\
            .assignments[self.assignment_id].submissions
        assert len(db_submissions) == 2
        db_submission = db_submissions[1]
        assert db_submission.student == self.student_id
        assert parse_utc(db_submission.timestamp) > now
        db_files = db_submission.files
        assert len(db_files) == 1
        db_file = db_files[0]
        assert db_file.path == self.notebook_id + '.ipynb'
        expected_content = None
        with open(self.files_path / 'test.ipynb', 'rb') as nb_file:
            expected_content = nb_file.read()
        assert base64.b64decode(db_file.content.encode()) == expected_content

        # Verify cache.
        assert len(os.listdir(self.cache_dir / self.course_id)) == 2
        cache_filename = sorted(os.listdir(self.cache_dir / self.course_id))[1]
        cache_username, cache_assignment, cache_timestamp2 = cache_filename\
            .split("+")[:3]
        assert cache_username == self.student_id
        assert cache_assignment == self.assignment_id
        assert parse_utc(cache_timestamp2) > parse_utc(cache_timestamp1)
        assert Path(self.cache_dir / self.course_id / cache_filename
                    / (self.notebook_id + '.ipynb')).is_file()
        assert Path(self.cache_dir / self.course_id / cache_filename /
                    'timestamp.txt').is_file()
        with open(self.cache_dir / self.course_id / cache_filename
                  / 'timestamp.txt', 'r') as fh:
            assert fh.read() == cache_timestamp2

    def test_submit_extra(self):
        # Add extra notebook.
        shutil.copyfile(get_files_path() / 'test.ipynb', self.course_dir /
                        self.assignment_id / 'p2.ipynb')
        self.submit.start()

    def test_submit_extra_strict(self):
        # Add extra notebook and enable strict flag.
        shutil.copyfile(get_files_path() / 'test.ipynb', self.course_dir /
                        self.assignment_id / 'p2.ipynb')
        self.submit.strict = True
        self.submit.start()

    def test_submit_missing(self):
        # Missing notebook.
        shutil.move(self.course_dir / self.assignment_id
                    / (self.notebook_id + '.ipynb'), self.course_dir
                    / self.assignment_id / 'p2.ipynb')
        self.submit.start()

    def test_submit_missing_strict(self):
        # Missing notebook and enable strict flag.
        shutil.move(self.course_dir / self.assignment_id
                    / (self.notebook_id + '.ipynb'), self.course_dir
                    / self.assignment_id / 'p2.ipynb')
        self.submit.strict = True
        with pytest.raises(ExchangeError):
            self.submit.start()

    def test_submit_multiple_courses(self, tmpdir_factory):
        course_id_alt = 'abc102'
        course_dir_alt = Path(tmpdir_factory.mktemp(course_id_alt)).absolute()
        self._prepare_submission(course_dir_alt)
        self._populate_ngshare(course_id=course_id_alt)

        # Submit to first course.
        self.submit.start()

        submissions1 = self._db_get_submissions()
        submissions2 = self._db_get_submissions(course_id=course_id_alt)
        assert len(submissions1) == 1
        assert len(submissions2) == 0

        assert len(os.listdir(self.cache_dir / self.course_id)) == 1
        assert not Path(self.cache_dir / course_id_alt).exists()

        # Submit to second course.
        self.course_dir = course_dir_alt
        self.submit = self._new_submit(course_id=course_id_alt)
        os.chdir(self.course_dir)
        self.submit.start()

        submissions1 = self._db_get_submissions()
        submissions2 = self._db_get_submissions(course_id=course_id_alt)
        assert len(submissions1) == 1
        assert len(submissions2) == 1

        assert len(os.listdir(self.cache_dir / self.course_id)) == 1
        assert len(os.listdir(self.cache_dir / course_id_alt)) == 1

    def test_submit_exclude(self):
        # Create a file that should be ignored.
        (self.course_dir / self.assignment_id / 'foo.pyc').touch()
        self.submit.start()

        submission_files = self._db_get_submissions()[0].files
        assert len(submission_files) == 1
        assert submission_files[0].path == self.notebook_id + '.ipynb'

    def test_submit_include(self):
        # Create a file that should be ignored.
        (self.course_dir / self.assignment_id / 'foo.txt').touch()
        self.submit.coursedir.include = ['*.ipynb']
        self.submit.start()

        submission_files = self._db_get_submissions()[0].files
        assert len(submission_files) == 1
        assert submission_files[0].path == self.notebook_id + '.ipynb'

    def test_submit_file_size(self):
        # Create two files around a 2 KB size limit.
        small_file = (self.course_dir / self.assignment_id / 'small_file')
        big_file = (self.course_dir / self.assignment_id / 'big_file')
        small_file.touch()
        big_file.touch()
        with open(small_file, 'w') as small, open(big_file, 'w') as big:
            small.write('x' * 2000)
            big.write('x' * 2001)
        self.submit.coursedir.max_file_size = 2
        self.submit.start()

        submission_filenames = [x.path for x in
                                self._db_get_submissions()[0].files]
        assert 'small_file' in submission_filenames
        assert 'big_file' not in submission_filenames
