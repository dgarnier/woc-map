from flask import (Blueprint, jsonify, request, current_app, url_for,
                   render_template, redirect, abort)
from flask_login import current_user
from flask_table import Table, Col, DatetimeCol
from flask_wtf import FlaskForm
# from flask_wtf.csrf import CSRFProtect
from wtforms import IntegerField
from wtforms.widgets import SubmitInput

import sqlalchemy as sa
from sqlalchemy.sql import func, distinct
from sqlalchemy.orm import joinedload

# from app.auth import auth.oauth
# import app.auth as auth
import app.utils as utils
from app.activities import (save_activity, process_event_id, process_range,
                            process_athletes)
from app.models import db, admin_required, Athlete, StravaEvent, Activity

admin = Blueprint('admin', __name__)


def dict_gen(model_query):
    for model in model_query:
        # yield model._asdict()
        yield {c.key: getattr(model, c.key)
               for c in sa.inspect(model).mapper.column_attrs}


@admin.route('/fetch_activity/<int:activity_id>')
@admin_required
def fetch_activity(activity_id):
    owner_id = request.args.get('owner') or current_user._id
    timestamp = request.args.get('timestamp')
    save_activity(activity_id, owner_id, timestamp=timestamp)
    return redirect(url_for('main.map', activity=activity_id))


@admin.route('/check_event/<int:event_id>')
@admin_required
def check_event(event_id):
    if not event_id:
        abort(404)
    return process_event_id(int(event_id))


@admin.route('/check_events')
@admin_required
def check_events():
    prange = process_range(**request.args)
    return jsonify(prange)

@admin.route('/check_athletes')
@admin_required
def check_athletes():
    return process_athletes(**request.args)


@admin.route('/athletes')
@admin_required
def athletes():
    
    athletes = Athlete.query.all()
    athlete_dicts = dict_gen(athletes)
    ext = request.args.get('ext')

    if ext and ext.lower() in ['csv', 'txt']:
        keys = ['_id', 'firstname', 'lastname', 'city', 'state', 'country',
                'auth_granted', 'club_member', 'club_admin', 'waiver_verified']

        return utils.cvsfileify(athlete_dicts, keys, 'athletes')
    else:
        return jsonify(list(athlete_dicts))


@admin.route('/activities')
@admin_required
def activities():
    # need to limit this
    activities = (db.session.query(Activity)
                  .options(joinedload(Activity.athlete))
                  .order_by(Activity.athlete_id)
                  )

    keys = ['Activity',
            'Type',
            'Start Date',
            'Athlete ID',
            'First Name',
            'Last Name',
            'Hashtag',
            'Title'
            ]

    def activity_dict_gen(activities):
        for activity in activities:
            row = {
                'Activity': activity._id,
                'Type': activity.activity_type,
                'Start Date': activity.start_date.timestamp(),
                'Athlete ID': activity.athlete_id,
                'First Name': activity.athlete.firstname,
                'Last Name': activity.athlete.lastname,
                'Hashtags': " ".join([tag for tag in activity.tags]),
                'Title': activity.name
            }
            yield row

    activity_dicts = activity_dict_gen(activities)

    ext = request.args.get('ext')

    if ext and ext.lower() in ['csv', 'txt']:
        return utils.cvsfileify(activity_dicts, keys, 'activities')
    else:
        return jsonify(list(activity_dicts))


class AthleteTable(Table):
    _id = Col("Strava ID")
    username = Col("User Name")
    firstname = Col("First Name")
    lastname = Col("Last Name")
    city = Col("City")
    state = Col("State")
    auth_granted = Col("Auth Granted")
    club_member = Col("Club Member")
    last_updated = DatetimeCol("Last Updated")


class CheckEventForm(FlaskForm):
    last = IntegerField('Last Event')
    first = IntegerField('First Event')
    max_check = IntegerField('Max to check')
    do_it = SubmitInput('Go')


@admin.route('/')
@admin_required
def index():
    stats = {}
    stats['good_athletes'] = db.session.query(Athlete.auth_granted).\
        filter(Athlete.auth_granted).count()
    stats['incomplete'] = db.session.query(Athlete.auth_granted).\
        filter(Athlete.auth_granted == 0).count()
    stats['wocblm_updates'] = db.session.query(StravaEvent.updates).\
        filter(StravaEvent.updates.match('#WOCBLM')).count()
    stats['saved activities'] = db.session.query(Activity._id).count()

    q = db.session.query(func.sum(Activity.moving_time)
                         .label("total_moving_time"),
                         func.sum(Activity.distance)
                         .label("total_distance"),
                         func.count(distinct(Activity.athlete_id))
                         .label("distinct athletes")
                         )
    result = q.first()

    current_app.logger.info(f'{result}')
    stats['athletes contributing'] = result[2]
    stats['moving time (hours)'] = "{:.1f}".format(int(result[0])/3600)
    stats['total distance (km)'] = "{:.1f}".format(int(result[1])/1000)
    stats['total distance (miles)'] = "{:.1f}".format(int(result[1])/1609.34)

    incomplete = Athlete.query.filter(Athlete.auth_granted == 0)
    incomplete_table = AthleteTable(incomplete)

    return render_template('admin.html', stats=stats,
                           incomplete_table=incomplete_table)
