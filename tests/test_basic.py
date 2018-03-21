#import pdb; pdb.set_trace()
import os
import pytest
from sys import path
path.append(".")

db_file = os.path.join("test.db")
os.environ["SCOREBOARD_DB"] =  db_file

from app import app, functions

# @pytest.fixture(scope='session')
# def app():
#     db_file = os.path.join("test.db")
#     from app import app
#
#     return app

def init_db(db):
    with open('schema.sql') as f:
        db.executescript(f.read())

    return db

def test_db(tmpdir):
    db_file = tmpdir.join("test_db.db").strpath
    app.config.update(dict(DATABASE=db_file))

    functions.connectDB()
    db = functions.getDB()

    assert app.config['DATABASE'] == db_file
    assert db is not None


def test_db_setup(tmpdir):
    db_file = tmpdir.join("test_db.db").strpath
    app.config.update(dict(DATABASE=db_file))

    functions.connectDB()
    db = functions.getDB()

    assert app.config['DATABASE'] == db_file
    assert db is not None

    init_db(db)
