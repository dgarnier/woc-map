from datetime import datetime
from flask import current_app

import geojson
# import geobuf

from sqlalchemy.orm import joinedload
from app.models import (db, Athlete, Activity, get_or_create,
                        Point, Tag, StravaEvent)
from app.utils import hashtags

import app.auth as auth
import app.analysis as analysis
from authlib.integrations.base_client import (InvalidTokenError,
                                              UnsupportedTokenTypeError)

# some python to handle activities.

# these are the drones we are looking for
woctags = set(['wocblm', 'blmwoc', 'blm', 'woc'])


def process_range(first=None, last=None, max_events=100):
    # process a range of events.
    # works well as long as no one "commits"
    # but it's ok.. we can "flush" after an event

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
        if tags.intersection(woctags):
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


def process_athletes(page=1, before=None, after=None, per_page=100):
    try:
        athletes = db.session.query(Athlete).paginate(page=int(page),
                                                      per_page=int(per_page))
    except (TypeError, ValueError):
        return 'Error', 400
    for athlete in athletes.items:
        process_athlete(athlete,  before=before, after=after)
    db.session.commit()
    return 'Done'


def process_athlete(athlete, before=None, after=None):

    params = {}
    if before:
        params['before'] = before
    if after:
        params['after'] = after
    # if page:
    #    params['page'] = page
    # if per_page:
    #    params['per_page'] = per_page

    if isinstance(athlete, int):
        athlete = db.session.query(Athlete).get(athlete)

    auth_token = athlete.auth_token

    try:
        resp = auth.oauth.strava.request('GET', 'athlete/activities',
                                         token=auth_token, params=params)
    except (UnsupportedTokenTypeError, InvalidTokenError):
        current_app.logger.info(
            f'Failed to get Athlete activities for {athlete}:'
            ' Invalid or Revoked Token')
        return "Invalid token."

    if not resp.ok:
        current_app.logger.info(
            f'Athlete: {athlete}; failed to get activities: {resp}')
        return "Invalid response from STRAVA"

    activity_summaries = resp.json()

    for summary in activity_summaries:
        tags = (hashtags(summary['name'])
                .union(hashtags(summary.get('description'))))
        if tags.intersection(woctags):
            if not Activity.query.get(summary['id']):
                save_activity(summary['id'], athlete, commit=False,
                              filter_for_tags=False)

    return 'Done'


def save_activity(activity_id, owner, timestamp=None, commit=True,
                  filter_for_tags=True):
    # get the athlete auth_token so we can get the activity

    if timestamp:
        act = Activity.query.get(activity_id)
        if act and act.last_updated.timestamp() > timestamp:
            current_app.logger.debug("Activity already saved since timestamp.")

            # already updated
            return "Already saved."

    if isinstance(owner, int):
        athlete = db.session.query(Athlete).get(owner)
    else:
        athlete = owner

    auth_token = athlete.auth_token if athlete else None
    if not auth_token:
        current_app.logger.info(
            f'Activity: {activity_id}; no auth for {athlete._id}: {athlete}')
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
        if not tags.intersection(woctags):
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


gRoutes = None


def analyze_activity(activity):
    import polyline
    import numpy as np
    global gRoutes
    if not gRoutes:
        gRoutes = analysis.read_routes_numpy()

    if isinstance(activity, int):
        activity = Activity.query.get(activity)

    pl = activity.map_polyline
    if not pl:
        pl = activity.map_summary_polyline
    if not pl:
        return

    pts = np.array(polyline.decode(activity.map_polyline))[:, (1, 0)]

    current_app.logger.info(f'Analysing {activity}')
    d2r, rtnums, deltas = analysis.activity_first_pass(pts, gRoutes)
    segs, on_route = analysis.activity_segment(pts, rtnums, d2r, deltas)
    on_route = int(on_route)

    results = {
        'coordinates': pts,
        'route_nums': rtnums,
        'dist_to_rtes': d2r,
        'deltas': deltas,
        'segments': segs
        }

    current_app.logger.info(f'{activity}: {on_route/1000.} of '
                            f'{activity.distance/1000.} (km) on route.')

    activity.on_course = int(on_route)
    activity.analysis = results
    db.session.flush()


def analyze_activities(page=1, before=None, after=None, per_page=100):
    try:
        activities = db.session.query(Activity).paginate(
            page=int(page), per_page=int(per_page))
    except (TypeError, ValueError):
        return 'Error', 400
    for activity in activities.items:
        analyze_activity(activity)

    db.session.commit()
    return 'Done'


def activity_to_geojson_features(activity, collect=True):
    import numpy as np
    from rdp import rdp

    # global gRoutes
    # if not gRoutes:
    #     gRoutes = analysis.read_routes_numpy()
    rt_names = analysis.route_names()

    if isinstance(activity, int):
        activity = (Activity.query
                    .options(joinedload(Activity.athlete))
                    .get(activity))

    if not (activity and activity.analysis):
        return []

    segments = activity.analysis['segments']
    rts = set([s['route_num'] for s in segments if s['route_num'] > 0] + [0])
    pls = {rt: {'distance': 0, 'polystring': []} for rt in rts}
    for s in activity.analysis.get('segments'):
        # Ramer-Douglas-Peucker reduction (epsilon=?) roughly 30m
        pts = rdp(s['coordinates'], epsilon=.0003)
        if pts.shape[0] < 2:    # ignore 1 point lines
            continue

        rt = s['route_num']
        if rt < 0:
            rt = 0

        pls[rt]['polystring'].append(pts)
        pls[rt]['distance'] += s['distance']

    features = []
    for rtn, pl in pls.items():
        mcoords = pl['polystring']
        if not mcoords:
            continue
        bbox = [
            np.amin([np.amin(coords[:, 0]) for coords in mcoords]),
            np.amin([np.amin(coords[:, 1]) for coords in mcoords]),
            np.amax([np.amax(coords[:, 0]) for coords in mcoords]),
            np.amax([np.amax(coords[:, 1]) for coords in mcoords]),
        ]
        props = {
            'name': activity.name,
            'avatar': activity.athlete.profile_medium,
            'id': activity._id,
            'bbox': bbox,
            'start_date': activity.start_date.timestamp(),
            'route': (rt_names[rtn - 1]
                      if rtn > 0 else 'off'),
            'distance': pl['distance'],
            'on_route': bool(rtn > 0)
        }
        # convert for geojson
        pts = [coords.tolist() for coords in mcoords]
        geometry = geojson.MultiLineString(coordinates=pts, precision=5)  # 1m
        ft = geojson.Feature(geometry=geometry, properties=props)
        features.append(ft)

    if collect:
        return geojson.FeatureCollection(features)

    return features


def activities_to_geojson(activities=None, filename=None):

    if not activities:
        activities = db.session.query(Activity)
        activities = activities.options(joinedload(Activity.athlete))

    current_app.logger.info('')

    feature_list = []
    for i, activity in enumerate(activities):
        current_app.logger.info(f'Making GEOJSON LS for activity [{i}]: '
                                f'{activity._id}: {activity.name}')
        features = activity_to_geojson_features(activity, collect=False)
        feature_list.extend(features)

    fcollection = geojson.FeatureCollection(feature_list)

    if filename:
        with open(filename, 'w') as fp:
            geojson.dump(fcollection, fp)
        return 'Done.'
        
    return fcollection
