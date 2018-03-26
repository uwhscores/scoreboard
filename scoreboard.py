import os
from app import app
from werkzeug.contrib.fixers import ProxyFix

app.wsgi_app = ProxyFix(app.wsgi_app)


if not "SCOREBOARD_DB" in os.environ:
    os.environ["SCOREBOARD_DB"] = "app/scores.db"

if __name__ == '__main__':
    # app.run(host='0.0.0.0')
    app.run()
