import os
from app import create_app


os.environ['FLASK_ENV'] = 'staging'
os.environ['FLASK_CONFIG'] = 'staging'
os.environ['FLASK_DEBUG'] = '1'

application = create_app('staging')
application.debug = True

print(application.config.__dict__)

if __name__ == '__main__':
    application.run()
