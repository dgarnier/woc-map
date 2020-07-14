from flask import flash, request, redirect, url_for, current_app
from flask_login import current_user
from authlib.integrations.flask_client import OAuth, token_update
from loginpass import Strava, create_flask_blueprint
from flask_login import login_user

# from app import app, db
from app.models import db, Athlete
import app.strava as strava


def fetch_token(name):
    # fetch the token based on the name of the authenticator
    if name == 'strava':
        if current_user.is_authenticated:
            current_app.logger.info("fetching auth token")
            return current_user.auth_token
    else:
        current_app.logger.error('fetching token but not strava auth')
    return None


@token_update.connect
def on_token_update(sender, name, token, refresh_token=None,
                    access_token=None):
    # after an automatic refresh of a token.. have to look it up
    # this can get called with a "bad token message"

    if name == 'strava':
        strava_update_token(token, refresh_token=refresh_token,
                            access_token=access_token)


def strava_update_token(token, refresh_token=None, access_token=None):
    with current_app.app_context():
        if refresh_token:
            ath = Athlete.query.filter_by(refresh_token=refresh_token).first()
        elif access_token:
            ath = Athlete.query.filter_by(access_token=access_token).first()
        else:
            return

        current_app.logger.debug(f'update token: {token}')
        if ath is None:
            current_app.logger.warn(f'Got access token without owner: {token}')
            return

        if token.get('message') == 'Bad Request':
            # this is likely a bad token.. need to just reject the token
            current_app.logger.warn(f'Bad refresh token for: {ath.id}')
            ath.deauthorize()
        else:
            current_app.logger.info(f'Token refreshed for: {ath.id}')
            ath.auth_token = token
        db.session.commit()


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
                flash('Strava access Denied.\n' +
                      f"Please <a href={url_for('activate')}>" +
                      "activate</a> to contribute.", 'error')
            else:
                flash('Strava: Invalid response.', 'error')
            return redirect(url_for('map'))
        # woot.. got authorization token.  Lets save it and the user...

        def fix_bad_link(a, link):
            if a[link] and not a[link].startswith('http'):
                a[link] = None

        ai = token['athlete']
        fix_bad_link(ai, 'profile')
        fix_bad_link(ai, 'profile_medium')

        user_id = int(user_info.sub)
        athlete = Athlete.query.get(user_id)

        if athlete is None:         # new athlete!
            # there's a lot of info in the token, more than in user_info.
            athlete = Athlete(
                id=ai['id'], username=ai['username'],
                firstname=ai['firstname'], lastname=ai['lastname'],
                city=ai['city'], state=ai['state'], country=ai['country'],
                profile=ai['profile'], profile_medium=ai['profile_medium']
            )

            db.session.add(athlete)

        attrs = ['username', 'firstname', 'lastname', 'city', 'state',
                 'country', 'profile', 'profile_medium']
        for attr in attrs:
            if getattr(athlete, attr) != ai[attr]:
                setattr(athlete, attr, ai[attr])

        # set or refresh token
        athlete.auth_token = token

        # get club membership
        # don't login yet, but use the token provided.
        club_data = strava.get_club_info(token=token)
        if club_data:
            is_member = (club_data.get('membership') == "member")
            is_admin = club_data.get('admin')
        else:
            is_admin = False
            is_member = False

        athlete.club_member = is_member
        athlete.club_admin = is_admin

        if not is_member:
            # reject the authorization and fail.
            athlete.deauthorize()
            flash('You must be a member of the '
                  "<a href='https://www.strava.com/clubs/WheelsofChange'>"
                  'Wheels of Change</a> club on STRAVA to participate',
                  'danger')

        if 'activity:read' not in request.args.get('scope'):
            athlete.deauthorize()
            flash('You must grant access to read activities to '
                  "participate. Please <a href='"
                  f"{url_for('loginpass.login', name='strava')}'>"
                  "Authorize</a> again.", 'danger')

        if not athlete.is_authenticated:
            db.session.commit()
            strava.deauthorize_athlete_from_token(token)
            return redirect(url_for('map'))

        login_user(athlete, remember=True)
        db.session.commit()

        flash("Login successful. Let's do this!", 'success')
        # return render_template('user_info.html', user_info=user_info)
        # return redirect(url_for('user_info'))
        return redirect(url_for('map'))


# get the oauth session, which also has a requests interface
# (update token handled by signal token_update)
oauth = OAuth(fetch_token=fetch_token)

# ask for activity read
Strava.OAUTH_CONFIG['client_kwargs']['scope'] = 'read,activity:read'
# appp.auth.auth is a blueprint
auth = create_flask_blueprint([Strava], oauth, handle_authorize)
