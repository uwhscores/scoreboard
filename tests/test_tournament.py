""" Tournament test class """
import os
import sqlite3

from flask import Flask

import pytest
from unittest import mock
from unittest.mock import patch


db_file = os.path.join("test.db")
os.environ["SCOREBOARD_DB"] = db_file

from scoreboard import functions
from scoreboard.tournament import Tournament

from common_functions import create_db, init_db, load_schedule, load_scores

# from flask import g
# import pdb; pdb.set_trace()

def init_tournament(tmpdir):
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

    return test_t


def test_tournament_init(app, tmpdir):
    app.config['DATABASE'] = tmpdir.join("test_db.db").strpath

    test_t = init_tournament(tmpdir)

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


def test_tournament_rankings_simple(app):

    mem_db = sqlite3.connect(":memory:")
    mem_db.row_factory = sqlite3.Row

    init_db(mem_db)

    tid = 1
    name = "Test Tournament"
    short_name = "test_tourn"
    start_date = "2018-01-01"
    end_date = "2018-01-02"
    location = "Pytest, PY"
    active = True

    with app.app_context():
        test_t = Tournament(tid, name, short_name, start_date, end_date, location, active, mem_db)

    load_schedule("simple", 1, mem_db)

    assert len(test_t.getTeams()) == 4
    assert len(test_t.getGames()) == 6
    assert len(test_t.getGames("A")) == 6
    assert len(test_t.getGames("B")) == 0

    scores = load_scores("simple")
    for score in scores:
        test_t.updateGame(score)

    standings = test_t.getStandings()
    first_place = standings["A"][0]
    assert first_place.place == 1
    assert first_place.team.name == "Team A"

    third_place = standings["A"][2]
    assert third_place.place == 3
    assert third_place.team.name == "Team C"

@mock.patch('scoreboard.tournament.flash', autospec=True)
def test_tournament_rankings_ties(mock_flash, app):

    mem_db = sqlite3.connect(":memory:")
    mem_db.row_factory = sqlite3.Row

    init_db(mem_db)

    tid = 1
    name = "Test Tournament"
    short_name = "test_tourn"
    start_date = "2018-01-01"
    end_date = "2018-01-02"
    location = "Pytest, PY"
    active = True

    with app.app_context():
        test_t = Tournament(tid, name, short_name, start_date, end_date, location, active, mem_db)

    load_schedule("simple_ties", 1, mem_db)

    assert len(test_t.getTeams()) == 4
    assert len(test_t.getGames()) == 6
    assert len(test_t.getGames("A")) == 6
    assert len(test_t.getGames("B")) == 0

    scores = load_scores("simple_ties")
    for score in scores:
        test_t.updateGame(score)

    standings = test_t.getStandings()
    print(standings)
    first_place = standings["A"][0]
    assert first_place.place == 1
    assert first_place.team.name == "Team A"

    second_place = standings["A"][1]
    assert second_place.place == 2
    assert second_place.team.name == "Team B"

    third_place = standings["A"][2]
    assert third_place.place == 2
    assert third_place.team.name == "Team C"

    ties = test_t.getTies()
    print(ties)
    assert len(ties) == 1
    tie = ties[0]
    assert tie['id_a'] == 2
    assert tie['id_b'] == 3

    tie_break = {"teams": [2, 3], "winner": 3}
    test_t.updateConfig("tie_break", tie_break)

    ties = test_t.getTies()
    assert ties is None

    standings = test_t.getStandings()
    print(standings)

    first_place = standings["A"][0]
    assert first_place.place == 1
    assert first_place.team.name == "Team A"

    second_place = standings["A"][1]
    assert second_place.place == 2
    assert second_place.team.name == "Team C"

    third_place = standings["A"][2]
    assert third_place.place == 3
    assert third_place.team.name == "Team B"
