from app import app
import sqlite3
import re
import bcrypt
from base64 import b64encode
from os import urandom
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

def getUserList():
    db = getDB()

    # cur = db.execute("SELECT user_id, short_name, email, date_created, last_login, active, site_admin, admin FROM users ORDER BY short_name COLLATE NOCASE")
    # users = []
    # for u in cur.fetchall():
    #     #users[u['user_id']] = {'short_name':u['short_name'], 'email':u['email'], 'date_created':u['date_created'], 'last_login':u['last_login'],\
    #     #                        'active':u['active'], 'site_admin':u['site_admin'], 'admin':u['admin']}
    #     users.append({'user_id':u['user_id'],'short_name':u['short_name'], 'email':u['email'], 'date_created':u['date_created'], 'last_login':u['last_login'],\
    #                             'active':u['active'], 'site_admin':u['site_admin'], 'admin':u['admin']})

    cur = db.execute("SELECT user_id FROM users ORDER BY short_name")
    users = []
    for u in cur.fetchall():
        users.append(getUserByID(u['user_id']))

    return users;

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

def addUser(new_user):
    db = getDB()

    result = {'success': False, 'message':""}
    # check that email is unique
    cur = db.execute("SELECT user_id FROM users WHERE email=?", (new_user['email'],))
    if cur.fetchone():
        result['message'] = "Email already exists, maybe try reseeting the password?"
        return result

    cur = db.execute("SELECT user_id FROM users WHERE short_name LIKE ?", (new_user['short_name'],))
    if cur.fetchone():
        result['message'] = "Short name already in use, sorry"
        return result

    while True:
        user_id = b64encode(urandom(6),"Aa")
        cur = db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        if not cur.fetchone():
            break

    while True:
        token = b64encode(urandom(30),"-_")
        cur = db.execute("SELECT user_id FROM users WHERE reset_token=?", (token,))
        if not cur.fetchone():
            break

    hashed = bcrypt.hashpw(token, bcrypt.gensalt())

    cur = db.execute("INSERT INTO users(user_id, short_name, email, password, active, reset_token) VALUES (?,?,?,?,1,?)",\
            (user_id, new_user['short_name'], new_user['email'], hashed, token))

    db.commit()

    if new_user['site-admin']:
        cur = db.execute("UPDATE users SET site_admin=1 WHERE user_id=?", (user_id,))
        db.commit()

    if new_user['admin']:
        cur = db.execute("UPDATE users SET admin=1 WHERE user_id=?", (user_id,))
        db.commit()

    result['success'] = True
    result['token'] = token
    result['user_id'] = user_id
    result['message'] = "User successfully created"

    return result

def validateResetToken(token):
    db = getDB()

    cur = db.execute("SELECT user_id FROM users where reset_token=? AND active=1", (token,))
    row = cur.fetchone()
    cur.close()

    if row:
        return row['user_id']
    else:
        return None
