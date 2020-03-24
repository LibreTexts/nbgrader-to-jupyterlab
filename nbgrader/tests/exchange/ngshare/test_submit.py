import base64
import datetime
import os
from pathlib import Path
import shutil

import pytest

from base import TestExchange
from nbgrader.coursedir import CourseDirectory
from nbgrader.exchange.abc.exchange import ExchangeError
from nbgrader.exchange.ngshare import ExchangeSubmit
from nbgrader.utils import parse_utc
from ngshare_mock import Assignment, Course, File


course_id = 'abc101'
assignment_id = 'ps1'
student_id = 'student_1'
notebook_id = 'p1'


def get_files_path() -> Path:
    return Path(__file__).parent.parent / 'files'


class TestExchangeSubmit(TestExchange):
    def _db_get_submissions(self, course_id=course_id,
                            assignment_id=assignment_id):
        return self.mock_ngshare.courses[course_id].assignments[assignment_id]\
            .submissions

    def _init_cache_dir(self, tmpdir_factory):
        return Path(tmpdir_factory.mktemp('nbgrader_cache')).absolute()

    def _init_course_dir(self, course_id, tmpdir_factory):
        return Path(tmpdir_factory.mktemp(course_id)).absolute()

    def _new_submit(self, cache_dir, course_dir, course_id=course_id,
                    assignment_id=assignment_id, student_id=student_id):
        ExchangeSubmit.cache = str(cache_dir)
        coursedir = CourseDirectory()
        coursedir.root = str(course_dir)
        coursedir.course_id = course_id
        coursedir.assignment_id = assignment_id
        submit = ExchangeSubmit(coursedir=coursedir)
        submit.username = student_id
        return submit

    def _populate_ngshare(self, course_id=course_id):
        files = [File(path=(notebook_id + '.ipynb'))]
        assignment = Assignment(files=files)
        course = Course()
        course.assignments[assignment_id] = assignment
        self.mock_ngshare.courses[course_id] = course

    def _prepare_submission(self, assignment, course_dir, notebook_id):
        course_dir = Path(course_dir).absolute()
        assignment_dir = course_dir / assignment
        files_dir = Path(__file__).parent.parent / 'files'
        os.makedirs(assignment_dir)
        shutil.copyfile(files_dir / 'test.ipynb',
                        assignment_dir / (notebook_id + '.ipynb'))

    def test_no_course_id(self, tmpdir_factory):
        """Does submitting without a course id thrown an error?"""
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir, course_id='')

        with pytest.raises(ExchangeError):
            submit.start()

    def test_submit(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        files_dir = get_files_path()
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        now = datetime.datetime.utcnow()
        submit.start()

        # Verify ngshare.
        db_submissions = self.mock_ngshare.courses[course_id]\
            .assignments[assignment_id].submissions
        assert len(db_submissions) == 1
        db_submission = db_submissions[0]
        assert db_submission.student == student_id
        assert parse_utc(db_submission.timestamp) > now
        db_files = db_submission.files
        assert len(db_files) == 1
        db_file = db_files[0]
        assert db_file.path == notebook_id + '.ipynb'
        expected_content = None
        with open(files_dir / 'test.ipynb', 'rb') as nb_file:
            expected_content = nb_file.read()
        assert base64.b64decode(db_file.content.encode()) == expected_content

        # Verify cache.
        cache_filename, = os.listdir(cache_dir / course_id)
        cache_username, cache_assignment, cache_timestamp1 = cache_filename\
            .split("+")[:3]
        assert cache_username == student_id
        assert cache_assignment == assignment_id
        assert parse_utc(cache_timestamp1) > now
        assert Path(cache_dir / course_id / cache_filename / (notebook_id +
                    '.ipynb')).is_file()
        assert Path(cache_dir / course_id / cache_filename /
                    'timestamp.txt').is_file()
        with open(cache_dir / course_id / cache_filename / 'timestamp.txt',
                  'r') as fh:
            assert fh.read() == cache_timestamp1

        # Submit again.
        submit.username = student_id
        now = datetime.datetime.utcnow()
        submit.start()

        # Verify ngshare.
        db_submissions = self.mock_ngshare.courses[course_id]\
            .assignments[assignment_id].submissions
        assert len(db_submissions) == 2
        db_submission = db_submissions[1]
        assert db_submission.student == student_id
        assert parse_utc(db_submission.timestamp) > now
        db_files = db_submission.files
        assert len(db_files) == 1
        db_file = db_files[0]
        assert db_file.path == notebook_id + '.ipynb'
        expected_content = None
        with open(files_dir / 'test.ipynb', 'rb') as nb_file:
            expected_content = nb_file.read()
        assert base64.b64decode(db_file.content.encode()) == expected_content

        # Verify cache.
        assert len(os.listdir(cache_dir / course_id)) == 2
        cache_filename = sorted(os.listdir(cache_dir / course_id))[1]
        cache_username, cache_assignment, cache_timestamp2 = cache_filename\
            .split("+")[:3]
        assert cache_username == student_id
        assert cache_assignment == assignment_id
        assert parse_utc(cache_timestamp2) > parse_utc(cache_timestamp1)
        assert Path(cache_dir / course_id / cache_filename / (notebook_id +
                    '.ipynb')).is_file()
        assert Path(cache_dir / course_id / cache_filename /
                    'timestamp.txt').is_file()
        with open(cache_dir / course_id / cache_filename / 'timestamp.txt',
                  'r') as fh:
            assert fh.read() == cache_timestamp2

    def test_submit_extra(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        # Add extra notebook.
        shutil.copyfile(get_files_path() / 'test.ipynb', course_dir /
                        assignment_id / 'p2.ipynb')

        submit.start()

    def test_submit_extra_strict(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        # Add extra notebook and enable strict flag.
        shutil.copyfile(get_files_path() / 'test.ipynb', course_dir /
                        assignment_id / 'p2.ipynb')
        submit.strict = True

        submit.start()

    def test_submit_missing(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        # Missing notebook.
        shutil.move(course_dir / assignment_id / (notebook_id + '.ipynb'),
                    course_dir / assignment_id / 'p2.ipynb')

        submit.start()

    def test_submit_missing_strict(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        # Missing notebook and enable strict flag.
        shutil.move(course_dir / assignment_id / (notebook_id + '.ipynb'),
                    course_dir / assignment_id / 'p2.ipynb')
        submit.strict = True

        with pytest.raises(ExchangeError):
            submit.start()

    def test_submit_multiple_courses(self, tmpdir_factory):
        course_id_alt = 'abc102'
        course_dir1 = self._init_course_dir(course_id, tmpdir_factory)
        course_dir2 = self._init_course_dir(course_id_alt, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir1, notebook_id)
        self._prepare_submission(assignment_id, course_dir2, notebook_id)
        self._populate_ngshare()
        self._populate_ngshare(course_id=course_id_alt)

        # Submit to first course.
        submit = self._new_submit(cache_dir, course_dir1)
        os.chdir(course_dir1)
        submit.start()

        submissions1 = self._db_get_submissions()
        submissions2 = self._db_get_submissions(course_id=course_id_alt)
        assert len(submissions1) == 1
        assert len(submissions2) == 0

        assert len(os.listdir(cache_dir / course_id)) == 1
        assert not Path(cache_dir / course_id_alt).exists()

        # Submit to second course.
        submit = self._new_submit(cache_dir, course_dir2,
                                  course_id=course_id_alt)
        os.chdir(course_dir2)
        submit.start()

        submissions1 = self._db_get_submissions()
        submissions2 = self._db_get_submissions(course_id=course_id_alt)
        assert len(submissions1) == 1
        assert len(submissions2) == 1

        assert len(os.listdir(cache_dir / course_id)) == 1
        assert len(os.listdir(cache_dir / course_id_alt)) == 1

    def test_submit_exclude(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        # Create a file that should be ignored.
        (course_dir / assignment_id / 'foo.pyc').touch()
        submit.start()

        submission_files = self._db_get_submissions()[0].files
        assert len(submission_files) == 1
        assert submission_files[0].path == notebook_id + '.ipynb'

    def test_submit_include(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        # Create a file that should be ignored.
        (course_dir / assignment_id / 'foo.txt').touch()
        submit.coursedir.include = ['*.ipynb']
        submit.start()

        submission_files = self._db_get_submissions()[0].files
        assert len(submission_files) == 1
        assert submission_files[0].path == notebook_id + '.ipynb'

    def test_submit_file_size(self, tmpdir_factory):
        course_dir = self._init_course_dir(course_id, tmpdir_factory)
        cache_dir = self._init_cache_dir(tmpdir_factory)
        self._prepare_submission(assignment_id, course_dir, notebook_id)
        self._populate_ngshare()
        submit = self._new_submit(cache_dir, course_dir)
        os.chdir(course_dir)

        # Create two files around a 2 KB size limit.
        small_file = (course_dir / assignment_id / 'small_file')
        big_file = (course_dir / assignment_id / 'big_file')
        small_file.touch()
        big_file.touch()
        with open(small_file, 'w') as small, open(big_file, 'w') as big:
            small.write('x' * 2000)
            big.write('x' * 2001)
        submit.coursedir.max_file_size = 2
        submit.start()

        submission_filenames = [x.path for x in
                                self._db_get_submissions()[0].files]
        assert 'small_file' in submission_filenames
        assert 'big_file' not in submission_filenames
