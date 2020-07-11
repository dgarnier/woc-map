import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, login_required, current_user

from app.models import db
from app.auth import auth_bp, oauth
from app.strava import strava_bp

from config import app_config


app = Flask(__name__)
app.config.from_object(app_config[os.getenv('FLASK_CONFIG') or 'default'])

bs = Bootstrap()
bs.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

db.init_app(app)

oauth.init_app(app)
app.register_blueprint(auth_bp)
app.register_blueprint(strava_bp)


@app.route('/')
def index():
    # return render_template("index.html")
    return redirect(url_for('map'))


@app.route('/map')
def map():
    if current_user.is_anonymous:
        user_info = dict(anonymous=True)
    else:
        user_info = {prop: getattr(current_user, prop)
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
        user_info['anonymous'] = False

    return render_template('map.html', user_info=user_info)


@app.route('/activate')
def activate():
    return render_template('activate.html')


@app.route('/club_activities')
@login_required
def club_activities():
    club = app.config['STRAVA_CLUB_ID']
    url = f"clubs/{club}/activities"
    app.logger.info(f'Getting club activites: {url}')
    params = {'per_page': 30, 'page': 1}
    resp = oauth.strava.request('GET', url, params=params)
    app.logger.info(resp)
    return jsonify(resp.json())


@app.route('/club/<api>')
@login_required
def club_api(api):
    club = app.config['STRAVA_CLUB_ID']
    url = f"clubs/{club}/{api}"
    app.logger.info(f'Getting club {api}: {url}')
    resp = oauth.strava.request('GET', url, params=request.args)
    app.logger.info(resp)
    return jsonify(resp.json())


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
