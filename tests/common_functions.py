from scoreboard import functions
from scoreboard.tournament import Tournament
import json
import os
import sqlite3


def init_db(db):
    with open('schema.sql') as f:
        db.executescript(f.read())

    return db


def create_db(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    init_db(db)

    return db


def connect_db(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    return db


def add_tournament(db, tid, name=None, short_name=None, start_date=None, end_date=None, location=None, active=True):
    tid = tid
    if not name:
        name = "Test Tournament"
    if not short_name:
        short_name = "test_tourn"
    if not start_date:
        start_date = "2018-01-01"
    if not end_date:
        end_date = "2018-01-02"
    if not location:
        location = "Pytest, PY"

    test_t = Tournament(tid, name, short_name, start_date, end_date, location, active, db)
    test_t.commitToDB()


def load_schedule(schedule_name, tid, db):
    """ fill in a tournament shedule """

    if not os.path.exists(f"tests/schedules/{schedule_name}.json"):
        raise(Exception(f"Unable to locate schedule {schedule_name}"))

    with open(f"tests/schedules/{schedule_name}.json") as json_file:
        schedule = json.load(json_file)

    for team in schedule['teams']:
        add_team(db, tid, team)

    for game in schedule['games']:
        add_game(db, tid, game)


def add_team(db, tid, team):
    db.execute("INSERT INTO teams(tid, team_id, name, division) VALUES(?,?,?,?)", (tid, team['team_id'], team['name'], team['division']))
    db.commit()


def add_game(db, tid, game):
    if 'day' not in game:
        game['day'] = "Sat"

    if 'start_time' not in game:

        game['start_time'] = f"2019-01-01 12:{game['game_id']:02}:00"

    if 'pool' not in game:
        game['pool'] = "A"

    if 'pod' not in game:
        game['pod'] = None

    db.execute("INSERT INTO games(tid, gid, day, start_time, pool, black, white, division, pod, type, description) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (tid, game['game_id'], game['day'], game['start_time'], game['pool'], game['black'], game['white'], game['div'], game['pod'], game['type'], None))
    db.commit()


def load_scores(schedule_name):
    if not os.path.exists(f"tests/schedules/{schedule_name}.json"):
        raise(Exception(f"Unable to locate schedule {schedule_name}"))

    with open(f"tests/schedules/{schedule_name}.json") as json_file:
        schedule = json.load(json_file)

    scores = []
    for e in schedule['scores']:
        if 'forfeit_w' not in e:
            e['forfeit_w'] = None
        if 'forfeit_b' not in e:
            e['forfeit_b'] = None
        e['gid'] = e['game_id']
        scores.append(e)

    return scores
