from functools import wraps
from datetime import datetime
from flask import current_app
from flask_login import UserMixin, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound


class SQLA(SQLAlchemy):
    def init_app(self, app):
        super(SQLA, self).init_app(app)

        @app.login_manager.user_loader
        def load_user(user_id):
            return Athlete.query.get(int(user_id))


db = SQLA()


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_app.config.get('LOGIN_DISABLED'):
            return func(*args, **kwargs)
        elif not (current_user.is_authenticated and
                  current_user.is_admin):
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


class Athlete(db.Model, UserMixin):
    "Strava Athelete and user"
    _id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(256))
    firstname = db.Column(db.String(256))
    lastname = db.Column(db.String(256))
    city = db.Column(db.String(256))
    state = db.Column(db.String(256))
    country = db.Column(db.String(256))
    profile = db.Column(db.String(256))
    profile_medium = db.Column(db.String(256))
    auth_granted = db.Column(db.Boolean)
    access_token = db.Column(db.String(8192), nullable=True)
    access_token_expires_at = db.Column(db.Integer)
    refresh_token = db.Column(db.String(8192), nullable=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, onupdate=datetime.utcnow)
    last_activity_check = db.Column(db.DateTime)
    club_member = db.Column(db.Boolean, default=False)
    club_admin = db.Column(db.Boolean, default=False)
    wavier_verified = db.Column(db.Boolean, default=False)
    details = db.Column(db.JSON, nullable=True)

    def get_id(self):
        return self._id

    @property
    def is_authenticated(self):
        # override the mixin.. check if revoked elsewhere
        return self.auth_granted

    @property
    def is_admin(self):
        # override the mixin.. check if revoked elsewhere
        return self.club_admin

    @property
    def auth_token(self):
        return dict(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_at=self.access_token_expires_at
        )
        # if self.auth_granted else None

    @auth_token.setter
    def auth_token(self, token):
        if isinstance(token, dict):
            self.auth_granted = True
            self.access_token = token.get('access_token')
            self.refresh_token = token.get('refresh_token')
            self.access_token_expires_at = int(token.get('expires_at'))
            self.last_updated = datetime.utcnow()
        else:
            if token:
                current_app.logger.debug(f'unexpected token: {token}')
            else:
                self.deauthorize()

    def deauthorize(self):
        self.auth_granted = False
        self.access_token = None
        self.refresh_token = None

    def __repr__(self):
        return f'<Athlete {self._id}: {self.firstname} {self.lastname}>'

    def __str__(self):
        return f'{self.firstname} {self.lastname}'


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


# many to many needs association table
act_tag_assoc_table = db.Table('act_tag_assoc', db.Model.metadata,
                               db.Column('tag_id', db.String(32),
                                         db.ForeignKey('tag._id')),
                               db.Column('activity_id', db.BigInteger,
                                         db.ForeignKey('activity._id'))
                               )


class Tag(db.Model):
    _id = db.Column(db.String(32), primary_key=True)
    activities = db.relationship('Activity',
                                 secondary=act_tag_assoc_table)


class Activity(db.Model):
    _id = db.Column(db.BigInteger, primary_key=True)
    athlete_id = db.Column(db.BigInteger, db.ForeignKey('athlete._id'),
                           nullable=False)
    athlete = db.relationship('Athlete',
                              backref=db.backref('activities', lazy=True))
    tags = db.relationship('Tag', secondary=act_tag_assoc_table)
    name = db.Column(db.Text())
    description = db.Column(db.Text, nullable=True)
    # tags = db.Column(db.String)
    activity_type = db.Column(db.String(32))
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
    details = db.Column(db.JSON, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class Route(db.Model):
    _id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer)
    event_order = db.Column(db.Integer)
    alternative = db.Column(db.Boolean)
    url = db.Column(db.String(1024))
    tcx = db.Column(db.Text)
    distance = db.Column(db.Float)
    total_elevation_gain = db.Column(db.Float)
    unique = db.Column(db.Float)
    thumb = db.Column(db.BLOB)
    map_polyline = db.Column(db.Text)


class StravaEvent(db.Model):
    _id = db.Column(db.BigInteger, primary_key=True)
    object_id = db.Column(db.BigInteger)
    aspect_type = db.Column(db.String(10))
    object_type = db.Column(db.String(10))
    owner_id = db.Column(db.BigInteger)
    updates = db.Column(db.TEXT)
    event_time = db.Column(db.BigInteger)
    subscription_id = db.Column(db.BigInteger)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


def get_or_create(model, defaults=None, **kwargs):
    """
    Get or create a model instance while preserving integrity.
    uses same as django.. returns if it had to create
    """
    try:
        return db.session.query(model).filter_by(**kwargs).one(), False
    except NoResultFound:
        if defaults is not None:
            kwargs.update(defaults)
        try:
            with db.session.begin_nested():
                instance = model(**kwargs)
                db.session.add(instance)
                return instance, True
        except IntegrityError:
            return db.session.query(model).filter_by(**kwargs).one(), False
