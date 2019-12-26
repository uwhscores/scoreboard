from flask import Flask, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
import logging.handlers
import os

if not os.path.isdir("logs/"):
    os.mkdir("logs")

LOG_FILENAME = 'logs/audit_log'
audit_logger = logging.getLogger('audit_log')
audit_logger.setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=128000, backupCount=0)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

audit_logger.addHandler(handler)

global_limiter = Limiter(
    current_app,
    key_func=get_remote_address,
    global_limits=["1000 per day", "100 per hour"]
)


def create_app(db_path=None, debug=False):
    app = Flask(__name__)
    app.config.from_object(__name__)

    config = dict(
        DATABASE=db_path,
        DEBUG=debug,
        SECRET_KEY="ojgMXp6Rv4n9qKaiAfC48yieA2m-UThR1v6Fuk3d"
    )
    app.config.update(config)

    with app.app_context():
        from scoreboard import views_main, views_admin, views_api_v1, views_cgi
        return app
