from scoreboard import create_app
from werkzeug.contrib.fixers import ProxyFix
import os

db_path = os.path.join("scoreboard/", 'scores.db')
app = create_app(db_path, debug=False)

app.wsgi_app = ProxyFix(app.wsgi_app)
