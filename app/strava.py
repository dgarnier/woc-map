from flask import Blueprint, jsonify, request, current_app, url_for
from flask import send_file, redirect, flash
from flask_login import login_required

# from app.auth import auth.oauth
import app.auth as auth
from app.models import db, admin_required, Athlete, StravaEvent  # , Activity

strava = Blueprint('strava', __name__)

STRAVA_SUBSCRIBE_URL = 'https://www.strava.com/api/v3/push_subscriptions'


def cvsfileify(dict_list, filename):
    import io
    import csv

    output = io.StringIO()
    keys = list(dict_list[0])
    keys.remove('resource_state')
    writer = csv.DictWriter(output, keys,
                            extrasaction='ignore', dialect=csv.excel)
    writer.writeheader()
    writer.writerows(dict_list)
    csv_string = output.getvalue()
    mem = io.BytesIO(csv_string.encode('utf-8'))
    return send_file(
        mem,
        as_attachment=True,
        attachment_filename=filename,
        mimetype='text/csv'
    )


def deauthorize_athlete_from_token(token):
    resp = auth.oauth.strava.request(
        'POST', 'https://www.strava.com/oauth/deauthorize', token=token)
    return resp


@strava.route('/deauthorize/<athlete_id>')
@admin_required
def deauthorize(athlete_id):
    id = int(athlete_id)
    athlete = Athlete.query.get(id)
    current_app.logger.info(f'Deauthorizing {id}:{athlete.firstname}')
    resp = deauthorize_athlete_from_token(athlete.auth_token)
    if resp.ok:
        # if ok..  response returns access token
        # but just access token, not full token
        athlete.deauthorize()
        db.session.commit()
        flash(f'Athlete {athlete} deauthorized.')
    return redirect(url_for('map'))


@strava.route('/avatar/<path:path>')
@login_required
def avatar(path):
    # just pass it on to strava
    url = f'https://strava.com/avatar/{path}'
    resp = auth.oauth.strava.request('GET', url, params=request.args)
    return resp.content


def get_club_info(api=None, params=None, token=None):
    club = current_app.config['STRAVA_CLUB_ID']
    url = f"clubs/{club}/{api}" if api else f"clubs/{club}"
    current_app.logger.info(f'Getting: {url}')
    resp = auth.oauth.strava.request('GET', url, params=params, token=token)
    current_app.logger.info(resp)
    return resp.json()


# expose club api for authorized users
@strava.route('/club/<api>')
@strava.route('/club')
@admin_required
def club_api(api=None):
    current_app.logger.info(f'requested club api {api}')
    if api and api.lower().endswith('.csv'):
        xapi = api.rsplit('.', 1)[0]
        info = get_club_info(xapi, request.args)
        return cvsfileify(info, api)
    else:
        info = get_club_info(api, request.args)
        return jsonify(info)


def get_activity(athelete, activity_id):
    # get an activity from strava
    pass


@strava.before_app_first_request
def check_and_make_subscription():
    callback_url = url_for('strava.webhook', _external=True, _scheme='https')
    sub = check_current_subscription()
    if sub:
        if sub["callback_url"] == callback_url:
            current_app.logger.debug('Got good subscription: ' +
                                     f'{sub["callback_url"]}, ' +
                                     f'updated: {sub["updated_at"]}'
                                     )
            return
        else:
            current_app.logger.debug(f'Unexpected subscription[{sub["id"]}]: '
                                     f'{sub["callback_url"]} != {callback_url}'
                                     )
            if current_app.config.get('FLASK_ENV') == 'production':
                # production server rules!
                delete_subscription(sub["id"])
            else:
                current_app.logger.info("OK! I'm not production server.")
                return
    else:
        current_app.logger.debug(f"No subscription for {callback_url}")

    if 'localhost' not in callback_url:
        # don't be silly
        subscribe(callback_url)


def check_current_subscription():
    params = {
        'client_id': current_app.config['STRAVA_CLIENT_ID'],
        'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
    }
    resp = auth.oauth.strava.request(
        'GET', STRAVA_SUBSCRIBE_URL, withhold_token=True, params=params)
    data = resp.json()
    if data:
        # only one allowed
        return data[0]
    else:
        return None


def delete_subscription(sub_id):
    params = {
        'client_id': current_app.config['STRAVA_CLIENT_ID'],
        'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
    }
    resp = auth.oauth.strava.request(
        'DELETE', STRAVA_SUBSCRIBE_URL+f'/{sub_id}',
        withhold_token=True, params=params)
    current_app.logger.info(f'Subscription delete: {resp}')


def subscribe(callback_url):
    current_app.logger.info('Subscribing to Strava notifications @' +
                            callback_url)
    subscribe_url = 'https://www.strava.com/api/v3/push_subscriptions'
    params = {
        'client_id': current_app.config['STRAVA_CLIENT_ID'],
        'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
        'callback_url': callback_url,
        'verify_token': current_app.config['STRAVA_VERIFY_TOKEN']
        }

    resp = auth.oauth.strava.request('POST', subscribe_url,
                                     withhold_token=True, params=params)
    current_app.logger.info(f'Strava notification subscription; {resp}')


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
    current_app.logger.debug(f'StravaEvent {data}')

    # convert to string
    updates = data.get('updates')
    data['updates'] = str(updates) 
    ev = StravaEvent(**data)
    db.session.add(ev)

    if data['object_type'] == 'activity':
        # we need to handle activites here.
        # FIX ME
        pass
    elif data['object_type'] == 'athlete':
        current_app.logger.info(f"Athlete {id}: {data['updates']}")
        athlete = Athlete.query.get(id)
        athlete.deauthorize()

    db.session.commit()


# handle strava webhooks subscriptions
@strava.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # with a GET, strava is just validating
    if request.method == 'GET':
        current_app.logger.info('Strava callback GET subscription validation')
        mode = request.args.get('hub.mode')
        challenge = request.args.get('hub.challenge')
        token = request.args.get('hub.verify_token')
        if mode == 'subscribe' and len(challenge) > 0 and \
                token == current_app.config['STRAVA_VERIFY_TOKEN']:
            # sweet.. strava cares.
            # respond current_approriately
            return jsonify({'hub.challenge': challenge}), 200
        else:
            return jsonify({'error': 'invalid params'}), 400

    # ok.. now we really can deal with the callback
    # this is a real strava event
    data = request.get_json()
    handle_strava_webhook_event(data)

    return '', 200


# add at end for other modules to grab the models
# can't add sooner or will be circular references
# from current_app import models
