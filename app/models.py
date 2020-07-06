from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Athlete(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String)
    firstname = db.Column(db.String)
    lastname = db.Column(db.String)
    city = db.Column(db.String)
    state = db.Column(db.String)
    country = db.Column(db.String)
    profile = db.Column(db.String)
    profile_medium = db.Column(db.String)
    auth_granted = db.Column(db.Boolean)
    access_token = db.Column(db.String)
    access_token_expires_at = db.Column(db.Integer)
    refresh_token = db.Column(db.String)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    subscription_id = db.Column(db.Integer)

    @property
    def is_authenticated(self):
        # override the mixin.. check if revoked elsewhere
        return self.auth_granted


class Activity(db.Model):
    activity_id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athlete.id'))
    name = db.Column(db.String)
    description = db.Column(db.String)
    activity_type = db.Column(db.String)
    comments = db.Column(db.String)
    start_date = db.Column(db.DateTime)
    athlete_name = db.Column(db.String)
    map_polyline = db.Column(db.Text)
    map_summary_polyline = db.Column(db.Text)


class Route(db.Model):
    route_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer)
    event_order = db.Column(db.Integer)
    alternative = db.Column(db.Boolean)
    url = db.Column(db.String)
    tcx = db.Column(db.String)
    distance = db.Column(db.Float)
    climbing = db.Column(db.Float)
    unique = db.Column(db.Float)
    thumb = db.Column(db.BLOB)
    map_polyline = db.Column(db.Text)


class StravaEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(db.Integer)
    obj_asp_type = db.Column(db.String(6))
    athlete_id = db.Column(db.Integer)
    updates = db.Column(db.String)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

