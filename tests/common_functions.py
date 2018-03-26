from app import functions
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
