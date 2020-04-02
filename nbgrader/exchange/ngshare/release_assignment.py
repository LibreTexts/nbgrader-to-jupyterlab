#!/usr/bin/python
import os
import shutil
from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IWGRP, S_IXGRP, \
    S_IROTH, S_IWOTH, S_IXOTH, S_ISGID, ST_MODE

from traitlets import Bool

from nbgrader.exchange.abc import ExchangeReleaseAssignment as ABCExchangeReleaseAssignment
from nbgrader.exchange.ngshare import Exchange


class ExchangeReleaseAssignment(Exchange, ABCExchangeReleaseAssignment):

    force = Bool(False,
                 help='Force overwrite existing files in the exchange.'
                 ).tag(config=True)

    def _load_config(self, cfg, **kwargs):
        if 'ExchangeRelease' in cfg:
            self.log.warning('Use ExchangeReleaseAssignment in config, not ExchangeRelease. Outdated config:\n%s'
                             ,
                             '\n'.join('ExchangeRelease.{key} = {value!r}'.format(key=key,
                             value=svalue) for (key, value) in
                             cfg.ExchangeRelease.items()))

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
                self.fail("Assignment found in '{}' but not '{}', run `nbgrader generate_assignment` first.".format(source, self.src_path))
            else:
                self._assignment_not_found(self.src_path, self.coursedir.format_path(self.coursedir.release_directory, '.', '*'))

    def init_dest(self):
        self.dest_path = '/assignment/{}/{}'.format(self.coursedir.course_id, self.coursedir.assignment_id)

    def copy_files(self):
        self.log.info('Encoding assignment')
        data = self.encode_dir(self.src_path)
        response = self.ngshare_api_post(self.dest_path, data)
        if response is None:
            self.log.warn('An error occurred while trying to release {}'.format(self.coursedir.assignment_id))
        else:
            self.log.info('Successfully released {}'.format(self.coursedir.assignment_id))
