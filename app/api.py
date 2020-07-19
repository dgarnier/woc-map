# this only returns json data for use in javascript displays
from datetime import datetime
from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app.models import db, admin_required, Athlete, Activity, get_or_create, Point
from app.utils import hashtags
from app.auth import oauth


api = Blueprint('api', __name__)


@api.route('/polylines')
@login_required
def polylines():
    activities = current_user.activities
    activity_data = [{'id': activity._id,
                      'name': activity.name,
                      'polyline': activity.map_polyline
                      } for activity in activities]
    return jsonify(activity_data)

