from flask import current_app as app
from flask import request, redirect, render_template, flash
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
import json
import re

from scoreboard import global_limiter, audit_logger
from scoreboard.functions import getTournaments, getTournamentByID, getUserByID, getTournamentID, getUserList, authenticate_user, addUser, validateResetToken, validateJSONSchema
from scoreboard.exceptions import UserAuthError

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

    return render_template('/admin/show_admin.html', tournaments=tournaments, user=current_user)


@app.route("/admin/t/<short_name>")
@login_required
def renderTAdmin(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

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
    redraws = []
    for div in divisions:
        l = t.getRedraw(div)
        if l:
            redraws.append(div)
    pods = t.getPodsActive()
    if pods:
        for pod in pods:
            l = t.getRedraw(None, pod=pod)
            if l:
                redraws.append(pod)

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

    return render_template('admin/tournament_admin.html', tournament=t, ties=ties, disable_message=t.getDisableMessage(), site_message=t.getSiteMessage(),
                           redraws=redraws, authorized_users=authorized_users, unauthorized_users=unauthorized_users)

@app.route('/admin/t/<short_name>/scores', methods=['GET'])
@login_required
def renderScores(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    games = t.getGames()
    return render_template('/admin/show_update.html', games=games, tournament=t)


@app.route('/admin/t/<short_name>/scores/<game_id>', methods=['GET'])
@login_required
def renderScoreInput(short_name, game_id):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    game = t.getGame(game_id)
    if not game:
        return render_template('show_error.html', error_message="404: Unknown Game ID"), 404
    if (game.score_b == "--"):
        game.score_b = "0"
    if (game.score_w == "--"):
        game.score_w = "0"

    if (game.black_tid < 0 or game.white_tid < 0):
        flash('Team(s) not determined yet. Cannot set score')
        return redirect("/admin/t/%s" % t.short_name)

    return render_template('/admin/update_single.html', tournament=t, game=game)


@app.route('/admin/t/<short_name>/scores', methods=['POST'])
@login_required
def updateScore(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    form = request.form
    game = {}
    game['gid'] = int(form.get('gid'))
    game['score_b'] = int(form.get('score_b'))
    game['score_w'] = int(form.get('score_w'))
    game['black_tid'] = int(form.get('btid'))
    game['white_tid'] = int(form.get('wtid'))
    game['pod'] = form.get('pod')

    game['forfeit_w'] = form.get('forfeit_w')
    game['forfeit_b'] = form.get('forfeit_b')

    audit_logger.info("Score for game %s:%s being updated by %s(%s): black: %s, white:%s" %
                      (t.short_name, game['gid'], current_user.short_name, current_user.user_id, game['score_b'], game['score_w']))
    t.updateGame(game)

    return redirect("/admin/t/%s/scores" % short_name)


@app.route('/admin/t/<short_name>/gametiming')
@login_required
def view_gametimerules(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    timing_rules = t.getTimingRuleSet()

    return render_template('/admin/view_timing_rules.html', tournament=t, timing_rules=timing_rules)


@app.route('/admin/t/<short_name>/editgametiming')
@login_required
def edit_gametimerules(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    timing_rules = t.getTimingRuleSet()

    return render_template('/admin/edit_timing_json.html', tournament=t, timing_rules=timing_rules)


@app.route('/admin/t/<short_name>/update/updategametiming', methods=['POST'])
@login_required
def update_gametimerules(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    raw_input = request.form.get('timing_json')
    try:
        timing_json = json.loads(raw_input)
    except ValueError:
        flash("Invalid JSON")
        return redirect("/admin/t/%s/editgametiming" % t.short_name)

    (valid, message) = validateJSONSchema(timing_json, "timing_rule_set")
    if not valid:
        flash("Your JSON didn't match the schema: %s" % message)
        return redirect("/admin/t/%s/editgametiming" % t.short_name)

    res = t.updateTimingRules(timing_json['timing_rule_set'])

    if not res == 1:
        flash("There was a server side error updating")
        return redirect("/admin/t/%s/editgametiming" % t.short_name)
    else:
        return redirect("/admin/t/%s/gametiming" % t.short_name)


@app.route('/admin/t/<short_name>/redraw', methods=['POST'])
@app.route('/admin/t/<short_name>/redraw/<group>', methods=['GET'])
@login_required
def redraw(short_name, group=None):
    if request.method == 'GET':
        tid = getTournamentID(short_name)
        if tid < 1:
            flash("Unkown Tournament Name")
            return redirect("/admin")

        t = getTournamentByID(tid)

        if not t.isAuthorized(current_user):
            flash("You are not authorized for this tournament")
            return redirect("/admin")

        if not t.isGroup(group):
            flash("Invalid division or pod on Redraw path")
            return redirect("/admin/t/%s" % short_name)

        if t.isPod(group):
            team_list = t.getTeams(None, group)
        else:
            team_list = t.getTeams(group, None)

        group_name = t.expandGroupAbbr(group)

        if not group_name:
            group_name = "%s Group" % group

        return render_template('/admin/redraw.html', tournament=t, group=group, group_name=group_name, teams=team_list)

    if request.method == 'POST':
        tid = getTournamentID(short_name)
        if tid < 1:
            flash("Unkown Tournament Name")
            return redirect(request.url_root)

        t = getTournamentByID(tid)

        if not t.isAuthorized(current_user):
            flash("You are not authorized for this tournament")
            return redirect("/admin")

        group = request.form.get('group')
        # check group is valid

        # get list of ids that need a redraw
        if t.isPod(group):
            redraw_ids = t.getRedraw(None, pod=group)
        else:
            redraw_ids = t.getRedraw(group)

        check = []
        redraws = []
        for e in request.form:
            match = re.search('^T(\d+)$', e)
            if match:
                team_id = match.group(1)
                redraw_id = request.form.get(e)
                check.append(redraw_id)
                if redraw_id == "":
                    flash("You missed a team ID")
                    return redirect("/admin/t/%s/redraw/%s" % (short_name, group))
                if redraw_id not in redraw_ids:
                    flash("Invalid ID, can't find in redraws")
                    return redirect("/admin/t/%s/redraw/%s" % (short_name, group))
                redraws.append({'team_id': team_id, 'redraw_id': redraw_id})

        # check that each redraw ID is unique
        if len(check) > len(set(check)):
            flash("You put a team ID in twice!")
            return redirect("/admin/t/%s/redraw/%s" % (short_name, group))

        res = t.redrawTeams(group, redraws)
        if res == 0:
            return redirect("/admin/t/%s" % short_name)
        else:
            return redirect("/admin/t/%s/redraw/%s" % (short_name, res))


@app.route('/admin/update_config', methods=['POST', 'GET'])
@login_required
def updateConfigPost():
    if request.method == 'GET':
        flash("You're not supposed to do that")
        return redirect("/admin")
    elif request.method == 'POST':
        t = None
        if request.form.get('tid'):
            tid = request.form.get('tid')
            t = getTournamentByID(tid)
        if not t:
            flash("Invalid tournament ID")
            return redirect('/admin')
    else:
        return redirect('/admin')

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    audit_logger.info("Some sort of config update by %s(%s) - you should really log this better" % (current_user.short_name, current_user.user_id))
    t.updateConfig(request.form)

    return redirect("/admin/t/%s" % t.short_name)


@app.route('/admin/t/<short_name>/update_admins')
@login_required
def doUdateTournamentLogins(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    if not t.isAuthorized(current_user):
        flash("You are not authorized for this tournament")
        return redirect("/admin")

    if request.args.get("add"):
        user_id = request.args.get("add")
        user = getUserByID(user_id)
        if user:
            audit_logger.info("Added %s(%s) as admin for %s by %s(%s)" % (user.short_name, user.user_id, t.short_name, current_user.short_name, current_user.user_id))
            t.addAuthorizedID(user_id)
        else:
            flash("Unknown user ID to add")
    elif request.args.get("remove"):
        user_id = request.args.get("remove")
        user = getUserByID(user_id)
        if user_id == current_user.user_id:
            flash("You can't remove yourself")
            return redirect(request.referrer)
        if user:
            audit_logger.info("Removed %s(%s) as admin for %s by %s(%s)" % (user.short_name, user.user_id, t.short_name, current_user.short_name, current_user.user_id))
            t.removeAuthorizedID(user_id)
        else:
            flash("Unkown user ID to remove")
    else:
        flash("Invalid add/remove syntax, go away")

    return redirect(request.referrer)


#######################################
# Login/Logout/passwd reset
#######################################
@app.route('/login', methods=['GET'])
def show_login():
    return render_template('admin/show_login.html')


@app.route('/login', methods=['POST'])
@global_limiter.limit("5/minute;20/hour")
def do_login():
    email = None

    form = request.form
    if form.get('email'):
        email = form.get('email')
    if form.get('password'):
        password = form.get('password')

    if email:
        user_id = None
        try:
            user_id = authenticate_user(email, password, ip_addr=request.remote_addr)
        except UserAuthError as e:
            flash(e.message)

        if user_id:
            login_user(getUserByID(user_id))
            audit_logger.info("Successful login by %s(%s)" % (current_user.short_name, current_user.user_id))
            return redirect("/admin")
    else:
        return render_template('show_error.html', error_message="You are not a person")

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
        return render_template('show_error.html', error_message="Invalid or missing token")

    return render_template('admin/show_pwreset.html', token=token)


@app.route('/login/reset', methods=['POST'])
def set_password():
    form = request.form
    if form.get('token'):
        token = form.get('token')
        user_id = validateResetToken(token)
    else:
        return render_template('show_error.html', error_message="You go away now")

    if not user_id:
        return render_template('show_error.html', error_message="You go away now")

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
    return render_template('admin/show_users.html', users=users)


@app.route('/admin/user/add',  methods=['GET'])
@login_required
def renderAddUser():
    if not current_user.site_admin:
        flash("You are not authorized for user management")
        return redirect("/admin")

    return render_template('admin/user_add.html')


@app.route('/admin/user/add',  methods=['POST'])
@login_required
def doAddUser():
    if not current_user.site_admin:
        flash("You are not authorized for user management")
        return redirect("/admin")

    form = request.form
    new_user = {}

    if form.get('short_name'):
        new_user['short_name'] = form.get('short_name')
    else:
        flash("Issue with short name")
        return redirect("/admin/user/add")

    if form.get('email'):
        new_user['email'] = form.get('email')
    else:
        flash("Issue with email")
        return redirect("/admin/user/add")

    # For now not allow users to be added as site-admin
    # saftey measure cause I'm not there yet, plubming works though
    # enable input on user_add.html and uncomment below

    # if form.get('site-admin'):
    #    new_user['site-admin'] = True
    # else:
    #    new_user['site-admin'] = False
    new_user['site-admin'] = False

    if form.get('admin'):
        new_user['admin'] = True
    else:
        new_user['admin'] = False

    audit_logger.info("Created new user for %s by %s(%s)" % (new_user['email'], current_user.short_name, current_user.user_id))
    res = addUser(new_user)

    if not res['success']:
        flash(res['message'])
        return redirect("/admin/user/add")

    # ideally here is where you would email out the reset token

    return render_template("/admin/show_new_user.html", email=new_user['email'], token=res['token'], user_id=res['user_id'])


@app.route("/admin/user/<user_id>")
@login_required
def renderUserManager(user_id):
    if not current_user.site_admin:
        flash("You are not authorized for user management")
        return redirect("/admin")

    user = getUserByID(user_id)
    if not user:
        flash("Unknown User")
        return redirect("/admin/users")

    ts = getTournaments()
    tournaments = []
    for t in ts:
        if ts[t].is_active:
            tournaments.append(ts[t])

    tournaments = sorted(tournaments)

    return render_template("/admin/show_user_admin.html", user=user, tournaments=tournaments)


@app.route('/admin/user/<user_id>/reset')
@login_required
def renderResetUserPass(user_id):
    if not current_user.site_admin:
        flash("You are not authorized for user management")
        return redirect("/admin")

    token = None
    user = getUserByID(user_id)
    if user:
        audit_logger.info("Password reset for %s(%s) by %s(%s)" % (user.short_name, user.user_id, current_user.short_name, current_user.user_id))
        token = user.resetUserPass()
    else:
        flash("That's not a real user")
        return redirect("/admin/users")

    return render_template('admin/show_passwd_reset.html', user=user, token=token)


@app.route('/admin/user/<user_id>/update')
@login_required
def doUpdateUser(user_id):
    if not current_user.site_admin:
        flash("You are not authorized for user management")
        return redirect("/admin")

    user = getUserByID(user_id)

    if not user:
        flash("User not found, stop messing around")
        return redirect("/admin/users")

    if request.args.get('admin'):
        admin = request.args.get('admin')
        audit_logger.info("Change admin status %s for %s(%s) by %s(%s)" % (admin, user.short_name, user.user_id, current_user.short_name, current_user.user_id))
        if admin == "1":
            user.setAdmin(True)
        elif admin == "0":
            user.setAdmin(False)
        else:
            flash("You're screwing with me")

    if request.args.get('active'):
        if current_user.user_id == user.user_id:
            flash("You can't deactivate yourself!")
            return redirect(request.referrer)

        active = request.args.get('active')
        audit_logger.info("Change active status %s for %s(%s) by %s(%s)" % (active, user.short_name, user.user_id, current_user.short_name, current_user.user_id))
        if active == "1":
            user.setActive(True)
        elif active == "0":
            user.setActive(False)
        else:
            flash("You're screwing with me")

    return redirect(request.referrer)
