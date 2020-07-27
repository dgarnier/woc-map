
import polyline
import geojson
from datetime import datetime
'''
from active_alchemy import ActiveAlchemy


db = ActiveAlchemy('mysql+pymysql://' +
                   '***REMOVED***_user:***REMOVED***@wheelsofchange.us' +
                   '/***REMOVED***')

'''
from sqlalchemy import create_engine
from sqlalchemy.orm import (sessionmaker, relationship, backref, composite,
                            joinedload)  # , lazyload)
from sqlalchemy.ext.declarative import declarative_base
import sqlalchemy as db

SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://' + \
    '***REMOVED***_user:***REMOVED***@wheelsofchange.us' + \
    '/***REMOVED***'


# ----- This is related code -----
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)
Base = declarative_base()
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
Session.configure(bind=engine)
session = Session()
# ----- This is related code -----


class Athlete(Base):
    "Strava Athelete and user"
    __tablename__ = 'athlete'
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

    @property
    def avatar_url(self):
        if self.profile:
            return self.profile
        else:
            i1 = self.firstname[0] if self.firstname else ''
            i2 = self.lastname[0] if self.lastname else ''
            return "https://ui-avatars.com/api/?bold=true&size=70" + \
                f"&name={i1}%20{i2}&background=0D8ABC&color=fff"

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
                # current_app.logger.debug(f'unexpected token: {token}')
                pass
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
act_tag_assoc_table = db.Table('act_tag_assoc', Base.metadata,
                               db.Column('tag_id', db.String(32),
                                         db.ForeignKey('tag._id')),
                               db.Column('activity_id', db.BigInteger,
                                         db.ForeignKey('activity._id'))
                               )


class Tag(Base):
    __tablename__ = 'tag'
    _id = db.Column(db.String(32), primary_key=True)
    activities = relationship('Activity',
                              secondary=act_tag_assoc_table)


class Activity(Base):
    __tablename__ = 'activity'
    _id = db.Column(db.BigInteger, primary_key=True)
    athlete_id = db.Column(db.BigInteger, db.ForeignKey('athlete._id'),
                           nullable=False)
    athlete = relationship('Athlete',
                           backref=backref('activities', lazy=True))
    tags = relationship('Tag', secondary=act_tag_assoc_table)
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
    start_latlon = composite(Point, start_lat, start_lon)
    end_latlon = composite(Point, end_lat, end_lon)
    trainer = db.Column(db.Boolean)
    commute = db.Column(db.Boolean)
    manual = db.Column(db.Boolean)
    private = db.Column(db.Boolean)
    flagged = db.Column(db.Boolean)
    details = db.Column(db.JSON, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class Route(Base):
    __tablename__ = 'route'
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


class StravaEvent(Base):
    __tablename__ = 'strava_event'
    _id = db.Column(db.BigInteger, primary_key=True)
    object_id = db.Column(db.BigInteger)
    aspect_type = db.Column(db.String(10))
    object_type = db.Column(db.String(10))
    owner_id = db.Column(db.BigInteger)
    updates = db.Column(db.TEXT)
    event_time = db.Column(db.BigInteger)
    subscription_id = db.Column(db.BigInteger)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


def activities_to_geojson():
    # colors = ['green', 'red', 'brown', '#0000CC', 'magenta']

    i = 0
    featurelist = []
    activities = session.query(Activity)
    activities = activities.options(joinedload(Activity.athlete))
    for activity in activities:
        # act_id = activity._id
        # ath_id = activity.athlete_id
        # could put in the bounding box (sw to ne)
        # ("bbox": [west, sout, east, north])

        msp = activity.map_summary_polyline or activity.map_polyline
        if not msp:
            continue
        coords = polyline.decode(msp)
        north, east = coords[0]
        south, west = coords[0]
        for coord in coords:
            north = coord[0] if coord[0] > north else north
            south = coord[0] if coord[0] < south else south
            east = coord[1] if coord[1] > east else east
            west = coord[1] if coord[1] < west else west

        props = {
                 'name': activity.name,
                 'avatar': activity.athlete.avatar_url,
                 'id': activity._id,
                 'bbox': [west, south, east, north],
                 'start_date': activity.start_date.timestamp(),
                }

        coorflip = [[lg, lt] for lt, lg in coords]
        geo_ls = geojson.LineString(coorflip)
        feature = geojson.Feature(geometry=geo_ls, properties=props)
        featurelist.append(feature)
        i += 1
        print(i, props['name'])

    fcollection = geojson.FeatureCollection(featurelist)

    return fcollection


gjson = activities_to_geojson()

gjstr = geojson.dumps(gjson)

with open('app/static/routes/activities_raw.geojson', 'w') as f:
    f.write(gjstr)
