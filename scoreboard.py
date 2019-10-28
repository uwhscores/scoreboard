from app import app
from werkzeug.contrib.fixers import ProxyFix
import os
import sys

app.wsgi_app = ProxyFix(app.wsgi_app)


if not "SCOREBOARD_DB" in os.environ:
    if os.path.exists("app/scores.db"):
        os.environ["SCOREBOARD_DB"] = "app/scores.db"
    else:
        print("Databse path not set in OS env and default doesn't exist")
        print("Create an empty DB from the schema or get a clone")
        print("Exiting")
        sys.exit(1)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    # app.run()
