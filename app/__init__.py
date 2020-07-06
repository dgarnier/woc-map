from datetime import datetime
import os
from flask import Flask, flash, render_template, request, jsonify, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, login_user, login_required, current_user
from authlib.integrations.flask_client import OAuth, token_update
from loginpass import Strava, create_flask_blueprint

# encapsulated app code
from app.models import db, Athlete
from config import app_config


app = Flask(__name__)
app.config.from_object(app_config[os.getenv('FLASK_CONFIG') or 'default'])

db.init_app(app)

bs = Bootstrap(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Athlete.query.get(int(user_id))


@app.route('/')
def index():
    # return render_template("index.html")
    return redirect('/map')


@app.route('/map')
def map():
    return render_template('map.html')


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
    tpl = '<ul><li><a href="/login/strava">Strava Login</a></li></ul>'
    return tpl


@app.route('/user_info')
@login_required
def user_info():
    return render_template('user_info.html', user_info=current_user)


def refresh_athlete_token(athlete, token):
    athlete.auth_granted = True
    athlete.access_token = token['access_token']
    athlete.access_token_expires_at = int(token['expires_at'])
    athlete.refresh_token = token['refresh_token']
    athlete.last_updated = datetime.utcnow()
    db.session.commit()


def athlete_token(athlete):
    return dict(
            access_token=athlete.access_token,
            refresh_token=athlete.refresh_token,
            expires_at=athlete.access_token_expires_at
        )


def fetch_token(name):
    # fetch the token based on the name of the authenticator
    if name == 'strava':
        if current_user.auth_granted:
            return athlete_token(current_user)


@token_update.connect_via(app)
def on_token_update(sender, name, token, refresh_token=None,
                    access_token=None):
    # after an automatic refresh of a token.. have to look it up
    if name == 'strava':
        if refresh_token:
            ath = Athlete.query.filter_by(refresh_token=refresh_token).first()
        elif access_token:
            ath = Athlete.query.filter_by(access_token=access_token).first()
        else:
            return

        refresh_athlete_token(ath, token)


def handle_authorize(remote, token, user_info):
    """
    called by loginpass after normal strava access token granting
    :return:
    redirect to page
    """
    if remote.name == 'strava':
        if token is None:
            error = request.args.get('error')
            if error == 'access_denied':
                flash('Strava: Access Denied', 'warning')
            else:
                flash('Strava: Invalid response.', 'danger')
            return redirect('/')
        # woot.. got authorization token.  Lets save it and the user...

        user_id = int(user_info.sub)
        athlete = Athlete.query.get(user_id)
        if athlete is None:         # new athlete!
            # there's a lot of info in the token, more than in user_info.
            ai = token['athlete']
            # could probably do this with athlete = Athlete(*ai)
            athlete = Athlete(
                id=ai['id'], username=ai['username'],
                firstname=ai['firstname'], lastname=ai['lastname'],
                city=ai['city'], state=ai['state'], country=ai['country'],
                profile=ai['profile'], profile_medium=ai['profile_medium']
            )
            db.session.add(athlete)

        refresh_athlete_token(athlete, token)
        # we should check for a subscription

        login_user(athlete, remember=True)

        # return render_template('user_info.html', user_info=user_info)
        # return redirect(url_for('user_info'))
        return redirect(url_for('map'))

    else:
        app.logger.error(f'Authorize unknown service: {remote.name}')


def handle_strava_webhook_event(data):
    """
    This lets strava send us data.  Here's what this needs to do.

    1.  Log it.
        a.  make a new entry & fill it out
        b. save it to the database
        c. log it to the logger.

    2.  If its an athlete.. problably need to delete the token

    3.  If its an activity..
        check if is an activity we care about
        if so, check if we have it
        if we dont, or its an update, download it again
        save the activity
    """
    app.logger.info('StravaEvent {data}')


# handle strava webhooks subscriptions
@app.route('/strava/callback', methods=['GET', 'POST'])
def strava_callback():
    # with a GET, strava is just validating
    if request.method == 'GET':
        app.logger.info('Strava callback GET subscription validation')
        mode = request.args.get('hub.mode')
        challenge = request.args.get('hub.challenge')
        token = request.args.get('hub.verify_token')
        if mode == 'subscribe' and len(challenge) > 0 and \
                token == app.config['STRAVA_VERIFY_TOKEN']:
            # sweet.. strava cares.
            # respond approriately
            return jsonify({'hub.challenge': challenge}), 200
        else:
            return jsonify({'error': 'invalid params'}), 400

    # ok.. now we really can deal with the callback
    # this is a real strava event
    data = request.get_json(force=True)
    handle_strava_webhook_event(data)

    return '', 200


oauth = OAuth(app, fetch_token=fetch_token)
auth_bp = create_flask_blueprint([Strava], oauth, handle_authorize)
app.register_blueprint(auth_bp)


@app.cli.command()
def initdb():
    # call "flask initdb" to initialized the database
    app.logger.info('Initialzing the database.')
    print('Initializing the database.')
    db.create_all()


from app import models
