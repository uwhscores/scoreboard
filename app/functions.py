from app import app
import sqlite3
import re
import bcrypt
from flask import Flask, request, session, g, redirect, url_for, abort, \
        render_template, flash, jsonify, json

from tournament import Tournament
from models import User

# DB logic for setting up database connection and teardown
def connectDB():
    with app.app_context():
    	rv = sqlite3.connect(app.config['DATABASE'])
    	rv.row_factory = sqlite3.Row
    	return rv

def getDB():
	# if not hasattr(app.g, 'sqlite_db'):
	# 	app.g.sqlite_db = connectDB()
	# return app.g.sqlite_db
    return connectDB()

@app.teardown_appcontext
def closeDB(error):
	if hasattr(g, 'sqlite_db'):
		g.sqlite_db.close()

def getTournamets():
    db = getDB()

    cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location, active FROM tournaments ORDER BY start_date DESC")
    rows = cur.fetchall()

    tournaments = {}
    for t in rows:
    	tournaments[t['tid']]= (Tournament(t['tid'], t['name'], t['short_name'], t['start_date'], t['end_date'], t['location'], t['active'], db))

    return tournaments

def getTournamentID(short_name):
    db = getDB()

    cur = db.execute("SELECT tid FROM tournaments where short_name = ?", (short_name,))

    row = cur.fetchone()
    if (row):
        return row['tid']
    else:
        return -1

def getTournamentByID(tid):
    db = getDB()

    cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location, active FROM tournaments WHERE tid=?", (tid,))
    t = cur.fetchone()
    if (t):
        return Tournament(t['tid'], t['name'], t['short_name'], t['start_date'], t['end_date'], t['location'], t['active'], db)
    else:
        return None

## User related functions
def getUserID(email):
    db = getDB()

    cur = db.execute("SELECT user_id FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    cur.close()

    user_id = None

    if row:
        return row['user_id']
    else:
        return None

def getUserByID(user_id):
    db = getDB()

    cur = db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    if row:
        return User(row['user_id'], db)
    else:
        return None

def authenticate_user(email, password_try, silent=False):
    db = getDB()

    cur = db.execute("SELECT user_id, password FROM users WHERE email=? AND active=1", (email,))
    row = cur.fetchone()
    cur.close()

    if row:
        user_id = row['user_id']
        hashed = str(row['password'])
        password_try = str(password_try)

        if bcrypt.hashpw(password_try, hashed) == hashed:
            return user_id
        else:
            if not silent:
                flash("Incorrect password")
            return None

    else:
        if not silent:
            flash("Cannot find account")
        return None
