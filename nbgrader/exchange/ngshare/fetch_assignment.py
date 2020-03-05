import os
import shutil

from traitlets import Bool

from nbgrader.exchange.abc import ExchangeFetchAssignment as ABCExchangeFetchAssignment
from nbgrader.exchange.ngshare import Exchange
from nbgrader.utils import check_mode
import requests

class ExchangeFetchAssignment(Exchange, ABCExchangeFetchAssignment):

    def _load_config(self, cfg, **kwargs):
        if 'ExchangeFetch' in cfg:
            self.log.warning(
                "Use ExchangeFetchAssignment in config, not ExchangeFetch. Outdated config:\n%s",
                '\n'.join(
                    'ExchangeFetch.{key} = {value!r}'.format(key=key, value=value)
                    for key, value in cfg.ExchangeFetchAssignment.items()
                )
            )
            cfg.ExchangeFetchAssignment.merge(cfg.ExchangeFetch)
            del cfg.ExchangeFetchAssignment

        super(ExchangeFetchAssignment, self)._load_config(cfg, **kwargs)

    def init_src(self):
        if self.coursedir.course_id == '':
            self.fail("No course id specified. Re-run with --course flag.")
        if not self.authenticator.has_access(self.coursedir.student_id, self.coursedir.course_id):
            self.fail("You do not have access to this course.")

        self.src_path = self.ngshare_url + '/api/assignment/{}/{}'.format(self.coursedir.course_id, self.coursedir.assignment_id)

    def init_dest(self):
        if self.path_includes_course:
            root = os.path.join(self.coursedir.course_id, self.coursedir.assignment_id)
        else:
            root = self.coursedir.assignment_id
        self.dest_path = os.path.abspath(os.path.join(self.assignment_dir, root))
        if os.path.isdir(self.dest_path) and not self.replace_missing_files:
            self.fail("You already have a copy of the assignment in this directory: {}".format(root))

    def copy_files(self):
        try:
            params = {'user': self.username}
            response = requests.get(self.src_path, params)          
        except:
            self.log.warn('An error occurred while trying to get assignment {}'.format(self.coursedir.assignment_id))
        
        if response.status_code != requests.codes.ok:
            self.log.warn('An error occurred while trying to release {}'.format(self.coursedir.assignment_id))
        elif not response.json()['success']:
            self.log.warn('An error occurred while trying to release {}'.format(self.coursedir.assignment_id))
            self.log.warn(response.json()['message'])
        else:
            self.log.info("Successfully fetched {}".format(self.coursedir.assignment_id))
        
        if not os.path.exists(self.dest_path):
            os.mkdir(self.dest_path)
        try:
            self.decode_dir(response.json()['files'], self.dest_path, ignore=shutil.ignore_patterns(*self.coursedir.ignore))
        except:
            self.log.warn("Could not decode the assignment")
        
        self.log.info("Fetched as: {} {}".format(self.coursedir.course_id, self.coursedir.assignment_id))
