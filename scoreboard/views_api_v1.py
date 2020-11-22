from flask import current_app as app
from base64 import b64encode
from flask import jsonify, request, make_response, g
from flask_httpauth import HTTPBasicAuth
from os import urandom
import urllib.parse
import sqlite3

from scoreboard import global_limiter, audit_logger
from scoreboard.functions import getTournaments, getTournamentByID, getUserByID, getPlayerByID, validateJSONSchema, getDB, authenticate_user
from scoreboard.exceptions import UserAuthError, UpdateError, InvalidUsage

auth = HTTPBasicAuth()


@auth.verify_password
def verify_pw(email, password_try):
    if not email:
        audit_logger.info("API: Auth attempted without user/token")
        return False

    audit_logger.info("API: Attempting auth for user/token %s" % email)

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
    user_id = None
    try:
        user_id = authenticate_user(email, password_try)
    except UserAuthError:
        return False

    if user_id:
        g.user_id = user_id
        audit_logger.info("Succesful authentication for %s" % user_id)
        return True

    # doesn't seem to be anybody we know
    return False


def authenticate_token(token):
    db = getDB()

    cur = db.execute("SELECT user_id FROM tokens WHERE token=? AND valid_til > datetime('now')", (token,))
    u = cur.fetchone()

    if u:
        audit_logger.info("Verified token auth for %s" % u['user_id'])
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
    token = b64encode(urandom(32)).decode('utf-8')

    try:
        cur = db.execute("INSERT INTO tokens (user_id, token, valid_til) VALUES (?,?, datetime('now', '+1 day'))", (user_id, token))
        db.commit()
    except sqlite3.DatabaseError as e:
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


################################################################################
# Public APIs
################################################################################
@app.route('/api/v1')
def documentationPath():
    return jsonify(documentation="http://docs.uwhscores.apiary.io/")


@app.route('/api/v1/tournaments')
def apiGetTournaments():
    tournaments = getTournaments()

    response = []

    for t in list(tournaments.values()):
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

@app.route('/api/v1/tournaments/<tid>/teams/<team_id>')
def apiGetTeamInfo(tid, team_id):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage("Unknown tid", status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    team_info = t.getTeamInfo(team_id)

    if not team_info:
        raise InvalidUsage("Unknown team ID", status_code=404)

    #request.url_root
    if team_info['flag_url']:
        team_info['flag_url'] = urllib.parse.urljoin(request.url_root, team_info['flag_url'])

    return jsonify(team=team_info)

@app.route('/api/v1/tournaments/<tid>/standings')
def apiGetStandings(tid):
    t = getTournamentByID(tid)

    if not t:
        raise InvalidUsage('Unkown tid', status_code=404)

    message = t.getDisableMessage()
    if message:
        raise InvalidUsage(message, status_code=503)

    pods = t.getPodsActive()
    standings = None

    pod_ask = request.args.get('pod')
    div_ask = request.args.get('div')

    if pod_ask and div_ask:
        raise InvalidUsage("Cannot filter by pod and div at same time", status_code=400)

    if div_ask and not t.isGroup(div_ask):
        raise InvalidUsage("division not found", status_code=404)

    if pod_ask:
        app.logger.debug("pods = %s" % pods)
        app.logger.debug("pod_ask = %s" % pod_ask)
        if pod_ask in pods:
            standings = t.getStandings(pod=pod_ask)
        else:
            raise InvalidUsage("Unknown pod", status_code=404)
    elif pods:
        for pod in pods:
            standings += t.getStandings(pod=pod)
    else:
        standings = t.getStandings()

    answer = []
    for group in standings:
        for r in standings[group]:
            if div_ask and div_ask == r.div:
                answer.append(r.serialize())
            elif not div_ask:
                answer.append(r.serialize())

    return jsonify(standings=answer)


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
    return jsonify(timing_rule_set=rules)


@app.route('/api/v1/players/<player_id>')
def apiGetPlayerByID(player_id):
    player = getPlayerByID(player_id)

    if not player:
        raise InvalidUsage("Unkown player", status_code=404)

    return jsonify(player=player.serialize())

################################################################################
# Private APIs
################################################################################
@app.route('/api/v1/login')
@global_limiter.limit("5/minute;20/hour")
@auth.login_required
def login_token():
    user_name = request.authorization.username
    response = genToken(user_name)
    app.logger.debug("API: Token generated %s" % response)
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


@app.route('/api/v1/login/test')
@auth.login_required
def login_test():
    """ Test route for verifying authentcation token is working """
    return jsonify(message="success")


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
    if score["forfeit_w"] or score["forfeit_b"]:
        audit_logger.info("API: Forfeit set for game %s: W: %s, B: %s" % (score['gid'], score["forfeit_w"], score["forfeit_b"]))

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

    res = t.updateTimingRules(rule_set)

    if not res == 1:
        raise InvalidUsage("Server side error updating game rules", status_code=500)
    else:
        rules = t.getTimingRuleSet()
        #response = {'timing_rule_set': {'tid': tid}}
        #response['timing_rule_set'].update(rules)
        return jsonify(rules)


@app.route('/api/v1/players/<player_id>', methods=['POST'])
@auth.login_required
def updatePlayerByID(player_id):
    player = getPlayerByID(player_id)

    if not player:
        raise InvalidUsage("Unkown player", status_code=404)

    current_user = getUserByID(g.user_id)
    if not current_user.admin:
        raise InvalidUsage("Not authorized", status_code=403)

    post_data = request.get_json()
    if not isinstance(post_data, dict):
        message = "POST data must be JSON format"
        raise InvalidUsage(message, status_code=400)

    (valid, message) = validateJSONSchema(post_data, "player")
    if not valid:
        raise InvalidUsage(message, status_code=400)

    player_update = post_data.get("player")

    if player_update["player_id"] != player_id:
        raise InvalidUsage("Player ID Mismatch", status_code=400)

    if player.display_name != player_update["display_name"]:
        audit_logger.info("API: Update player ID %s name from %s to %s" % (player_id, player.display_name,  player_update["display_name"]))
        try:
            player.updateDisplayName(player_update["display_name"])
        except UpdateError as e:
            if e.message:
                message = e.message
            else:
                message = e.error
            raise InvalidUsage(message, status_code=500)

    # get updated player object and return
    player = getPlayerByID(player_id)

    return jsonify(player=player.serialize())
