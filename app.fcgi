#!/home1/wheelsp5/wocapp/env/bin/python

import os
from os.path import dirname, abspath, join
from flup.server.fcgi import WSGIServer
import logging
from app import create_app


os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = '1'

app = create_app('production')

code_dir = dirname(abspath(__file__))
# log_dir = join(code_dir,'log')
log_dir = code_dir


# middleware for using mod_rewrite
class ScriptNameStripper(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = '/app'
        return self.app(environ, start_response)


app.config['APPLICATION_ROOT'] = '/app'
application = ScriptNameStripper(app)

# limiting threads doesn't seem to help
# but the (default) threading server is the one that 
# people say is compatible with FastCGI in dynamic mode (.htaccess enabled)

logging.basicConfig(filename=join(log_dir, 'flask_console.log'),
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG)

# WSGIServer(application, maxThreads=8).run()
WSGIServer(application).run()
