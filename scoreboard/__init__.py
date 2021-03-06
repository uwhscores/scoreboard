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
    key_func=get_remote_address,
    default_limits=["200000 per day", "10000 per hour"]
)


def create_app(db_path=None, debug=False, testing=False):
    app = Flask(__name__)
    app.config.from_object(__name__)

    config = dict(
        DATABASE=db_path,
        DEBUG=debug,
        TESTING=testing,
        SECRET_KEY="ojgMXp6Rv4n9qKaiAfC48yieA2m-UThR1v6Fuk3d"
    )
    app.config.update(config)
    global_limiter.init_app(app)

    with app.app_context():
        from scoreboard import views_main, views_admin, views_api_v1, views_cgi
        return app
