import os
import json
import traceback

from notebook.base.handlers import APIHandler
from notebook.utils import url_path_join
import tornado
from textwrap import dedent

from traitlets.config import Config
from jupyter_core.paths import jupyter_config_path

# TODO: from ...apps import NbGrader
# TODO: from ...validator import Validator
# TODO: from ...nbgraderformat import SchemaTooOldError, SchemaTooNewError
# TODO: from ... import __version__ as nbgrader_version

class SchemaTooOldError(Exception): pass    # TODO: hardcoded value
class SchemaTooNewError(Exception): pass    # TODO: hardcoded value
nbgrader_version = '0.7.0.dev'  # TODO: hardcoded value

class NbGraderVersionHandler(APIHandler):

    @tornado.web.authenticated
    def get(self):
        ui_version = self.get_argument('version')
        if ui_version != nbgrader_version:
            msg = dedent(
                """
                The version of the Validate nbextension does not match
                the server extension; the nbextension version is {} while the
                server version is {}. This can happen if you have recently
                upgraded nbgrader, and may cause this extension to not work
                correctly. To fix the problem, please see the nbgrader
                installation instructions:
                http://nbgrader.readthedocs.io/en/stable/user_guide/installation.html
                """.format(ui_version, nbgrader_version)
            ).strip().replace("\n", " ")
            self.log.error(msg)
            result = {"success": False, "message": msg}
        else:
            result = {"success": True}

        self.finish(json.dumps(result))

class ValidateAssignmentHandler(APIHandler):

    @property
    def notebook_dir(self):
        return self.settings['notebook_dir']

    def load_config(self):
        paths = jupyter_config_path()
        paths.insert(0, os.getcwd())

        config_found = False
        full_config = Config()
        for config in NbGrader._load_config_files("nbgrader_config", path=paths, log=self.log):
            full_config.merge(config)
            config_found = True

        if not config_found:
            self.log.warning("No nbgrader_config.py file found. Rerun with DEBUG log level to see where nbgrader is looking.")

        return full_config

    def validate_notebook(self, path):
        fullpath = os.path.join(self.notebook_dir, path)

        try:
            config = None       # config = self.load_config()
                                # validator = Validator(config=config)
            result = ''         # result = validator.validate(fullpath)
            if self.get_argument('test', '0') == '1':
                raise SchemaTooOldError
            elif self.get_argument('test', '0') == '2':
                raise SchemaTooNewError
            elif self.get_argument('test', '0') == '3':
                raise ZeroDivisionError

        except SchemaTooOldError:
            msg = (
                "The notebook '{}' uses an old version "
                "of the nbgrader metadata format. Please **back up this "
                "notebook** and then update the metadata using:\n\nnbgrader update {}\n"
            ).format(fullpath, fullpath)
            self.log.error(msg)
            retvalue = {
                "success": False,
                "value": msg
            }

        except SchemaTooNewError:
            msg = (
                "The notebook '{}' uses a newer version "
                "of the nbgrader metadata format. Please update your version of "
                "nbgrader to the latest version to be able to use this notebook."
            ).format(fullpath)
            retvalue = {
                "success": False,
                "value": msg
            }

        except:
            retvalue = {
                "success": False,
                "value": traceback.format_exc()
            }

        else:
            retvalue = {
                "success": True,
                "value": result
            }

        return retvalue

    @tornado.web.authenticated
    def post(self):
        output = self.validate_notebook(self.get_argument('path'))
        self.finish(json.dumps(output))

def setup_handlers(web_app):
    host_pattern = ".*$"
    
    base_url = web_app.settings["base_url"]
    handlers = [
        (url_path_join(base_url, "validate_assignment", "assignments/validate"),
         ValidateAssignmentHandler),
        (url_path_join(base_url, "validate_assignment", "nbgrader_version"),
         NbGraderVersionHandler),
    ]
    webapp.settings['notebook_dir'] = '/i/dont/know/what/to/put/here/'
    web_app.add_handlers(host_pattern, handlers)
