from functions import *
from flask import json,jsonify, request
from flask.ext.httpauth import HTTPBasicAuth
from base64 import b64encode
from os import urandom

auth = HTTPBasicAuth()

class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

@auth.verify_password
def verify_pw(email, password_try):
    # first assume its a token for speed
    user_id = authenticate_token(email)

    if user_id:
        g.user_id = user_id
        return True

    # it wasn't a token, so lets try it as a username/password pair
    user_id = authenticate_user(email, password_try, True)

    if user_id:
        g.user_id = user_id
        return True

    # doesn't seem to be anybody we know
    return False

def authenticate_token(token):
    db = getDB()

    cur = db.execute("SELECT user_id FROM tokens WHERE token=? AND valid_til > datetime('now')", (token,))
    u = cur.fetchone()

    if u:
        return u['user_id']
    else:
        return None


# generates a token from a given user name (email), expects user to be valid but error_message
#
def genToken(user_name):
    db = getDB()

    cur = db.execute("SELECT user_id FROM users WHERE email = ?", (user_name,))
    u = cur.fetchone()
    if not u:
        return None

    user_id = u['user_id']
    token = b64encode(urandom(32))

    try:
        cur = db.execute("INSERT INTO tokens (user_id, token, valid_til) VALUES (?,?, datetime('now', '+1 day'))", (user_id, token))
        db.commit()
    except Execption as e:
        db.rollback()
        # do something with the exception?
        return None

    return {'token':token, 'user_id':user_id, 'ttl':1440}

def deleteToken(token, user_id=None):
    db = getDB()

    if token:
        cur = db.execute("DELETE FROM tokens WHERE token=?", (token,))
    elif user_id:
        cur = db.execute("DELETE FROM tokens WHERE user_id=?", (user_id,))

    db.commit()

    return True

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

################################################################################
# Public APIs
################################################################################
@app.route('/api/v1/tournament/games')
def apiGetGames():
    if request.args.get('tid'):
        tid = request.args.get('tid')
    else:
        raise InvalidUsage('Missing tid', status_code=400)

    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    games = []
    if request.args.get('gid'):
        gid = request.args.get('gid')
        games.append(t.getGame(gid))
    elif request.args.get('div'):
        div = request.args.get('div')
        if not t.isGroup(div):
            raise InvalidUsage('Uknown division', status_code=404)
        games = t.getGames(div)
    else:
        games = t.getGames()

    response = []
    for g in games:
        response.append(g.serialize())

    return jsonify(games=response)

@app.route('/api/v1/tournament/teams')
def apiGetTeams():
    if request.args.get('tid'):
        tid = request.args.get('tid')
    else:
        raise InvalidUsage('Missing tid', status_code=400)

    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    teams = t.getTeams()

    return jsonify(teams=teams)


@app.route('/api/v1/tournament/standings')
def apiGetStandings():
    if request.args.get('tid'):
        tid = request.args.get('tid')
    else:
        raise InvalidUsage('Missing tid', status_code=400)

    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    standings = t.getStandings()
    response = []
    for s in standings:
        response.append(s.serialize())


    return jsonify(standings=response)

@app.route('/api/v1/tournament/messages')
def apiGetMessages():
    if request.args.get('tid'):
        tid = request.args.get('tid')
    else:
        raise InvalidUsage('Missing tid', status_code=400)

    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    standings= t.getStandings()
    ties = t.getTieFlashes()

    return jsonify(ties=ties)

################################################################################
# Private APIs
################################################################################
@app.route('/api/v1/login')
@auth.login_required
def login_token():
    user_name = request.authorization.username
    response = genToken(user_name)

    return jsonify(response)

@app.route('/api/v1/logout')
@auth.login_required
def logout_token():
    if 'all' in request.args:
        r = deleteToken(None, g.user_id)
    else:
        r = deleteToken(request.authorization.username)

    message = "Goodbye %s" % g.user_id
    return jsonify(message='goodbye')


@app.route('/api/v1/game/score', methods= ['POST'])
@auth.login_required
def updateGame():
    if not request.json:
        raise InvalidUsage('not JSON', status_code=400)

    if request.json.get('tid'):
        tid = request.json.get('tid')
    else:
        raise InvalidUsage('Missing tid', status_code=400)

    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    current_user = getUserByID(g.user_id)
    if not t.isAuthorized(current_user):
        message = "user %s is not authorized" % g.user_id
        raise InvalidUsage(message, status_code=404)

    j = request.json

    gid = int(j.get('gid'))
    game = t.getGame(gid)

    if not game:
        raise InvalidUsage("Unkown gid", status_code=404)

    # check that team ids match
    try:
        black_id = int(j.get('black_id'))
    except (TypeError, ValueError):
        black_id = None

    try:
        white_id = int(j.get('white_id'))
    except (TypeError, ValueError):
        white_id = None

    if game.white_tid == -1 or game.black_tid == -1:
        raise InvalidUsage("game is not set yet", status_code=400)
    elif game.white_tid != white_id:
        raise InvalidUsage("team id mismatch", status_code=400)
    elif game.black_tid != black_id:
        raise InvalidUsage("team id mismatch", status_code=400)

    score = {}
    score['gid'] = int(j.get('gid'))
    score['score_b'] = int(j.get('score_b'))
    score['score_w'] = int(j.get('score_w'))
    score['black_tid'] = black_id
    score['white_tid'] = white_id
    score['pod'] = j.get('pod')

    score['forfeit_w'] = j.get('forfeit_w')
    score['forfeit_b'] = j.get('forfeit_b')

    status = t.updateGame(score)

    if not status == 1:
        return jsonify(answer="Something went wrong")
    else:
        return jsonify(message="success")
