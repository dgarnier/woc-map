#!/home1/wheelsp5/wocapp/env/bin/python

import os, sys
from os.path import *
from flup.server.fcgi import WSGIServer
from app import app
import logging

code_dir = dirname(abspath(__file__))
log_dir = join(code_dir,'log')

# middleware for using mod_rewrite
class ScriptNameStripper(object):
   def __init__(self, app):
       self.app = app

   def __call__(self, environ, start_response):
       environ['SCRIPT_NAME'] = '/wocapp/app'
       return self.app(environ, start_response)


application = ScriptNameStripper(app)
logging.basicConfig(filename=join(log_dir,'flask_console.log'), level=logging.DEBUG)

WSGIServer(application).run()

