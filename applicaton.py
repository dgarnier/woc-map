# awseb wants things called application
from app import app as application

if __name__ == '__main__':
    application.debug = True
    application.run()
