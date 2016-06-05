from app import app
import sqlite3
import re
import bcrypt
from flask import g, flash

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

def authenticate_user(email, password_try, silent=False, ip_addr=None):
    db = getDB()

    cur = db.execute("SELECT user_id, password, failed_logins FROM users WHERE email=? AND active=1", (email,))
    row = cur.fetchone()
    cur.close()

    if row:
        user_id = row['user_id']
        hashed = str(row['password'])
        password_try = str(password_try)
        failed_logins = row['failed_logins']

        # if too many failed passwords in a row, just block, will require manual intervention
        if failed_logins > 10:
            # should fire off password reset email here once I write that
            if not silent:
                flash("Account locked due to too many failed passwords")

            return None

        if bcrypt.hashpw(password_try, hashed) == hashed:
            cur = db.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP, failed_logins=0 WHERE user_id=?", (user_id,))
            db.commit()
            return user_id
        else:
            failed_logins += 1
            cur = db.execute("UPDATE users SET failed_logins=? WHERE user_id=?", (failed_logins, user_id))
            db.commit()

            if not silent:
                flash("Incorrect password")

            return None

    else:
        if not silent:
            flash("Cannot find account")
        return None

def validateResetToken(token):
    db = getDB()

    cur = db.execute("SELECT user_id FROM users where reset_token=? AND active=1", (token,))
    row = cur.fetchone()
    cur.close()

    if row:
        return row['user_id']
    else:
        return None

def setUserPassword(user_id, password):
    db = getDB()

    password = password.encode('utf-8')
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())  
    
    cur = db.execute("UPDATE users SET password=?, reset_token=null, failed_logins=0 WHERE user_id=?", (hashed, user_id))
    db.commit()

    return 0
