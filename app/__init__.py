import os
from flask import Flask, request, session, g, redirect, url_for, abort, \
	render_template, flash, jsonify, json
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

from app import functions, tournament, models, views_main, views_admin
	#views_admin, views_static
