from flask import Blueprint, jsonify, request, current_app, url_for, render_template
from flask import send_file, redirect, flash
import sqlalchemy as sa
# from flask_login import login_required

# from app.auth import auth.oauth
import app.auth as auth
import app.utils as utils
from app.models import db, admin_required, Athlete, StravaEvent  # , Activity

admin = Blueprint('admin', __name__)


def dict_gen(model_query):
    for model in model_query:
        # yield model._asdict()
        yield {c.key: getattr(model, c.key)
               for c in sa.inspect(model).mapper.column_attrs}


@admin.route('/athletes')
@admin_required
def athletes():
    athletes = Athlete.query.all()
    athlete_dicts = dict_gen(athletes)
    ext = request.args.get('ext')

    if ext and ext.lower() in ['csv', 'txt']:
        keys = ['_id', 'firstname', 'lastname', 'city', 'state', 'country',
                'auth_granted', 'club_member', 'club_admin', 'waiver_verified']

        return utils.cvsfileify(athlete_dicts, keys, 'athletes'+ext)
    else:
        return jsonify(list(athlete_dicts))

@admin.route('/')
@admin_required
def index():
    return render_template('admin.html')
