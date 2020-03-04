import os
import shutil
from stat import (
    S_IRUSR, S_IWUSR, S_IXUSR,
    S_IRGRP, S_IWGRP, S_IXGRP,
    S_IROTH, S_IWOTH, S_IXOTH,
    S_ISGID, ST_MODE
)

from traitlets import Bool

from nbgrader.exchange.abc import ExchangeReleaseAssignment as ABCExchangeReleaseAssignment
from nbgrader.exchange.ngshare import Exchange

import requests
import json


class ExchangeReleaseAssignment(Exchange, ABCExchangeReleaseAssignment):

    force = Bool(False, help="Force overwrite existing files in the exchange.").tag(config=True)

    def _load_config(self, cfg, **kwargs):
        if 'ExchangeRelease' in cfg:
            self.log.warning(
                "Use ExchangeReleaseAssignment in config, not ExchangeRelease. Outdated config:\n%s",
                '\n'.join(
                    'ExchangeRelease.{key} = {value!r}'.format(key=key, value=value)
                    for key, value in cfg.ExchangeRelease.items()
                )
            )
            cfg.ExchangeReleaseAssignment.merge(cfg.ExchangeRelease)
            del cfg.ExchangeRelease

        super(ExchangeReleaseAssignment, self)._load_config(cfg, **kwargs)

    def ensure_root(self):
        pass

    def init_src(self):
        self.src_path = self.coursedir.format_path(self.coursedir.release_directory, '.', self.coursedir.assignment_id)

        if not os.path.isdir(self.src_path):
            source = self.coursedir.format_path(self.coursedir.source_directory, '.', self.coursedir.assignment_id)
            if os.path.isdir(source):
                # Looks like the instructor forgot to assign
                self.fail("Assignment found in '{}' but not '{}', run `nbgrader generate_assignment` first.".format(
                    source, self.src_path))
            else:
                self._assignment_not_found(
                    self.src_path,
                    self.coursedir.format_path(self.coursedir.release_directory, '.', '*'))

    '''
    def _check_if_course_exists(self):
        data = {'user': self.username}
        list_url = self.ngshare_url + '/api/courses'
        try:

            response = requests.post(url = list_url, data = data)
        except:
            self.log.warm("Error occured while trying to list all courses")
        self.log.info(response.json()['success'])
        if response.json()['success']:
            courses = response.json()['courses']

            for course in courses:
                if course == self.self.coursedir.course_id:
                    return 

            # if you got here couse doesn exist so create it
            course_url = self.ngshare_url + '/api/course/{}'.format(self.coursedir.course_id)
            response = requests.post(url = course_url, data = data)
            self.log.info("created course")
    '''
    def init_dest(self):
        data = {'user': self.username}
        course_url = self.ngshare_url + '/api/course/{}'.format(self.coursedir.course_id)
        response = requests.post(url = course_url, data = data)
        #self._check_if_course_exists()
        self.dest_path = self.ngshare_url + '/api/assignment/{}/{}'.format(self.coursedir.course_id, self.coursedir.assignment_id)

    def copy_files(self):

        
        try:
            data = self.encode_dir(self.src_path)
            response = requests.post(url = self.dest_patht, data = data)
        except:
            self.log.warn('An error occurred while trying to release 2 {}'.format(self.coursedir.assignment_id))
            
        if response.status_code != requests.codes.ok:
            self.log.warn('An error occurred while trying to release {}'.format(self.coursedir.assignment_id))  
        elif not response.json()['success']:
            self.log.warn('An error occurred while trying to release {}'.format(self.coursedir.assignment_id)) 
            self.log.warn(response.json()['message'])
        else:
            self.log.info("Successfully released {}".format(self.coursedir.assignment_id))
        
