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

5. Install Flask and dependancies. Copy the below block into a text file, say requirements.txt:
    ```
    bcrypt==2.0.0
    cffi==1.5.2
    Flask==0.10.1
    Flask-HTTPAuth==3.1.1
    Flask-Login==0.3.2
    Flask-Limiter==0.9.3
    itsdangerous==0.24
    Jinja2==2.8
    MarkupSafe==0.23
    mechanize==0.2.5
    pycparser==2.14
    six==1.10.0
    Werkzeug==0.11.3
    ```
    Now install all the packages:

    `pip install -r requirements.txt`

6. Build the database, ideally from a populate file, or from the schema.sql file:

    `sqlite app/scores.db < backup_file.sql`

7. Start the web service:

    `python scoreboard.py`

8. Connect at http://localhost:5000
