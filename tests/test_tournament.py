""" Tournament test class """
import os
import pytest
import flask
from sys import path
path.append(".")

db_file = os.path.join("test.db")
os.environ["SCOREBOARD_DB"] = db_file

from app import app, functions
from app.tournament import Tournament

from common_functions import create_db

# from flask import g
# import pdb; pdb.set_trace()


def test_tournament_init(tmpdir):
    tid = 1
    name = "Test Tournament"
    short_name = "test_tourn"
    start_date = "2018-01-01"
    end_date = "2018-01-02"
    location = "Pytest, PY"
    active = True

    db_file = tmpdir.join("test_db.db").strpath

    db = create_db(db_file)

    test_t = Tournament(tid, name, short_name, start_date, end_date, location, active, db)

    assert test_t is not None

    assert test_t.date_string == "January 01-02, 2018"
    assert test_t.days == []
    assert test_t.getGames() == []
