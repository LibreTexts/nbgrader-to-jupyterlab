#!/usr/bin/python
import os
import shutil

from traitlets import Bool

from nbgrader.exchange.abc import ExchangeFetchAssignment as ABCExchangeFetchAssignment
from nbgrader.exchange.ngshare import Exchange
from nbgrader.utils import check_mode


class ExchangeFetchAssignment(Exchange, ABCExchangeFetchAssignment):

    def _load_config(self, cfg, **kwargs):
        if 'ExchangeFetch' in cfg:
            self.log.warning('Use ExchangeFetchAssignment in config, not ExchangeFetch. Outdated config:\n%s'
                             ,
                             '\n'.join('ExchangeFetch.{key} = {value!r}'.format(key=key,
                             value=value) for (key, value) in
                             cfg.ExchangeFetchAssignment.items()))

            cfg.ExchangeFetchAssignment.merge(cfg.ExchangeFetch)
            del cfg.ExchangeFetchAssignment

        super(ExchangeFetchAssignment, self)._load_config(cfg, **kwargs)

    def init_src(self):
        if self.coursedir.course_id == '':
            self.fail('No course id specified. Re-run with --course flag.')
        if not self.authenticator.has_access(self.coursedir.student_id, self.coursedir.course_id):
            self.fail('You do not have access to this course.')

        self.src_path = '/assignment/{}/{}'.format(self.coursedir.course_id, self.coursedir.assignment_id)

    def init_dest(self):
        if self.path_includes_course:
            root = os.path.join(self.coursedir.course_id, self.coursedir.assignment_id)
        else:
            root = self.coursedir.assignment_id
        self.dest_path = os.path.abspath(os.path.join(self.assignment_dir, root))
        if os.path.isdir(self.dest_path) and not self.replace_missing_files:
            self.fail('You already have a copy of the assignment in this directory: {}'.format(root))

    def copy_files(self):
        response = self.ngshare_api_get(self.src_path)
        if response is None:
            self.log.warn('Failed to fetch assignment.')
        else:
            self.log.info('Successfully fetched {}. Will try to decode'.format(self.coursedir.assignment_id))
            try:
                self.decode_dir(response['files'], self.dest_path)
                self.log.info('Successfully decoded {}.'.format(self.coursedir.assignment_id))
            except:
                self.log.warn('Could not decode the assignment')
