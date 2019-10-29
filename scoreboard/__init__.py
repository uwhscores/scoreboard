import os
# import sqlite3
import logging
import logging.handlers
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask
#, request, session, g, redirect, url_for, abort, \
#	render_template, flash, jsonify, json


app = Flask(__name__)
app.config.from_object(__name__)

db_path = None
#import pdb; pdb.set_trace()
db_path = os.getenv("SCOREBOARD_DB")

if not db_path:
    db_path = os.path.join(app.root_path, 'scores.db')

config = dict(
    DATABASE= db_path,
    DEBUG=True,
    SECRET_KEY='testkey'
    # USERNAME='admin',
    # PASSWORD='default',
    # TID='5'
)
app.config.update(config)

#app.config.from_envvar('SCOREBOARD_SETTINGS', silent=True)

global_limiter = Limiter(
    app,
    key_func=get_remote_address,
    #global_limits=["1000 per day", "100 per hour"]
    global_limits=[]
)

if not os.path.isdir("logs/"):
    os.mkdir("logs")

LOG_FILENAME = 'logs/audit_log'
audit_logger = logging.getLogger('audit_log')
audit_logger.setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
              LOG_FILENAME, maxBytes=128000, backupCount=0)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

audit_logger.addHandler(handler)


#from app import functions, tournament, models, views_main, views_admin, views_api_v1
from scoreboard import views_main, views_admin, views_api_v1
    #views_admin, views_static
