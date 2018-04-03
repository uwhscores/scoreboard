# Welcome to Scoreboard
Welcome to Scoreboard, the software behind UWHScores.com. Scoreboard is a Python project
using the Flask framework and a SQLite backend. Below are the very rough steps to
setup an instance and run it. These steps are likely not complete.

## Setup
1. Start by installing virtualenv if you have not already:

    `sudo pip install virtualenv`

2. Clone the repository:

    `git clone git@github.com:notroot/scoreboard.git`

    Checkout `dev`

    `git checkout dev`

3. Create a new virtualenv:

    `cd scoreboard; virtualenv venv`

4. Step into your virtualenv:

    `. venv/bin/activate`

5. Install Flask and dependancies. 

    `pip install -r requirements.txt`

6. Build the database, ideally from a populate file, or from the schema.sql file:

    `sqlite app/scores.db < backup_file.sql`

7. Start the web service:

    `python scoreboard.py`

8. Connect at http://localhost:5000
