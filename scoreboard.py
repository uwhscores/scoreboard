from scoreboard import create_app
from werkzeug.contrib.fixers import ProxyFix
import os
import sys



if not "SCOREBOARD_DB" in os.environ:
    if os.path.exists("scoreboard/scores.db"):
        os.environ["SCOREBOARD_DB"] = "scoreboard/scores.db"
    else:
        print("Databse path not set in OS env and default doesn't exist")
        print("Create an empty DB from the schema or get a clone")
        print("Exiting")
        sys.exit(1)

if __name__ == '__main__':
    db_path = None
    db_path = os.getenv("SCOREBOARD_DB")

    if not db_path:
        db_path = os.path.join("scoreboard/", 'scores.db')

    app = create_app(db_path, debug=True)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run(host='0.0.0.0')
    # app.run()
