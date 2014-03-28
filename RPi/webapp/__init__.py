from flask import Flask

#import logging, sys
#logging.basicConfig(stream=sys.stderr)

from flask.ext.bootstrap import Bootstrap
from flask.ext.appconfig import AppConfig
def create_app(configfile=None):
    app = Flask(__name__)
    AppConfig(app, configfile)

    Bootstrap(app)

    app.config['SECRET_KEY'] = 'BEPHZyS3SY9BrFWwgTHJ2xVFrQk44ggE4WAR3QPpNiIgIiCmJmmkEO15gepeEQBENHDfrIcfGmYuP2envn2QX6TLOYl0J06qLcme'

    app.config['LOG_FILE_PATH'] = '/tmp/seniorproj.log'
    app.config['LOG_TO_EMAIL'] = False

    return app

app = create_app()
#app.config['BOOTSTRAP_SERVE_LOCAL'] = True

from .log import set_up_loggers
set_up_loggers()

from .forms import *
from . import view

__all__ = ['app', 'forms']

