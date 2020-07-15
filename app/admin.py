from flask import Blueprint, jsonify, request, current_app, url_for
from flask import send_file, redirect, flash
from flask_login import login_required

# from app.auth import auth.oauth
import app.auth as auth
from app.models import db, admin_required, Athlete, StravaEvent  # , Activity

admin = Blueprint('admin', __name__)
