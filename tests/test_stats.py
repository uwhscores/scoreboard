import pytest
import os
from unittest import mock

from scoreboard.models import Stats
# def test_stats_compare(tmpdir):
#     tid = 1
#     name = "Test Tournament"
#     short_name = "test_tourn"
#     start_date = "2018-01-01"
#     end_date = "2018-01-02"
#     location = "Pytest, PY"
#     active = True
#
#     db_file = tmpdir.join("test_db.db").strpath
#     os.environ["SCOREBOARD_DB"] = db_file
#
#     db = create_db(db_file)
#
#     test_t = Tournament(tid, name, short_name, start_date, end_date, location, active, db)
#
#     team_a = {"team_id": 1, "name": "team_a", "division": "A", "flag_url": None}
#     team_b = {"team_id": 2, "name": "team_b", "division": "A", "flag_url": None}
#
#     team_a = Stats(test_t, team_a, unittest=True)
#     team_b = Stats(test_t, team_b, unittest=True)
#
#     team_a.points = 8
#     team_b.points = 7
#
#     assert team_a > team_b


@mock.patch('scoreboard.tournament.Tournament')
def test_stats_compare(mock_t):

    team_a = {"team_id": 1, "name": "team_a", "division": "A", "flag_url": None}
    team_b = {"team_id": 2, "name": "team_b", "division": "A", "flag_url": None}

    team_a = Stats(mock_t, team_a, unittest=True)
    team_b = Stats(mock_t, team_b, unittest=True)

    team_a.points = 4
    team_a.wins = 2
    team_a.losses = 0
    team_a.ties = 0
    team_a.goals_allowed = 0

    team_b.points = 4
    team_b.wins = 2
    team_b.losses = 0
    team_b.ties = 0
    team_b.goals_allowed = 0

    # tied
    assert team_a == team_b

    # b gave up more goals
    team_b.goals_allowed = 1
    assert team_a == team_b
    assert team_a < team_b
    assert team_b > team_a

    # more losses
    team_b.goals_allowed = 0
    team_b.losses = 1
    assert team_a == team_b
    assert team_a < team_b

    team_b.losses = 0
    team_a.wins = 3
    assert team_a == team_b
    assert team_a < team_b

    team_a.points = 5
    assert team_a != team_b
    assert team_a < team_b


@mock.patch('scoreboard.tournament.Tournament')
def test_stats_sort(mock_t):
    team_a = {"team_id": 1, "name": "team_a", "division": "A", "flag_url": None}
    team_b = {"team_id": 2, "name": "team_b", "division": "A", "flag_url": None}
    team_c = {"team_id": 3, "name": "team_c", "division": "A", "flag_url": None}

    team_a = Stats(mock_t, team_a, unittest=True)
    team_b = Stats(mock_t, team_b, unittest=True)
    team_c = Stats(mock_t, team_c, unittest=True)

    # straight up points sort
    team_a.points = 6
    team_a.wins = 3
    team_a.losses = 0
    team_a.ties = 0
    team_a.goals_allowed = 0

    team_b.points = 4
    team_b.wins = 2
    team_b.losses = 1
    team_b.ties = 0
    team_b.goals_allowed = 2

    team_c.points = 2
    team_c.wins = 1
    team_c.losses = 2
    team_c.ties = 0
    team_c.goals_allowed = 3

    stats_list = [team_c, team_b, team_a]
    sorted_list = sorted(stats_list)

    first = sorted_list[0]
    assert first.name == "team_a"
    second = sorted_list[1]
    assert second.name == "team_b"
    third = sorted_list[2]
    assert third.name == "team_c"

    # goals allowed
    team_a.points = 6
    team_a.wins = 3
    team_a.losses = 0
    team_a.ties = 0
    team_a.goals_allowed = 0

    team_b.points = 6
    team_b.wins = 3
    team_b.losses = 0
    team_b.ties = 0
    team_b.goals_allowed = 2

    team_c.points = 2
    team_c.wins = 1
    team_c.losses = 2
    team_c.ties = 0
    team_c.goals_allowed = 3

    stats_list = [team_c, team_b, team_a]
    sorted_list = sorted(stats_list)

    first = sorted_list[0]
    assert first.name == "team_a"
    second = sorted_list[1]
    assert second.name == "team_b"
    third = sorted_list[2]
    assert third.name == "team_c"

    # least losses
    team_a.points = 6
    team_a.wins = 3
    team_a.losses = 0
    team_a.ties = 0
    team_a.goals_allowed = 3

    team_b.points = 6
    team_b.wins = 3
    team_b.losses = 1
    team_b.ties = 0
    team_b.goals_allowed = 0

    team_c.points = 2
    team_c.wins = 1
    team_c.losses = 2
    team_c.ties = 0
    team_c.goals_allowed = 3

    stats_list = [team_c, team_b, team_a]
    sorted_list = sorted(stats_list)

    first = sorted_list[0]
    assert first.name == "team_a"
    second = sorted_list[1]
    assert second.name == "team_b"
    third = sorted_list[2]
    assert third.name == "team_c"

    # most wins
    team_a.points = 6
    team_a.wins = 4
    team_a.losses = 1
    team_a.ties = 0
    team_a.goals_allowed = 3

    team_b.points = 6
    team_b.wins = 3
    team_b.losses = 0
    team_b.ties = 0
    team_b.goals_allowed = 0

    team_c.points = 3
    team_c.wins = 1
    team_c.losses = 2
    team_c.ties = 0
    team_c.goals_allowed = 3

    stats_list = [team_c, team_b, team_a]
    sorted_list = sorted(stats_list)

    first = sorted_list[0]
    assert first.name == "team_a"
    second = sorted_list[1]
    assert second.name == "team_b"
    third = sorted_list[2]
    assert third.name == "team_c"


@mock.patch('scoreboard.tournament.Tournament')
def test_ranking(mock_t):
    team_a = {"team_id": 1, "name": "team_a", "division": "A", "flag_url": None}
    team_b = {"team_id": 2, "name": "team_b", "division": "A", "flag_url": None}
    team_c = {"team_id": 3, "name": "team_c", "division": "A", "flag_url": None}

    team_a = Stats(mock_t, team_a, unittest=True)
    team_b = Stats(mock_t, team_b, unittest=True)
    team_c = Stats(mock_t, team_c, unittest=True)

    # straight up points sort
    team_a.points = 6
    team_a.wins = 3
    team_a.losses = 0
    team_a.ties = 0
    team_a.goals_allowed = 0

    team_b.points = 4
    team_b.wins = 2
    team_b.losses = 1
    team_b.ties = 0
    team_b.goals_allowed = 2

    team_c.points = 2
    team_c.wins = 1
    team_c.losses = 2
    team_c.ties = 0
    team_c.goals_allowed = 3
