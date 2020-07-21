from datetime import datetime
from flask import current_app

from app.models import (db, Athlete, Activity, get_or_create,
                        Point, Tag, StravaEvent)
from app.utils import hashtags

import app.auth as auth
from authlib.integrations.base_client import InvalidTokenError

# some python to handle activities.


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
        process_event(event, commit=False)
        i = i+1
        if i >= int(max_events):
            first = event._id
            break
    db.session.commit()
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
    if ev.object_type == 'activity' and ev.aspect_type == 'create':
        exists = db.session.query(db.session.query(Activity)
                                  .filter_by(_id=ev.object_id)
                                  .exists()).scalar()
        if exists:
            current_app.logger.debug(f"Already saved: {ev._id}, "
                                     f"Activity: {ev.object_id}")
            return "Already saved."
        return save_activity(ev.object_id, ev.owner_id,
                             timestamp=ev.timestamp, commit=commit)
    else:
        current_app.logger.debug(f"Ignoring event: {ev._id}")
    return "Ignored."


def check_athlete(athlete, before=None, after=None, page=None, per_page=None):

    params = {}
    if before:
        params['before'] = before
    if after:
        params['after'] = after
    if page:
        params['page'] = page
    if per_page:
        params['per_page'] = per_page

    if isinstance(athlete, int):
        athlete = db.session.query(Athlete).get(athlete)

    auth_token = athlete.auth_token

    try:
        resp = auth.oauth.strava.request('GET', f'athlete/activities',
                                         token=auth_token, params=params)
    except InvalidTokenError:
        current_app.logger.info(
            f'Activity: {activity_id}; failed to GET: InvalidTokenError!')
        return "Invalid token."

    if not resp.ok:
        current_app.logger.info(
            f'Athlete: {athlete._id}; failed to get activities: {resp}')
        return "Invalid response from STRAVA"

    activity_summaries = resp.json()

    for summary in activity_summaries:
        pass


def save_activity(activity_id, owner_id, timestamp=None, commit=True,
                  filter_for_tags=True):
    # get the athlete auth_token so we can get the activity

    if timestamp:
        act = Activity.query.get(activity_id)
        if act and act.last_updated.timestamp() > timestamp:
            current_app.logger.debug("Activity already saved since timestamp.")

            # already updated
            return "Already saved."

    athlete = Athlete.query.get(int(owner_id))
    auth_token = athlete.auth_token if athlete else None
    if not auth_token:
        current_app.logger.info(
            f'Activity: {activity_id}; no auth for {owner_id}: {athlete}')
        return "No auth token."

    # params = {'include_all_efforts': False}
    params = None   # this returns less efforts
    try:
        resp = auth.oauth.strava.request('GET', f'activities/{activity_id}',
                                         token=auth_token, params=params)
    except InvalidTokenError:
        current_app.logger.info(
            f'Activity: {activity_id}; failed to GET: InvalidTokenError!')
        return "Invalid token."

    if not resp.ok:
        current_app.logger.info(
            f'Activity: {activity_id}; failed to GET: {resp}')
        return "Invalid response from STRAVA"

    data = resp.json()

    current_app.logger.debug(f"Got activity {activity_id} from STRAVA:"
                             f" {data['name']}")
    # current_app.logger.debug(f"efforts {len(data['segment_efforts'])}")

    if filter_for_tags:
        tags = hashtags(data['name']).union(hashtags(data.get('description')))
        if not tags.intersection(set(['wocblm', 'blmwoc', 'blm', 'woc'])):
            current_app.logger.info(f'Activity: {activity_id}; '
                                    f'had no matching hashtag: {data["name"]}')
            return "Not a WOC activity."

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
        setattr(activity, attr, data.get(attr))

    activity.start_date = datetime.strptime(data['start_date'],
                                            "%Y-%m-%dT%H:%M:%SZ")
    activity.map_polyline = data["map"].get("polyline")
    activity.map_summary_polyline = data["map"].get("summary_polyline")
    if data.get('start_latlng'):
        activity.start_latlon = Point(*data['start_latlng'])
    if data.get('end_latlng'):
        activity.end_latlon = Point(*data['end_latlng'])
    activity.activity_type = data['type']

    activity.athlete = athlete

    activity.details = data

    htags = hashtags(data['name']).union(hashtags(data.get('description')))
    current_app.logger.debug(f'tags {htags}')
    for hashtag in htags:
        tag, _ = get_or_create(Tag, _id=hashtag)
        activity.tags.append(tag)

    if commit:
        db.session.commit()
    else:
        db.session.flush()

    return activity
