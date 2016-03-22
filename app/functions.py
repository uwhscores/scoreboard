from app import app
import sqlite3
import re
from flask import Flask, request, session, g, redirect, url_for, abort, \
        render_template, flash, jsonify, json

from tournament import Tournament

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

    cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location FROM tournaments ORDER BY start_date DESC")
    rows = cur.fetchall()

    tournaments = {}
    for t in rows:
    	tournaments[t['tid']]= (Tournament(t['tid'], t['name'], t['short_name'], t['start_date'], t['end_date'], t['location'], db))

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

    cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location FROM tournaments WHERE tid=?", (tid,))
    t = cur.fetchone()
    if (t):
        return Tournament(t['tid'], t['name'], t['short_name'], t['start_date'], t['end_date'], t['location'], db)
    else:
        return None
