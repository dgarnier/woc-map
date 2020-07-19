from datetime import datetime
from flask import current_app, Blueprint, jsonify
from flask_login import login_required, current_user

from app.models import (db, Athlete, Activity, get_or_create, 
                        Point, Tag, StravaEvent)
from app.utils import hashtags

import app.auth as auth
from authlib.integrations.base_client import InvalidTokenError

# some python to handle activities.

activities = Blueprint('activities', __name__)


def process_range(first=None, last=None, max_events=100):

    events = StravaEvent.query
    if first:
        events = events.filter(StravaEvent._id >= int(first))
    if last:
        events = events.filter(StravaEvent._id <= int(last))

    events = events.order_by(StravaEvent._id.desc())

    i = 0
    for event in events:
        if i == 0:
            last = event._id
        process_event(event)
        i = i+1
        if i >= int(max_events):
            first = event._id
            break
    return dict(first=first, last=last)


def process_event_id(event_id):
    # process a single event from the event database
    ev = StravaEvent.query.get(event_id)
    if not ev:
        current_app.logger.debug(f"Couldn't find event {event_id}")
        return f"No event {event_id}"
    return process_event(ev)


def process_event(ev, commit=True):
    # process a single event from the event database

    if ev.object_type == 'activity' and ev.aspect_type == 'update':
        tags = hashtags(ev.updates)
        if tags.intersection(set(['wocblm', 'blmwoc', 'blm', 'woc'])):
            ev.timestamp = datetime.now()
            ret = save_activity(ev.object_id, ev.owner_id, 
                            timestamp=ev.event_time,
                            commit=commit)
            if ret is None:
                return "Didn't save."
            return "Saved."
        else:
            current_app.logger.debug(f"Activity not WOC: {ev._id}")
            return "Not interested."
    else:
        current_app.logger.debug(f"Ignoring event: {ev._id}")
    return "Ignored."


def save_activity(activity_id, owner_id, timestamp=None, commit=True):
    # get the athlete auth_token so we can get the activity

    if timestamp:
        act = Activity.query.get(activity_id)
        if act and act.last_updated.timestamp() > timestamp:
            current_app.logger.debug(f"Activity already saved since timestamp.")

            # already updated
            return

    athlete = Athlete.query.get(int(owner_id))
    auth_token = athlete.auth_token if athlete else None
    if not auth_token:
        current_app.logger.info(
            f'Activity: {activity_id}; no auth for {owner_id}: {athlete}')
        return

    # params = {'include_all_efforts': False}
    params = None   # this returns less efforts
    try:
        resp = auth.oauth.strava.request('GET', f'activities/{activity_id}',
                                        token=auth_token, params=params)
    except InvalidTokenError:
        current_app.logger.info(
            f'Activity: {activity_id}; failed to GET: InvalidTokenError!')
        return

    if not resp.ok:
        current_app.logger.info(
            f'Activity: {activity_id}; failed to GET: {resp}')
        return

    data = resp.json()

    current_app.logger.debug(f"Got activity {activity_id} from STRAVA: {data['name']}")
    # current_app.logger.debug(f"efforts {len(data['segment_efforts'])}")

    activity, created = get_or_create(Activity, _id=data['id'])

    save_keys = ["name",
                 "description",
                 "elapsed_time",
                 "moving_time",
                 "total_elevation_gain",
                 "trainer",
                 "distance",
                 "commute",
                 "manual",
                 "private",
                 "flagged"]

    for attr in save_keys:
        setattr(activity, attr, data[attr])

    activity.start_date = datetime.strptime(data['start_date'],
                                            "%Y-%m-%dT%H:%M:%SZ")
    activity.map_polyline = data["map"]["polyline"]
    activity.map_summary_polyline = data["map"]["summary_polyline"]
    activity.start_latlon = Point(*data['start_latlng'])
    activity.end_latlon = Point(*data['end_latlng'])
    activity.activity_type = data['type']

    activity.athlete = athlete

    activity.details = data

    htags = hashtags(data['name']).union(hashtags(data['description']))
    current_app.logger.debug(f'tags {htags}')
    for hashtag in htags:
        tag, _ = get_or_create(Tag, _id=hashtag)
        activity.tags.append(tag)

    if commit:
        db.session.commit()

    return activity

