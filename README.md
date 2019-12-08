# Welcome to Scoreboard
Welcome to Scoreboard, the software behind UWHScores.com. Scoreboard is a Python3 project
using the Flask framework and a SQLite database. Below are the very rough steps to
setup an instance and run it. These steps are likely not complete.

## Setup
1. Start by installing virtualenv if you have not already, Python 3.6:

    `sudo pip3 install virtualenv`

2. Clone the repository:

    `git clone git@github.com:notroot/scoreboard.git`

3. Create a new virtualenv:

    `cd scoreboard; virtualenv -p $( which python3.6 ) venv`

4. Step into your virtualenv:

    `. venv/bin/activate`

5. Install Flask and dependancies.

    `pip install -r requirements.txt`

6. Build the database, ideally from a populate file, or from the schema.sql file, you may need to install sqlite3 first:

    `sqlite3 app/scores.db < backup_file.sql`

7. Start the web service:

    `python scoreboard.py`

8. Connect at http://localhost:5000


## Build and Test
The project uses tox to build, install and run pytest. Generally the Scoreboard package is not installed when deployed (though it could be) but allowing tox to setup the virtual environment for testing with Pytest is adventagous.

### Steps
1. Run `tox` from the root of the project

That's it, tox does everything else and you'll get an output if all the tests pass or which ones fail

### Adding Tests
Tests are defined in the `/tests` folder along with supporting files. Automated tests should be contained in files starting with `test_` anything else should not have the test prefix. Individual tests are defined in the `test_*.py` files and are functions also starting with the `test_` prefix. Again any helper functions should be named not starting with the test prefix.

New tests can either be added to an existing `test_*.py` if it makes sens to group it with those tests, or can start a new file. 
