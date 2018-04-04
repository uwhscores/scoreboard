from functions import getTournamets, getTournamentByID, getUserByID, validateJSONSchema, getDB, authenticate_user
from app import app, global_limiter
from app import audit_logger
from flask import jsonify, request, make_response, g
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
    token = email
    user_id = authenticate_token(token)

    if user_id:
        g.user_id = user_id
        return True

    # only accept username/password combos if its the login path
    if request.path != "/api/v1/login":
        return False

    # it wasn't a token, so lets try it as a username/password pair
    user_id = authenticate_user(email, password_try, silent=True)

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

    return {'token': token, 'user_id': user_id, 'ttl': 1440}


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


# json response for rate limit exceeded
@app.errorhandler(429)
def ratelimit_handler(e):
    return make_response(
            jsonify(error="ratelimit exceeded %s" % e.description)
            , 429
    )


################################################################################
# Public APIs
################################################################################
@app.route('/api/v1')
def documentationPath():
    return jsonify(documentation="http://docs.uwhscores.apiary.io/")


@app.route('/api/v1/tournaments')
def apiGetTournaments():
    tournaments = getTournamets()

    response = []

    for t in tournaments.values():
        response.append(t.serialize())
    return jsonify(tournaments=response)


@app.route('/api/v1/tournaments/<tid>')
def apiGetTournament(tid):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    return jsonify(tournament=t.serialize(verbose=True))


@app.route('/api/v1/tournaments/<tid>/games')
def apiGetGames(tid):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    games = []

    if request.args.get('div'):
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


@app.route('/api/v1/tournaments/<tid>/games/<gid>')
def apiGetGame1(tid, gid):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unknown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    game = t.getGame(gid)

    if not game:
        raise InvalidUsage("Unknown gid", status_code=404)

    return jsonify(game=game.serialize())


@app.route('/api/v1/tournaments/<tid>/teams')
def apiGetTeams(tid):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    teams = t.getTeams()

    return jsonify(teams=teams)


@app.route('/api/v1/tournaments/<tid>/standings')
def apiGetStandings(tid):
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


@app.route('/api/v1/tournaments/<tid>/messages')
def apiGetMessages(tid):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    standings = t.getStandings()
    ties = t.getTieFlashes()

    return jsonify(ties=ties)


@app.route('/api/v1/tournaments/<tid>/timingruleset')
def apiGetTimingRules(tid):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unknown tid', status_code=404)

    rules = t.getTimingRuleSet()
    # response = {'timing_rule_set': {'tid': tid}}
    # response['timing_rule_set'].update(rules)
    return jsonify(timingruleset=rules)


################################################################################
# Private APIs
################################################################################
@app.route('/api/v1/login')
@global_limiter.limit("5/minute;20/hour")
@auth.login_required
def login_token():
    user_name = request.authorization.username
    response = genToken(user_name)
    audit_logger.info("API: Token generated for %s" % user_name)
    return jsonify(response)


@app.route('/api/v1/logout')
@auth.login_required
def logout_token():
    if 'all' in request.args:
        r = deleteToken(None, g.user_id)
    else:
        r = deleteToken(request.authorization.username)

    message = "Goodbye %s" % g.user_id
    current_user = getUserByID(g.user_id)
    audit_logger.info("API: Logout for user %s(%s)" % (current_user.short_name, current_user.user_id))
    return jsonify(message='goodbye')


@app.route('/api/v1/tournaments/<tid>/games/<gid>', methods=['POST'])
@auth.login_required
def updateGame(tid, gid):

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

    # TODO: validate score post data and simplify updating scores
    post_data = request.get_json()
    if not isinstance(post_data, dict):
        message = "POST data must be JSON format"
        raise InvalidUsage(message, status_code=400)

    score_post = post_data['game_score']
    # make sure tid in json matches URL
    try:
        tid = int(tid)
    except (TypeError, ValueError):
        raise InvalidUsage("Unknown tid", status_code=404)

    if not tid == score_post.get('tid'):
        raise InvalidUsage("tid mismatch", status_code=400)

    # make sure gid in json matches URL
    try:
        gid = int(gid)
    except (TypeError, ValueError):
        raise InvalidUsage("bad gid", status_code=400)

    if not gid == score_post.get('gid'):
        raise InvalidUsage("gid mismatch", status_code=400)

    game = t.getGame(gid)

    if not game:
        raise InvalidUsage("Unkown gid", status_code=404)

    # check that team ids match
    try:
        black_id = int(score_post.get('black_id'))
    except (TypeError, ValueError):
        black_id = None

    try:
        white_id = int(score_post.get('white_id'))
    except (TypeError, ValueError):
        white_id = None

    if game.white_tid == -1 or game.black_tid == -1:
        raise InvalidUsage("game is not set yet", status_code=400)
    elif game.white_tid != white_id:
        raise InvalidUsage("team id mismatch", status_code=400)
    elif game.black_tid != black_id:
        raise InvalidUsage("team id mismatch", status_code=400)

    score = {}
    score['gid'] = int(score_post.get('gid'))
    score['score_b'] = int(score_post.get('score_b'))
    score['score_w'] = int(score_post.get('score_w'))
    score['black_tid'] = black_id
    score['white_tid'] = white_id
    score['pod'] = score_post.get('pod')

    score['forfeit_w'] = score_post.get('forfeit_w')
    score['forfeit_b'] = score_post.get('forfeit_b')

    audit_logger.info("API: Score for game %s:%s being updated by %s(%s): black: %s, white:%s" %
                      (t.short_name, score['gid'], current_user.short_name, current_user.user_id, score['score_b'], score['score_w']))
    status = t.updateGame(score)

    if not status == 1:
        return jsonify(answer="Something went wrong")
    else:
        res = t.getGame(gid)
        return jsonify(res.serialize())


@app.route('/api/v1/tournaments/<tid>/timingruleset', methods=['POST'])
@auth.login_required
def updateGameTiming(tid):
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

    post_data = request.get_json()
    if not isinstance(post_data, dict):
        message = "POST data must be JSON format"
        raise InvalidUsage(message, status_code=400)

    # import pdb; pdb.set_trace()
    audit_logger.info("API called with %s" % post_data)
    (valid, message) = validateJSONSchema(post_data, "timing_rule_set")
    if not valid:
        raise InvalidUsage(message, status_code=400)

    rule_set = post_data.get('timing_rule_set')
    # make sure tid in json matches URL
    try:
        tid = int(tid)
    except (TypeError, ValueError):
        raise InvalidUsage("Unknown tid in URL", status_code=404)

    if not tid == rule_set.get('tid'):
        raise InvalidUsage("tid mismatch", status_code=400)

    # for game_type_entry in rule_set.get('game_types'):
    #     game_type = game_type_entry.get('game_type')
    #     ## TODO: get game type list from schedule
    #     if game_type not in ['RR', 'BR', 'E', 'CO']:
    #         raise InvalidUsage("Unknown game type %s" % game_type, status_code=400)
    #
    #     audit_logger.info("API: Timing rules for tournament %s, game type %s updated by %s(%s)" %
    #                       (t.short_name, game_type, current_user.short_name, current_user.user_id))
    #
    #     timing_rules = game_type_entry.get('timing_rules')
    #     res = t.updateTimingRules(game_type, timing_rules)
    res = t.updateTimingRules(rule_set)

    if not res == 1:
        raise InvalidUsage("Server side error updating game rules", status_code=500)
    else:
        rules = t.getTimingRules()
        #response = {'timing_rule_set': {'tid': tid}}
        #response['timing_rule_set'].update(rules)
        return jsonify(rules)
