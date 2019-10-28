from app import app
import sqlite3
import os
import bcrypt
import json
from base64 import b64encode
from flask import g, flash
from jsonschema import validate, ValidationError, RefResolutionError

from .tournament import Tournament
from .models import User


def connectDB():
    """ Connect to DB as configured """
    with app.app_context():
        rv = sqlite3.connect(os.environ["SCOREBOARD_DB"])
        rv.row_factory = sqlite3.Row
        return rv


def getDB():
    """ Should store database object is context, doesn't right now """
    # TODO: Store db to context
    # if not hasattr(app.g, 'sqlite_db'):
    #     app.g.sqlite_db = connectDB()
    # return app.g.sqlite_db
    return connectDB()


@app.teardown_appcontext
def closeDB(error):
    """ tear down database connection on exit """
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


def getTournaments(filter=None):
    """ get dictionary of tournament objects indexed by tournament ID """
    db = getDB()

    if filter == "past":
        cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location, active FROM tournaments WHERE end_date < date('now', '-1 day') ORDER BY start_date DESC")
    elif filter == "future":
        cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location, active FROM tournaments WHERE start_date > date('now', '+1 day') ORDER BY start_date DESC")
    elif filter == "live":
        cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location, active FROM tournaments WHERE start_date <= date('now','+1 day') AND end_date >= date('now', '-1 day') ORDER BY start_date DESC")
    else:
        # all
        cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location, active FROM tournaments ORDER BY start_date DESC")
    rows = cur.fetchall()

    tournaments = {}
    for t in rows:
        tournaments[t['tid']] = (Tournament(t['tid'], t['name'], t['short_name'], t['start_date'], t['end_date'], t['location'], t['active'], db))

    return tournaments


def getTournamentID(short_name):
    """ get tournament ID from short name string """
    db = getDB()

    cur = db.execute("SELECT tid FROM tournaments where short_name = ?", (short_name,))

    row = cur.fetchone()
    if (row):
        return row['tid']
    else:
        return -1


def getTournamentByID(tid):
    """ get tournament object from ID integer """
    db = getDB()

    cur = db.execute("SELECT tid, name, short_name, start_date, end_date, location, active FROM tournaments WHERE tid=?", (tid,))
    t = cur.fetchone()
    if (t):
        return Tournament(t['tid'], t['name'], t['short_name'], t['start_date'], t['end_date'], t['location'], t['active'], db)
    else:
        return None


def getUserID(email):
    """ get user ID string from email """
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
    """ get user object from user id string """
    db = getDB()

    cur = db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    if row:
        return User(row['user_id'], db)
    else:
        return None


def getUserList():
    """ get list of all users as user objects """
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

    return users


def authenticate_user(email, password_try, silent=False, ip_addr=None):
    """ authenticate user for login """
    db = getDB()

    cur = db.execute("SELECT user_id, password, failed_logins FROM users WHERE email=? AND active=1", (email,))
    row = cur.fetchone()
    cur.close()

    if row:
        user_id = row['user_id']
        hashed = row['password'].encode('utf-8')
        password_try = password_try.encode('utf-8')
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
    """ add a new user to the database
    returns dictionary with the results of the add including their password reset reset_token
    always returns dictionary, must check 'success' field for True/False """
    db = getDB()

    result = {'success': False, 'message': ""}
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
        user_id = b64encode(os.urandom(6), "Aa")
        cur = db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        if not cur.fetchone():
            break

    while True:
        token = b64encode(os.urandom(30), "-_")
        cur = db.execute("SELECT user_id FROM users WHERE reset_token=?", (token,))
        if not cur.fetchone():
            break

    hashed = bcrypt.hashpw(token, bcrypt.gensalt())

    cur = db.execute("INSERT INTO users(user_id, short_name, email, password, active, reset_token) VALUES (?,?,?,?,1,?)",
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
    """ validate reset token, returns the user_id if the reset token is found and active """
    db = getDB()

    cur = db.execute("SELECT user_id FROM users where reset_token=? AND active=1", (token,))
    row = cur.fetchone()
    cur.close()

    if row:
        return row['user_id']
    else:
        return None


def validateJSONSchema(source, schema_name):
    """ validates a JSON against defined schema in json_schemas folder by name
        function looks for a json file with the given name appending ".json" (eg, team becaomes team.json)
        Returns duple of Pass/Fail boolean and message
    """
    schema_file = schema_name.lower() + ".json"
    schema_file = os.path.join("app/json_schemas", schema_file)

    if not os.path.isfile(schema_file):
        return (False, "Unable to locate schema file for schema name %s" % schema_name)

    with open(schema_file) as f:
        schema = json.load(f)

    if not schema:
        return (False, "Schema file failed to load, unable to validate")

    # import pdb; pdb.set_trace()
    try:
        validate(source, schema)
    except ValidationError as e:
        if e.validator == "required":
            msg = "Validation error, %s" % e.message
        elif e.validator == "type":
            path = ""
            for entry in e.path:
                path = path + ":" + str(entry)
            msg = "%s is not of type %s" % (path, e.schema['type'])
        elif e.validator == "additionalProperties":
            msg = "Invalid format: %s" % e.message
        else:
            msg = "Validataion failed %s" % e.message

        return (False, msg)
    except RefResolutionError as e:
        msg = "Unable to find schema refrenced %s" % e.message

        return (False, msg)

    return (True, "")


def ordinalize(number):
    """ returns the ordinalized string given a number
    1 -> 1st, 3 -> 3rd, 6 -> 6th
    takes in an int or a string, retunrs a string
    """
    #n = int(number)
    # return str(lambda n: "%d%s" % (n, "tsnrhtdd"[(n/10 % 10 != 1)*(n % 10 <
    # 4)*n % 10::4]))
    try:
        n = int(number)
    except ValueError:
        return number

    if 4 <= n <= 20:
        suffix = 'th'
    elif n == 1 or (n % 10) == 1:
        suffix = 'st'
    elif n == 2 or (n % 10) == 2:
        suffix = 'nd'
    elif n == 3 or (n % 10) == 3:
        suffix = 'rd'
    elif n < 100:
        suffix = 'th'
    ord_num = str(n) + suffix
    return ord_num
