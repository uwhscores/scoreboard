from scoreboard import create_app
import os

db_path = os.path.join("scoreboard/", 'scores.db')
app = create_app(db_path, debug=False)
