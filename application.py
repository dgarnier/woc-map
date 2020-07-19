import os
from app import create_app


# os.environ['FLASK_ENV'] = 'staging'
# os.environ['FLASK_CONFIG'] = 'staging'
# os.environ['FLASK_DEBUG'] = '1'

# application = create_app('staging')

application = create_app(os.environ.get('FLASK_ENV', 'default'))
application.debug = True

if os.environ.get('SERVER_NAME'):
    application.config.update(SERVER_NAME=os.environ['SERVER_NAME'])

print(application.config.__dict__)

if __name__ == '__main__':
    application.run()
