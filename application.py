import os
from app import create_app

application = create_app(os.environ.get('FLASK_APP_ENV', 'production'))
application.debug = True

if os.environ.get('SERVER_NAME'):
    application.config.update(SERVER_NAME=os.environ['SERVER_NAME'])

print(application.config.__dict__)

if __name__ == '__main__':
    application.run()
