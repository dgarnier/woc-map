from flask import Flask
import click
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_migrate import Migrate
# from flask_wtf.csrf import CSRFProtect

from app.models import db
# from app.auth import auth
import app.auth as auth
from app.main import main
from app.api import api
import app.strava as strava
import app.admin as admin


def create_app(configuration='default'):
    # don't import app_config until needed
    from config import app_config

    app = Flask(__name__)

    app.config.from_object(app_config[configuration])
    # app_config[configuration].init_app(app)
    app.logger.info(f'Configuration: {configuration}')
    app.logger.info(f"SERVER_NAME: { app.config['SERVER_NAME'] }")

    bs = Bootstrap()
    bs.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    # csrf = CSRFProtect()
    # csrf.init_app(app)

    db.init_app(app)

    migrate = Migrate()
    migrate.init_app(app, db)

    auth.oauth.init_app(app)
    app.register_blueprint(auth.auth)

    app.register_blueprint(main)
    app.register_blueprint(api, url_prefix='/api')

    app.register_blueprint(strava.strava, url_prefix='/strava')
    app.register_blueprint(admin.admin, url_prefix='/admin')

    @app.cli.command()
    def initdb():
        # call "flask initdb" to initialized the database
        app.logger.info('Initialzing the database.')
        print('Initializing the database.')
        db.create_all()

    @app.cli.command("webhook-reset")
    @click.argument("subscription_id")
    def webhook_reset(subscription_id):
        strava.delete_subscription(subscription_id)

    return app
