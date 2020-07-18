from flask import current_app

from app.models import db, Athlete, Activity
from app.utils import hashtags
from app.auth import oauth

# some python to handle activities.


def save_activity(activity_id, owner_id):
    # get the athlete auth_token so we can get the activity
    athlete = Athlete.query.get(int(owner_id))
    auth_token = athlete.auth_token if athlete else None
    if not auth_token:
        current_app.logger.info(
            f'Activity: {activity_id}; no auth for {owner_id}: {athlete}')
        return

    resp = oauth.strava.request('GET', f'activities/{activity_id}',
                                token=auth_token, params={'include_all_efforts': None})
    if not resp.ok:
        current_app.logger.info(
            f'Activity: {activity_id}; failed to GET: {resp}')
        return

    data = resp.json()

    activity = Activity.query.get(int(data['id']))
    if not activity:
        data['_id'] = int(data[id])
        activity = Activity(**data)
        db.session.add(activity)

    
    activity = Ac



    
