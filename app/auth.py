from flask import flash, request, redirect, url_for
from flask_login import current_user
from authlib.integrations.flask_client import OAuth
from loginpass import Strava, create_flask_blueprint
from flask_login import login_user

# from app import app, db
from app.models import db, Athlete


def fetch_token(name):
    # fetch the token based on the name of the authenticator
    if name == 'strava':
        return current_user.auth_token


# @token_update.connect_via(app)
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

        ath.auth_token = token


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

        # refresh and save the token
        athlete.auth_token = token

        login_user(athlete, remember=True)

        # return render_template('user_info.html', user_info=user_info)
        # return redirect(url_for('user_info'))
        return redirect(url_for('map'))


# get the oauth session, which also has a requests interface
oauth = OAuth(fetch_token=fetch_token,
              update_token=on_token_update)

# ask for activity read
Strava.OAUTH_CONFIG['client_kwargs']['scope'] = 'read,activity:read'
# appp.auth.auth is a blueprint
auth_bp = create_flask_blueprint([Strava], oauth, handle_authorize)
