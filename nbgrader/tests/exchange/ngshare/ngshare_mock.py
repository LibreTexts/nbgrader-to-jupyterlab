import base64
import datetime
from dateutil.tz import gettz
import hashlib
import json
import re
import typing
import urllib

import requests

from nbgrader.exchange.ngshare.exchange import Exchange


re_name = '[^/?]+'
re_query = r'(\?[^#]*)?'
re_course_id = '(?P<course_id>{})'.format(re_name)
re_assignment_id = '(?P<assignment_id>{})'.format(re_name)
re_student_id = '(?P<student_id>{})'.format(re_name)

url_suffix_get_assignment = '/assignment/{}/{}{}'.format(
    re_course_id, re_assignment_id, re_query)
url_suffix_post_submission = '/submission/{}/{}{}'.format(
    re_course_id, re_assignment_id, re_query)
# TODO: Other url suffixes.


def _generate_timestamp():
    tz = gettz(Exchange.timezone.default_value)
    timestamp_format = Exchange.timestamp_format.default_value
    timestamp = datetime.datetime.now(tz).strftime(timestamp_format)
    return timestamp


def _parse_body(body: str):
    # https://stackoverflow.com/questions/48018622/how-can-see-the-request-data#51052385
    return dict(urllib.parse.parse_qsl(body))


class File:
    def __init__(self, path: str = '', content: str = ''):
        self.path = path
        self.content = content

    @property
    def checksum(self):
        md5 = hashlib.md5()
        md5.update(base64.b64decode(self.content.encode()))
        return md5.hexdigest()

    def to_dict(self):
        return {'path': self.path, 'content': self.content, 'checksum':
                self.checksum}


class Submission:
    def __init__(self, student: str = '', files: typing.List[File] = None):
        self.student = student
        self.files = [] if files is None else files
        self.timestamp = _generate_timestamp()


class Assignment:
    def __init__(self, files: typing.List[File] = None, submissions:
                 typing.List[Submission] = None):
        self.files = [] if files is None else files
        self.submissions = [] if submissions is None else submissions

    def to_list(self):
        return [file.to_dict() for file in self.files]


class Course:
    def __init__(self, instructors: typing.List[str] = None,
                 students: typing.List[str] = None,
                 assignments: typing.Dict[str, Assignment] = None):
        self.instructors = [] if instructors is None else instructors
        self.students = [] if students is None else students
        self.assignments = {} if assignments is None else assignments


class MockNgshare():
    def __init__(self, base_url: str = '',
                 courses: typing.Dict[str, Course] = None):
        self.courses = {} if courses is None else courses
        self.base_url = base_url

    def mock_get_assignment(self, request: requests.PreparedRequest, context):
        pattern = re.compile('^{}{}$'.format(self.base_url,
                                             url_suffix_get_assignment))
        match = pattern.match(request.url)
        course_id = match.group('course_id')
        assignment_id = match.group('assignment_id')

        if course_id not in self.courses:
            return {'success': False, 'message': 'Course not found'}
        if assignment_id not in self.courses[course_id].assignments:
            return {'success': False, 'message': 'Assignment not found'}
        assignment = self.courses[course_id].assignments[assignment_id]
        retval = {'success': True, 'files': assignment.to_list()}
        return retval

    def mock_post_submission(self, request: requests.PreparedRequest, context):
        pattern = re.compile('^{}{}$'.format(self.base_url,
                                             url_suffix_post_submission))
        match = pattern.match(request.url)
        course_id = match.group('course_id')
        assignment_id = match.group('assignment_id')

        request_json = _parse_body(request.body)
        if 'files' not in request_json:
            return {'success': False, 'message': 'Please supply files'}
        files = []
        for file in json.loads(request_json['files']):
            files.append(File(path=file['path'], content=file['content']))
        submission = Submission(student=request_json['user'], files=files)
        self.courses[course_id].assignments[assignment_id].submissions\
            .append(submission)
        return {'success': True, 'timestamp': submission.timestamp}

    # TODO: Mock other responses.
