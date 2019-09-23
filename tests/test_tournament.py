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

from common_functions import create_db, init_db

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
    os.environ["SCOREBOARD_DB"] = db_file

    db = create_db(db_file)

    test_t = Tournament(tid, name, short_name, start_date, end_date, location, active, db)

    assert test_t is not None

    assert test_t.date_string == "January 01-02, 2018"
    assert test_t.days == []
    assert test_t.getGames() == []

    tournament_list = functions.getTournaments()

    assert tournament_list == {}

    test_t.commitToDB()

    tournament_list = functions.getTournaments()
    assert len(tournament_list) == 1

    found_tournament = tournament_list[1]
    assert found_tournament.name == "Test Tournament"
    assert found_tournament.short_name == "test_tourn"

    test_t.short_name = "new_name"
    test_t.commitToDB()

    tournament_list = functions.getTournaments()
    assert len(tournament_list) == 1

    found_tournament = tournament_list[1]
    assert found_tournament.name == "Test Tournament"
    assert found_tournament.short_name == "new_name"
