
import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config():
    SECRET_KEY = b'SHH Its a secret!'
    STRAVA_CLIENT_SECRET = "STRAVA_CLIENT_SECRET"
    STRAVA_CLIENT_ID = "STRAVA_CLIENT_ID"
    STRAVA_CLUB_ID = "STRAVA_CLUB_ID"
    STRAVA_VERIFY_TOKEN = "SUBSCRIPTION_VERIFY_TOKEN"
    STRAVA_CLIENT_KWARGS = {
        'response_type': 'code',
        'approval_prompt': 'auto',
        'scope': 'read,activity:read',
        'token_endpoint_auth_method': 'client_secret_post',
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    DEBUG = True
    # SQLALCHEMY_ECHO = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')


class TestingConfig(Config):
    CALL_STRAVA_API = False
    TESTING = True
    LIVESERVER_PORT = 8943
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'test_app.db')


class StagingConfig(Config):
    DEBUG = True
    # SQLALCHEMY_ECHO = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('STAGING_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'stage_app.db')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'prod_app.db')


app_config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'eb': StagingConfig,
    'default': DevelopmentConfig,
}
