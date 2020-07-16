from flask import (Blueprint, render_template, jsonify, redirect,
                   url_for, current_app)
from flask_login import login_required, current_user

# from app.models import db
from app.auth import oauth
# import app.strava as strava

main = Blueprint('main', __name__)


@main.route('/')
def index():
    # return render_template("index.html")
    return redirect(url_for('main.map'))


@main.route('/map')
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


@main.route('/activate')
def activate():
    return render_template('activate.html')


@main.route('/activity/<activity_id>')
def activity(activity_id):
    url = f"activities/{activity_id}"
    current_app.logger.info(f'Get: {url}')
    resp = oauth.strava.request(
        'GET', url, params={'include_all_efforts': ' '})
    current_app.logger.info(resp)
    return jsonify(resp.json())


@main.route('/map_activity/<activity_id>')
def map_activity(activity_id):
    url = f"activities/{activity_id}"
    resp = oauth.strava.request(
        'GET', url, params={'include_all_efforts': ' '})
    current_app.logger.info(f'GET: {url} = {resp.status_code}')
    data = resp.json()
    return render_template(
                    'activity.html',
                    polyline=data['map']['polyline'],
                    popup=data['name']
            )


@main.route('/strava_login')
def strava_login():
    return render_template('strava_login.html')


@main.route('/user_info')
@login_required
def user_info():
    return render_template('user_info.html', user_info=current_user)
