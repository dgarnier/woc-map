# awseb wants things called application
from app import app as application
import logging
from os.path import *

if __name__ == '__main__':
    application.debug = True
    logging.basicConfig(filename=join(
        dirname(abspath(__file__)), 'flask_console.log'), level=logging.DEBUG)

    application.run()
