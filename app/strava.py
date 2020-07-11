from flask import Blueprint, jsonify, request, current_app, url_for

from app.auth import oauth
from app.models import db, Athlete, Activity

strava_bp = Blueprint('strava', __name__)

STRAVA_SUBSCRIBE_URL = 'https://www.strava.com/api/v3/push_subscriptions'


def get_activity(athelete, activity_id):
    # get an activity from strava
    pass


@strava_bp.before_app_first_request
def check_and_make_subscription():
    callback_url = url_for('strava.callback', _external=True)
    sub = check_current_subscription()
    if sub:
        if sub["callback_url"] == callback_url:
            current_app.logger.info('Got good subscription: ' +
                                    f'{sub["callback_url"]}, ' +
                                    f'updated: {sub["updated_at"]}'
                                    )
            return
        else:
            current_app.logger.info('Unexpected subscription: ' +
                                    f'{sub["callback_url"]} != {callback_url}'
                                    )
            if current_app.config.get('FLASK_ENV') == 'production':
                # production server rules!
                delete_subscription(sub["id"])
            else:
                current_app.logger.info("OK! I'm not production server.")
                return
    if 'localhost' not in callback_url:
        # don't be silly
        subscribe(callback_url)


def check_current_subscription():
    params = {
        'client_id': current_app.config['STRAVA_CLIENT_ID'],
        'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
    }
    resp = oauth.strava.request(
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
    resp = oauth.strava.request(
        'DELETE', STRAVA_SUBSCRIBE_URL+f'/{sub_id}',
        withhold_token=True, params=params)
    current_app.logger.info(f'Subscription delete: {resp}')


def subscribe(callback_url):
    current_app.logger.info('Subscribing to Strava notifications.')
    subscribe_url = 'https://www.strava.com/api/v3/push_subscriptions'
    params = {
        'client_id': current_app.config['STRAVA_CLIENT_ID'],
        'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
        'callback_url': callback_url,
        'verify_token': current_app.config['STRAVA_VERIFY_TOKEN']
        }

    resp = oauth.strava.request('POST', subscribe_url,
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
    current_app.logger.info('StravaEvent {data}')


# handle strava webhooks subscriptions
@strava_bp.route('/callback', methods=['GET', 'POST'])
def callback():
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
    data = request.get_json(force=True)
    handle_strava_webhook_event(data)

    return '', 200


# add at end for other modules to grab the models
# can't add sooner or will be circular references
# from current_app import models
