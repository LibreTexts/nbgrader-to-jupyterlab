import os
import glob
import shutil
import re
import hashlib
import requests

from nbgrader.exchange.abc import ExchangeList as ABCExchangeList
from .exchange import Exchange


def _checksum(path):
    m = hashlib.md5()
    m.update(open(path, 'rb').read())
    return m.hexdigest()


class ExchangeList(Exchange, ABCExchangeList):

    def _get_assignments(self, course_ids):
        """
        Returns a list of assignments. Each assignment is a dictionary
        containing the course_id and assignment_id.

        ``course_ids`` - A list of course IDs.
        """
        assignments = []
        server_error = False
        for course_id in course_ids:
            url = self.ngshare_url + '/api/assignments/{}'.format(course_id)
            params = {'user': self.username}
            # TODO: Timeout.
            try:
                response = requests.get(url, params=params)
            except:
                server_error = True
                continue

            if response.status_code != requests.codes.ok:
                server_error = True
                continue
            if not response.json()['success']:
                continue

            assignments += [{'course_id': course_id, 'assignment_id': x}
                            for x in response.json()['assignments']]

        if server_error:
            self.log.warn('An error occurred querying the server for '
                          'assignments.')

        return assignments

    def _get_courses(self):
        """
        Returns a list of course_ids.
        """
        url = self.ngshare_url + '/api/courses'
        params = {'user': self.username}

        # TODO: Timeout.
        try:
            response = requests.get(url, params=params)
        except:
            self.log.warn('An error occurred querying the server for courses.')
            return []

        if response.status_code != requests.codes.ok:
            self.log.warn('An error occurred querying the server for courses.')
            return []
        if not response.json()['success']:
            return []

        return response.json()['courses']

    def _get_notebooks(self, course_id, assignment_id):
        """
        Returns a list of notebook_ids from the assignment.
        """
        url = self.ngshare_url + '/api/assignment/{}/{}'.format(course_id,
                                                                assignment_id)
        params = {'list_only': True, 'user': self.username}

        # TODO: Timeout.
        try:
            response = requests.get(url, params)
        except:
            self.log.warn('An error occurred querying the server for notebooks'
                          '.')
            return []

        if response.status_code != requests.codes.ok:
            self.log.warn('An error occurred querying the server for courses.')
            return []
        if not response.json()['success']:
            return []

        return [os.path.splitext(os.path.split(x['path'])[1])[0] for x in
                response.json()['files']]

    def _get_submissions(self, assignments, student_id=None):
        """
        Returns a list of submissions. Each submission is a dictionary
        containing the "course_id", "assignment_id", "student_id", "timestamp"
        and a list of "notebooks". Each notebook is a dictionary containing a
        "notebook_id" and "feedback_checksum".

        ``assignments`` - A list of dictionaries containing "course_id" and
        "assignment_id".
        ``student_id`` - Used to specify a specific student's submissions to
        get. If None, submissions from all students are fetched if permitted.
        """
        submissions = []
        server_error = False
        for assignment in assignments:
            course_id = assignment['course_id']
            assignment_id = assignment['assignment_id']
            url = self.ngshare_url + '/api/submissions/{}/{}'.format(
                    course_id, assignment_id)
            params = {'user': self.username}

            if student_id is not None:
                url += '/' + student_id

            try:
                response = requests.get(url, params=params)
            except:
                server_error = True
                continue

            if response.status_code != requests.codes.ok:
                server_error = True
                continue

            response_json = response.json()
            if not response_json['success']:
                continue

            for submission in response_json['submissions']:
                submissions.append({
                        'course_id': course_id,
                        'assignment_id': assignment_id,
                        'student_id': submission['student_id'] if student_id
                        is None else student_id,
                        'timestamp': submission['timestamp'],
                        #TODO 'notebooks': submission['notebooks']})
                        'notebooks': []})

        if server_error:
            self.log.warn('An error occurred querying the server for '
                          'submissions.')

        return submissions

    def init_src(self):
        pass

    def init_dest(self):
        course_id = self.coursedir.course_id if self.coursedir.course_id else '*'
        assignment_id = self.coursedir.assignment_id if self.coursedir.assignment_id else '*'
        student_id = self.coursedir.student_id if self.coursedir.student_id else '*'

        self.ngshare_url = 'http://172.17.0.1:11111' # TODO: Find server address.
        self.username = os.environ['USER'] # TODO: Get from JupyterHub.
        if course_id == '*':
            courses = self._get_courses()
        else:
            courses = [course_id]
        if assignment_id == '*':
            assignments = self._get_assignments(courses)
        else:
            assignments = [{'course_id': course,
                            'assignment_id': assignment_id}
                           for course in courses]

        if self.inbound:
            if student_id == '*':
                student_id = None
            self.assignments = self._get_submissions(assignments, student_id)
        elif self.cached:
            pattern = os.path.join(self.cache, course_id, '{}+{}+*'.format(student_id, assignment_id))
            self.assignments = sorted(glob.glob(pattern))
            if student_id == '*':
                student_id = None
            self.submissions = self._get_submissions(assignments, student_id)
        else:
            self.assignments = assignments

    def parse_assignment(self, assignment):
        if self.inbound:
            return {'course_id': assignment['course_id'],
                    'student_id': assignment['student_id'],
                    'assignment_id': assignment['assignment_id'],
                    'timestamp': assignment['timestamp']}
        elif self.cached:
            regexp = r".*/(?P<course_id>.*)/(?P<student_id>.*)\+(?P<assignment_id>.*)\+(?P<timestamp>.*)"
        else:
            return assignment

        m = re.match(regexp, assignment)
        if m is None:
            raise RuntimeError("Could not match '%s' with regexp '%s'", assignment, regexp)
        return m.groupdict()

    def format_inbound_assignment(self, info):
        msg = "{course_id} {student_id} {assignment_id} {timestamp}".format(**info)
        if info['status'] == 'submitted':
            if info['has_local_feedback'] and not info['feedback_updated']:
                msg += " (feedback already fetched)"
            elif info['has_exchange_feedback']:
                msg += " (feedback ready to be fetched)"
            else:
                msg += " (no feedback available)"
        return msg

    def format_outbound_assignment(self, info):
        msg = "{course_id} {assignment_id}".format(**info)
        if os.path.exists(info['assignment_id']):
            msg += " (already downloaded)"
        return msg

    def copy_files(self):
        pass

    def parse_assignments(self):
        if self.coursedir.student_id:
            courses = self.authenticator.get_student_courses(self.coursedir.student_id)
        else:
            courses = None

        assignments = []
        for assignment in self.assignments:
            info = self.parse_assignment(assignment)
            if courses is not None and info['course_id'] not in courses:
                continue

            if self.path_includes_course:
                assignment_dir = os.path.join(self.assignment_dir, info['course_id'], info['assignment_id'])
            else:
                assignment_dir = os.path.join(self.assignment_dir, info['assignment_id'])

            if self.inbound or self.cached:
                info['status'] = 'submitted'
                if self.cached:
                    info['path'] = assignment
            elif os.path.exists(assignment_dir):
                info['status'] = 'fetched'
                info['path'] = os.path.abspath(assignment_dir)
            else:
                info['status'] = 'released'

            if self.remove:
                info['status'] = 'removed'

            if self.cached:
                notebooks = sorted(glob.glob(os.path.join(info['path'], '*.ipynb')))
            elif self.inbound:
                notebooks = sorted(assignment['notebooks'])
            else:
                notebooks = self._get_notebooks(info['course_id'],
                                                info['assignment_id'])

            if not notebooks:
                self.log.warning('No notebooks found for assignment "{}" in '
                                 'course "{}"' .format(info['assignment_id'],
                                                       info['course_id']))

            if self.cached:
                submissions = [x['notebooks'] for x in self.submissions if
                               x['timestamp'] == info['timestamp']
                               and x['student_id'] == info['student_id']
                               and x['assignment_id'] == info['assignment_id']
                               and x['course_id'] == info['course_id']
                               ]

            info['notebooks'] = []
            for notebook in notebooks:
                if self.cached:
                    nb_info = {
                        'notebook_id': os.path.splitext(os.path.split(notebook)[1])[0],
                        'path': os.path.abspath(notebook)
                    }
                elif self.inbound:
                    nb_info = {'notebook_id': notebook['notebook_id']}
                else:
                    nb_info = {'notebook_id': notebook}
                if info['status'] != 'submitted':
                    info['notebooks'].append(nb_info)
                    continue

                nb_info['has_local_feedback'] = False
                nb_info['has_exchange_feedback'] = False
                nb_info['local_feedback_path'] = None
                nb_info['feedback_updated'] = False

                # Check whether feedback has been fetched already.
                local_feedback_dir = os.path.join(
                    assignment_dir, 'feedback', info['timestamp'])
                local_feedback_path = os.path.join(
                    local_feedback_dir, '{0}.html'.format(nb_info['notebook_id']))
                has_local_feedback = os.path.isfile(local_feedback_path)
                if has_local_feedback:
                    local_feedback_checksum = _checksum(local_feedback_path)
                else:
                    local_feedback_checksum = None

                # Also look to see if there is feedback available to fetch.
                if self.cached:
                    has_exchange_feedback = False
                    exchange_feedback_checksum = None
                    for submission_notebook in submissions:
                        if submission_notebook['notebook_id'] == info[
                                'notebook_id']:
                            has_exchange_feedback = True
                            exchange_feedback_checksum = submission_notebook[
                                'feedback_checksum']
                            break
                else:  # self.inbound
                    has_exchange_feedback = notebook['feedback_checksum']\
                        is not None and notebook['feedback_checksum'] != ''
                    if has_exchange_feedback:
                        exchange_feedback_checksum = notebook[
                            'feedback_checksum']
                    else:
                        exchange_feedback_checksum = None

                nb_info['has_local_feedback'] = has_local_feedback
                nb_info['has_exchange_feedback'] = has_exchange_feedback
                if has_local_feedback:
                    nb_info['local_feedback_path'] = local_feedback_path
                if has_local_feedback and has_exchange_feedback:
                    nb_info['feedback_updated'] = exchange_feedback_checksum != local_feedback_checksum
                info['notebooks'].append(nb_info)

            if info['status'] == 'submitted':
                if info['notebooks']:
                    has_local_feedback = all([nb['has_local_feedback'] for nb in info['notebooks']])
                    has_exchange_feedback = all([nb['has_exchange_feedback'] for nb in info['notebooks']])
                    feedback_updated = any([nb['feedback_updated'] for nb in info['notebooks']])
                else:
                    has_local_feedback = False
                    has_exchange_feedback = False
                    feedback_updated = False

                info['has_local_feedback'] = has_local_feedback
                info['has_exchange_feedback'] = has_exchange_feedback
                info['feedback_updated'] = feedback_updated
                if has_local_feedback:
                    info['local_feedback_path'] = os.path.join(
                        assignment_dir, 'feedback', info['timestamp'])
                else:
                    info['local_feedback_path'] = None

            assignments.append(info)

        # partition the assignments into groups for course/student/assignment
        if self.inbound or self.cached:
            _get_key = lambda info: (info['course_id'], info['student_id'], info['assignment_id'])
            _match_key = lambda info, key: (
                info['course_id'] == key[0] and
                info['student_id'] == key[1] and
                info['assignment_id'] == key[2])
            assignment_keys = sorted(list(set([_get_key(info) for info in assignments])))
            assignment_submissions = []
            for key in assignment_keys:
                submissions = [x for x in assignments if _match_key(x, key)]
                submissions = sorted(submissions, key=lambda x: x['timestamp'])
                info = {
                    'course_id': key[0],
                    'student_id': key[1],
                    'assignment_id': key[2],
                    'status': submissions[0]['status'],
                    'submissions': submissions
                }
                assignment_submissions.append(info)
            assignments = assignment_submissions

        return assignments

    def list_files(self):
        """List files."""
        assignments = self.parse_assignments()

        if self.inbound or self.cached:
            self.log.info("Submitted assignments:")
            for assignment in assignments:
                for info in assignment['submissions']:
                    self.log.info(self.format_inbound_assignment(info))
        else:
            self.log.info("Released assignments:")
            for info in assignments:
                self.log.info(self.format_outbound_assignment(info))

        return assignments

    def remove_files(self):
        """List and remove files."""
        assignments = self.parse_assignments()

        if self.inbound or self.cached:
            self.log.info("Removing submitted assignments:")
            for assignment in assignments:
                for info in assignment['submissions']:
                    self.log.info(self.format_inbound_assignment(info))
        else:
            self.log.info("Removing released assignments:")
            for info in assignments:
                self.log.info(self.format_outbound_assignment(info))

        if self.cached:
            for assignment in self.assignments:
                shutil.rmtree(assignment)
        # TODO: Remove inbound and outbound assignments.

        return assignments

    def start(self):
        if self.inbound and self.cached:
            self.fail("Options --inbound and --cached are incompatible.")

        super(ExchangeList, self).start()

        if self.remove:
            return self.remove_files()
        else:
            return self.list_files()
