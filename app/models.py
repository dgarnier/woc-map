from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin


class SQLA(SQLAlchemy):
    def init_app(self, app):
        super(SQLA, self).init_app(app)

        @app.login_manager.user_loader
        def load_user(user_id):
            return Athlete.query.get(int(user_id))


db = SQLA()


class Athlete(db.Model, UserMixin):
    "Strava Athelete and user"
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
    last_activity_check = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_authenticated(self):
        # override the mixin.. check if revoked elsewhere
        return self.auth_granted

    @property
    def auth_token(self):
        return dict(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_at=self.access_token_expires_at
        ) if self.auth_granted else None

    @auth_token.setter
    def auth_token(self, token):
        self.auth_granted = True
        self.access_token = token['access_token']
        self.refresh_token = token['refresh_token']
        self.access_token_expires_at = int(token['expires_at'])
        self.last_updated = datetime.utcnow()
        db.session.commit()

    @auth_token.deleter
    def auth_token(self):
        self.auth_granted = False
        db.session.commit()

    def __repr__(self):
        return f'<Athlete: {self.id} {self.username}>'


class Point(object):
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon

    def __composite_values__(self):
        return self.lat, self.lon

    def __repr__(self):
        return "Point(lat=%r, lon=%r)" % (self.lat, self.lon)

    def __eq__(self, other):
        return isinstance(other, Point) and \
            other.lat == self.lat and \
            other.lon == self.lon

    def __ne__(self, other):
        return not self.__eq__(other)


class Activity(db.Model):
    activity_id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athlete.id'))
    athlete = db.relationship('Athlete',
                              backref=db.backref('activities', lazy=True))
    name = db.Column(db.String)
    description = db.Column(db.String)
    activity_type = db.Column(db.String)
    start_date = db.Column(db.DateTime)
    map_polyline = db.Column(db.Text)
    map_summary_polyline = db.Column(db.Text)
    distance = db.Column(db.Integer)
    moving_time = db.Column(db.Integer)
    elapsed_time = db.Column(db.Integer)
    total_elevation_gain = db.Column(db.Integer)
    start_lat = db.Column(db.Integer)
    start_lon = db.Column(db.Integer)
    end_lat = db.Column(db.Integer)
    end_lon = db.Column(db.Integer)
    start_latlon = db.composite(Point, start_lat, start_lon)
    end_latlon = db.composite(Point, end_lat, end_lon)
    trainer = db.Column(db.Boolean)
    commute = db.Column(db.Boolean)
    manual = db.Column(db.Boolean)
    private = db.Column(db.Boolean)
    flagged = db.Column(db.Boolean)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class Route(db.Model):
    route_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer)
    event_order = db.Column(db.Integer)
    alternative = db.Column(db.Boolean)
    url = db.Column(db.String)
    tcx = db.Column(db.String)
    distance = db.Column(db.Float)
    total_elevation_gain = db.Column(db.Float)
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
