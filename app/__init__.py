import os
from flask import Flask
import click
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_migrate import Migrate

from app.models import db
from app.auth import oauth, auth
from app.main import main
import app.strava as strava

from config import app_config


def create_app(configuration='default'):

    app = Flask(__name__)

    app.config.from_object(app_config[configuration])
    # app_config[configuration].init_app(app)
    app.logger.info(f'Configuration: {configuration}')

    bs = Bootstrap()
    bs.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    db.init_app(app)
    migrate = Migrate(app, db)

    oauth.init_app(app)
    app.register_blueprint(auth)

    app.register_blueprint(main)

    app.register_blueprint(strava.strava, url_prefix='/strava')

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
