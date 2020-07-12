
import os
basedir = os.path.abspath(os.path.dirname(__file__))

try:
    from secrets import Config
    Config.SQLALCHEMY_TRACK_MODIFICATIONS = False

except ImportError:

    class Config():
        SECRET_KEY = os.environ.get('SECRET_KEY') or \
            b'SHH Its a secret!'
        STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET") or \
            "STRAVA_CLIENT_SECRET"
        STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID") or \
            "STRAVA_CLIENT_ID"
        STRAVA_CLUB_ID = os.environ.get("STRAVA_CLUB_ID") or \
            "STRAVA_CLUB_ID"
        STRAVA_VERIFY_TOKEN = os.environ.get("SUBSCRIPTION_VERIFY_TOKEN") or \
            "SUBSCRIPTION_VERIFY_TOKEN"
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
        'sqlite:///' + os.path.join(basedir, 'app.sqlite3')


class TestingConfig(Config):
    CALL_STRAVA_API = False
    TESTING = True
    LIVESERVER_PORT = 8943
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'test_app.sqlite3')


class StagingConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('STAGING_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'stage_app.sqlite3')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('PRODUCTION_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'prod_app.sqlite3')


app_config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'default': DevelopmentConfig,
}
