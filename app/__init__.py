import os
from flask import Flask, render_template, jsonify, redirect, url_for
import click
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, login_required, current_user

from app.models import db
from app.auth import oauth, auth
import app.strava as strava

from config import app_config


app = Flask(__name__)
app.config.from_object(app_config[os.getenv('FLASK_CONFIG') or
                                  os.getenv('FLASK_ENV') or 'default'])

bs = Bootstrap()
bs.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

db.init_app(app)

oauth.init_app(app)
app.register_blueprint(auth)

app.register_blueprint(strava.strava, url_prefix='/strava')


@app.route('/')
def index():
    # return render_template("index.html")
    return redirect(url_for('map'))


@app.route('/map')
def map():
    if current_user.is_anonymous:
        info = dict(anonymous=True)
    else:
        info = {prop: getattr(current_user, prop)
                for prop in [
                        'firstname',
                        'lastname',
                        'profile',
                        'profile_medium',
                        'city',
                        'state',
                        'country'
                    ]
                }
        if not info['profile_medium']:
            info['profile_medium'] = \
                'https://ui-avatars.com/api/?bold=true&size=70' + \
                f"&name={info['firstname']}+{info['lastname']}"
        info['anonymous'] = False

    return render_template('map.html', user_info=info)


@app.route('/activate')
def activate():
    return render_template('activate.html')


@app.route('/activity/<activity_id>')
def activity(activity_id):
    url = f"activities/{activity_id}"
    app.logger.info(f'Get: {url}')
    resp = oauth.strava.request(
        'GET', url, params={'include_all_efforts': ' '})
    app.logger.info(resp)
    return jsonify(resp.json())


@app.route('/map_activity/<activity_id>')
def map_activity(activity_id):
    url = f"activities/{activity_id}"
    resp = oauth.strava.request(
        'GET', url, params={'include_all_efforts': ' '})
    app.logger.info(f'GET: {url} = {resp.status_code}')
    data = resp.json()
    return render_template(
                    'activity.html',
                    polyline=data['map']['polyline'],
                    popup=data['name']
            )


@app.route('/strava_login')
def strava_login():
    return render_template('strava_login.html')


@app.route('/user_info')
@login_required
def user_info():
    return render_template('user_info.html', user_info=current_user)


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
