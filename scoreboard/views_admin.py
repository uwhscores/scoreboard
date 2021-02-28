from flask import current_app as app
from flask import jsonify, request, redirect, render_template, flash, abort
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
import json

from scoreboard import global_limiter, audit_logger
from scoreboard.exceptions import UserAuthError, UpdateError, InvalidUsage
from scoreboard.functions import getTournaments, getTournamentByShortName, getUserByID, getUserList, authenticate_user, validateResetToken, \
                                 validateJSONSchema, getPlayerByID, getDB
from scoreboard.models import User

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/login"


@global_limiter.request_filter
def ip_whitelist():
    return request.remote_addr == "127.0.0.1"


@login_manager.user_loader
def load_user(user_id):
    return getUserByID(user_id)


@app.route("/admin")
@login_required
def renderAdmin():
    ts = getTournaments()
    tournaments = []
    for t in ts:
        if ts[t].is_active:
            tournaments.append(ts[t])

    tournaments = sorted(tournaments)

    return render_template('/admin/pages/admin.html.j2', tournaments=tournaments, user=current_user)


@app.route("/admin/t/<short_name>")
@login_required
def renderTAdmin(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    # pods = getPodsActive()
    #
    # teams = []
    # if pods:
    #     for pod in pods:
    #         teams += getStandings(None, pod)
    # else:
    #     teams = getStandings()

    team_list = t.getTeams()

    standings = []
    pods = t.getPodsActive()
    if pods:
        for pod in pods:
            standings += t.getStandings(None, pod)
    else:
        standings = t.getStandings()

    t.genTieFlashes()
    ties = t.getTies()

    divisions = t.getDivisions()

    # stats = getTournamentStats()

    authorized_users = []
    unauthorized_users = []

    authorized_ids = t.getAuthorizedUserIDs()
    users = getUserList()
    for u in users:
        if authorized_ids and u.user_id in authorized_ids:
            authorized_users.append(u)
        else:
            if u.admin or u.site_admin or not u.active:
                continue
            unauthorized_users.append(u)

    return render_template('admin/pages/tournament_admin.html.j2', tournament=t, ties=ties, blackout_message=t.getBlackoutMessage(), site_message=t.getSiteMessage(),
                           authorized_users=authorized_users, unauthorized_users=unauthorized_users)


@app.route('/admin/t/<short_name>', methods=['PUT'])
@login_required
def updateTournamentConfig(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        raise InvalidUsage("Tournament not found", status_code=404)

    if not t.isAuthorized(current_user):
        raise InvalidUsage("You are not authorized for this tournament", status_code=403)

    app.logger.debug(request.json)
    (valid, message) = validateJSONSchema(request.json, "tournament_config")
    if not valid:
        raise InvalidUsage(message, status_code=400)

    config_name = request.json['config_name']
    if config_name in request.json:
        config_value = request.json[config_name]
    else:
        raise InvalidUsage(f"JSON missing object for {config_name}", status_code=400)

    # audit_logger.info("Config update for %s:%s by %s(%s)" % (short_name, config_id, current_user.short_name, current_user.user_id))
    audit_logger.info(f"Config change requested: {short_name} {current_user.short_name} ({current_user.user_id}) - {config_name}")
    try:
        t.updateConfig(config_name, config_value)
    except UpdateError as e:
        raise InvalidUsage(f"Update failed: {e.message}", status_code=400)

    return jsonify(success=True, config=config_value)


@app.route('/admin/t/<short_name>/games', methods=['GET'])
@login_required
def renderScores(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    games = t.getGames()
    return render_template('/admin/pages/admin_games.html.j2', games=games, tournament=t)


@app.route('/admin/t/<short_name>/games/<game_id>', methods=['GET'])
@login_required
def renderScoreInput(short_name, game_id):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    game = t.getGame(game_id)
    if not game:
        abort(404)
    if (game.score_b == "--"):
        game.score_b = "0"
    if (game.score_w == "--"):
        game.score_w = "0"

    if (game.black_tid < 0 or game.white_tid < 0):
        flash('Team(s) not determined yet. Cannot set score')
        return redirect("/admin/t/%s" % t.short_name)

    return render_template('/admin/pages/admin_game_update.html.j2', tournament=t, game=game)


@app.route('/admin/t/<short_name>/games/<game_id>', methods=['PUT'])
@login_required
def updateScore(short_name, game_id):
    # TODO: Fix mixed response patterns
    t = getTournamentByShortName(short_name)
    if not t:
        raise InvalidUsage("tournament not found", status_code=404)

    if not t.isAuthorized(current_user):
        raise InvalidUsage("not authorized", status_code=403)

    body = request.json

    (valid, message) = validateJSONSchema(body, "admin_score")
    if not valid:
        raise InvalidUsage(message, status_code=400)

    score = body['score']
    game = t.getGame(game_id)
    if not game:
        raise InvalidUsage("Game not found", status_code=404)

    audit_logger.info("Score for game %s:%s being updated by %s(%s): black: %s, white:%s" %
                      (t.short_name, game.gid, current_user.short_name, current_user.user_id, score['score_b'], score['score_w']))

    try:
        game.updateScore(score)
    except UpdateError as e:
        app.logger.debug(f"Error updating game: {e}")
        flash(f"Error updating game: {e.message}")
        return jsonify(success=False, message="e.message", url=f"/admin/t/{short_name}/games")

    # return redirect("/admin/t/%s/games" % short_name, code=302)
    return jsonify(success=True, url=f"/admin/t/{short_name}/games")

@app.route('/admin/t/<short_name>/gametiming')
@login_required
def view_gametimerules(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    timing_rules = t.getTimingRuleSet()

    return render_template('/admin/pages/admin_timing_rules.html.j2', tournament=t, timing_rules=timing_rules)


@app.route('/admin/t/<short_name>/editgametiming')
@login_required
def edit_gametimerules(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    timing_rules = t.getTimingRuleSet()

    return render_template('/admin/pages/admin_edit_timing.html.j2', tournament=t, timing_rules=timing_rules)

#######################################
# Login/Logout/passwd reset
#######################################
@app.route('/login', methods=['GET'])
def show_login():
    return render_template('admin/pages/login.html.j2')


@app.route('/login', methods=['POST'])
@global_limiter.limit("5/minute;20/hour")
def do_login():
    email = None
    password = None

    form = request.form

    if form.get('email'):
        email = form.get('email')
    if form.get('password'):
        password = form.get('password')

    app.logger.debug(f"Attempting login {email} {password}")
    if email:
        user_id = None
        try:
            user_id = authenticate_user(email, password, ip_addr=request.remote_addr)
        except UserAuthError as e:
            app.logger.debug(f"User auth failed {e}")
            flash(e.message)

        if user_id:
            login_user(getUserByID(user_id))
            audit_logger.info("Successful login by %s(%s)" % (current_user.short_name, current_user.user_id))
            return redirect("/admin")
    else:
        return render_template('errors/error.html.j2', error_message="You are not a person")

    audit_logger.info("Failed login attempt w/ email: %s" % email)
    return redirect("/login")


@app.route('/logout')
@login_required
def logout():
    audit_logger.info("Logout for %s(%s)" % (current_user.short_name, current_user.user_id))
    logout_user()
    return redirect('/')


@app.route('/login/reset', methods=['GET'])
def pw_reset():

    token = None

    if request.args.get('token'):
        token = request.args.get('token')
        user_id = validateResetToken(token)

    # token wasn't supplied or doesn't belong to a user
    if not token or not user_id:
        return render_template('errors/error.html.j2', error_message="Invalid or missing token")

    return render_template('admin/pages/password_reset.html.j2', token=token)


@app.route('/login/reset', methods=['POST'])
def set_password():
    form = request.form
    if form.get('token'):
        token = form.get('token')
        user_id = validateResetToken(token)
    else:
        return render_template('errors/error.html.j2', error_message="You go away now")

    if not user_id:
        return render_template('errors/error.html.j2', error_message="You go away now")

    if form.get('password1') and form.get('password2'):
        password1 = form.get('password1')
        password2 = form.get('password2')

        if len(password1) < 6:
            flash("Password too short, must be at least 6 characters")
            return redirect("/login/reset?token=%s" % token)

        if password1 != password2:
            flash("Passwords do not match, try again")
            return redirect("/login/reset?token=%s" % token)

        user = getUserByID(user_id)
        if user:
            user.setPassword(password1)
        else:
            flash("Something went wrong")
            return redirect("/login")

        audit_logger.info("User password reset for %s" % user_id)
        flash("New password set, please login")

        return redirect("/login")


#######################################
# User Management
#######################################
@app.route('/admin/users')
@login_required
def renderShowUsers():
    if not current_user.site_admin:
        flash("You are not authorized for user management")
        return redirect("/admin")

    users = getUserList()
    return render_template('admin/pages/admin_users.html.j2', users=users)


@app.route("/admin/users/<user_id>")
@login_required
def renderUserManager(user_id):
    # TODO: useless page, remove or improve?
    if not current_user.site_admin:
        flash("You are not authorized for user management")
        return redirect("/admin")

    user = getUserByID(user_id)
    if not user:
        flash("Unknown User")
        return redirect("/admin")

    return render_template('admin/pages/admin_users.html.j2', users=[user])

# create new user
@app.route('/admin/users', methods=["POST"])
@login_required
def createUser():
    if not current_user.site_admin:
        raise InvalidUsage("Not authorized", status_code=403)

    user_json = request.json

    (valid, message) = validateJSONSchema(user_json, "user_create")
    if not valid:
        raise InvalidUsage(message, status_code=400)

    try:
        new_user = User.create(user_json['user'], getDB())
    except UpdateError as e:
        raise InvalidUsage(e.message, status_code=400)

    try:
        new_user.sendUserEmail(template="welcome")
        email_error = None
    except UpdateError as e:
        email_error = e.message

    return jsonify(success=True, user=new_user.serialize(), token=new_user.getResetToken(), email_error=email_error)

# update user route
@app.route("/admin/users/<user_id>", methods=['PUT'])
@login_required
def updateUser(user_id):
    if not current_user.site_admin:
        raise InvalidUsage("not authorized for user management", status_code=403)

    user_json = request.json
    (valid, message) = validateJSONSchema(user_json, "user")
    if not valid:
        raise InvalidUsage(message, status_code=400)

    user = getUserByID(user_json['user']['user_id'])

    if not user:
        raise InvalidUsage("user not found", status_code=404)

    if 'admin' in user_json['user']:
        new_status = user_json['user']['admin']

        try:
            user.setAdmin(new_status)
        except UpdateError as e:
            raise InvalidUsage(e.message, status_code=400)
        audit_logger.info(f"Change admin status {new_status} for {user.short_name}({user.user_id}) by {current_user.short_name}({current_user.user_id})")

    if 'active' in user_json['user']:
        new_status = user_json['user']['active']

        try:
            user.setActive(new_status)
        except UpdateError as e:
            raise InvalidUsage(e.message, status_code=400)
        audit_logger.info(f"Change active status {new_status} for {user.short_name}({user.user_id}) by {current_user.short_name}({current_user.user_id})")

    token = None
    if 'reset_password' in user_json['user'] and user_json['user']['reset_password'] is True:
        token = user.createResetToken(by_admin=True)
        try:
            user.sendUserEmail(template="pwreset", pwreset_by_admin=True)
            email_error = None
        except UpdateError as e:
            email_error = e.message
        audit_logger.info("Password reset for %s(%s) by %s(%s)" % (user.short_name, user.user_id, current_user.short_name, current_user.user_id))

    response = {'success': True, 'user': user.serialize()}
    if token:
        response['token'] = token
        response['email_error'] = email_error
    return jsonify(response)


#######################################
# Player Management
#######################################
@app.route('/admin/player/<player_id>')
@login_required
def adminPlayer(player_id):
    if not (current_user.admin or current_user.site_admin):
        flash("You are not authorized to edit players")
        return redirect("/admin")

    player = getPlayerByID(player_id)

    if not player:
        abort(404, "Player not found")

    return render_template('admin/pages/admin_player.html.j2', player=player)


@app.route('/admin/player/<player_id>', methods=["PUT"])
@login_required
def updatePlayer(player_id):
    app.logger.debug(f"Updating player {player_id}")
    player = getPlayerByID(player_id)

    if not player:
        raise InvalidUsage("Player not found", status_code=404)

    player_json = request.json
    (valid, message) = validateJSONSchema(player_json, "player")
    if not valid:
        raise InvalidUsage(message, status_code=400)

    try:
        audit_logger.info(f"Player change submitted by {current_user.short_name} ({current_user.user_id})")
        player.updateDisplayName(player_json['player']['display_name'])
    except UpdateError as e:
        raise InvalidUsage(f"Error updating {e}", status_code=500)

    return jsonify(success=True)
