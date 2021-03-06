#import pdb; pdb.set_trace()
import os
import pytest
from sys import path
path.append(".")

db_file = os.path.join("test.db")
os.environ["SCOREBOARD_DB"] =  db_file

from scoreboard import functions
from common_functions import init_db

# @pytest.fixture(scope='session')
# def app():
#     db_file = os.path.join("test.db")
#     from app import app
#
#     return app


def test_db(app, tmpdir):
    db_file = tmpdir.join("test_db.db").strpath
    os.environ["SCOREBOARD_DB"] = db_file
    app.config.update(dict(DATABASE=db_file))

    functions.connectDB()
    db = functions.getDB()

    assert app.config['DATABASE'] == db_file
    assert db is not None


def test_db_setup(app, tmpdir):
    db_file = tmpdir.join("test_db.db").strpath
    app.config.update(dict(DATABASE=db_file))
    os.environ["SCOREBOARD_DB"] = db_file

    functions.connectDB()
    db = functions.getDB()

    assert app.config['DATABASE'] == db_file
    assert db is not None

    init_db(db)
