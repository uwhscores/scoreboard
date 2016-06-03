import os
from flask import Flask, request, session, g, redirect, url_for, abort, \
	render_template, flash, jsonify, json
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3

app = Flask(__name__)
app.config.from_object(__name__)

app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'scores.db'),
	DEBUG=True,
	SECRET_KEY='testkey',
	USERNAME='admin',
	PASSWORD='default',
	TID='5'
))

app.config.from_envvar('SCOREBOARD_SETTINGS', silent=True)

global_limiter = Limiter(
    app,
    key_func=get_remote_address,
    #global_limits=["1000 per day", "100 per hour"]
	global_limits=[]
)

from app import functions, tournament, models, views_main, views_admin, views_api_v1
	#views_admin, views_static
