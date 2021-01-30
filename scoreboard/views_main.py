from flask import current_app as app
from flask import request, redirect, render_template, flash, abort, jsonify
from flask_login import current_user
from .functions import getTournaments, getPlayerByID, getTournamentByShortName
import re

@app.route('/')
def renderHome():
    ts_p = getTournaments(filter="past")
    past_tournaments = []

    for t in ts_p:
        past_tournaments.append(ts_p[t])

    ts_f = getTournaments(filter="future")
    future_tournaments = []
    for t in ts_f:
        future_tournaments.append(ts_f[t])

    ts_live = getTournaments(filter="live")
    live_tournaments = []
    for t in ts_live:
        live_tournaments.append(ts_live[t])

    return render_template('show_home.html.j2', past_tournaments=past_tournaments, future_tournaments=future_tournaments, live_tournaments=live_tournaments)


@app.route('/t/<short_name>')
def renderTourament(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html.j2', message=message)

    games = t.getGames()
    if not games or len(games) == 0:
        return render_template('show_coming_soon.html.j2', tournament=t)

    divisions = t.getDivisionNames()
    team_list = t.getTeams()

    team_infos = {}
    for team in team_list:
        team_id = team["team_id"]
        team_info = t.getTeamInfo(team_id)
        if team_info["roster"]:
            team_infos[team_id] = team_info

    pod_names = t.getPodNamesActive()
    group_names = t.getGroups()

    standings = t.getStandings()

    t.genTieFlashes()
    placings = t.getPlacings()

    site_message = t.getSiteMessage()

    return render_template('show_tournament.html.j2', tournament=t, games=games, standings=standings, grouped_standings=standings, group_names=group_names,
                           placings=placings, team_infos=team_infos, divisions=divisions, team_list=team_list, pods=pod_names, site_message=site_message, print_friendly=True)


@app.route('/t/<short_name>/div/<div>')
def renderTDiv(short_name, div):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html.j2', message=message)

    if not t.isGroup(div):
        abort(404)

    games = t.getGames(div)
    divisions = t.getDivisionNames()
    team_list = t.getTeams(div)
    team_infos = {}
    for team in team_list:
        team_id = team["team_id"]
        team_info = t.getTeamInfo(team_id)
        if team_info["roster"]:
            team_infos[team_id] = team_info

    pod_names = t.getPodNamesActive()

    standings = t.getStandings(div)
    grouped_standings = standings
    group_names = t.getGroups()


    placings = t.getPlacings(div=div)

    division_name = t.expandGroupAbbr(div)
    if division_name is None:
        division_name = "%s Division" % div
    site_message = t.getSiteMessage()

    return render_template('show_tournament.html.j2', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, group_names=group_names, divisions=divisions,
                           pods=pod_names, team_list=team_list, team_infos=team_infos, site_message=site_message, title_text=division_name, placings=placings)


@app.route('/t/<short_name>/pod/<pod>')
def renderTPod(short_name, pod):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html.j2', message=message)

    if not t.isGroup(pod):
        abort(404)

    games = t.getGames(pod=pod)
    division = t.getDivisionNames()
    standings = t.getStandings(pod=pod)
    grouped_standings = t.splitStandingsByGroup(standings)
    group_names = t.getGroups()

    team_list = t.getTeams(pod=pod)
    team_infos = {}
    for team in team_list:
        team_id = team["team_id"]
        team_info = t.getTeamInfo(team_id)
        if team_info["roster"]:
            team_infos[team_id] = team_info

    pods = t.getPodsActive()
    pod_names = t.getPodNamesActive()

    pod_name = t.expandGroupAbbr(pod)
    if pod_name is None:
        pod_name = "%s Pod" % pod
    site_message = t.getSiteMessage()

    return render_template('show_tournament.html.j2', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, group_names=group_names, divisions=division,
                           pods=pod_names, team_list=team_list, team_infos=team_infos, site_message=site_message, title_text=pod_name)


@app.route('/t/<short_name>/team/<team_id>')
def renderTTeam(short_name, team_id):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html.j2', message=message)

    if not team_id.isdigit():
        abort(404)

    team_id = int(team_id)

    if t.getTeam(team_id) is None:
        abort(404)

    divisions = t.getDivisionNames()
    div = t.getDivision(team_id)
    team_list = t.getTeams()
    pods = t.getPodsActive(team=team_id)
    pod_names = t.getPodNamesActive()

    games = t.getTeamGames(team_id)

    standings = []
    if pods:
        for pod in pods:
            standings += t.getStandings(None, pod)
    else:
        standings = t.getStandings()

    grouped_standings = t.splitStandingsByGroup(standings)
    group_names = t.getGroups()

    team = t.getTeam(team_id)
    team_info = t.getTeamInfo(team_id)
    site_message = t.getSiteMessage()

    return render_template('show_tournament.html.j2', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, group_names=group_names, divisions=divisions,
                           pods=pod_names, team_list=team_list, site_message=site_message, title_text=team, team_info=team_info)


@app.route('/t/<short_name>/multi/<group>')
def renderTGroup(short_name, group):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html.j2', message=message)

    games = []
    team_list = None
    if re.match(r".*\+.*", group):
        # team IDs separated by plus sign
        team_list = group.split("+")
    else:
        team_list = t.getTeamsLike(group)

    if not team_list:
        flash("Couldn't find any teams for %s" % group)
        rdir_string = "/t/%s" % t.short_name
        return redirect(rdir_string)

    for team_id in team_list:
        try:
            team_id = int(team_id)
        except ValueError:
            continue

        if t.getTeam(team_id) is not None:
            games.extend(t.getTeamGames(team_id))

    games.sort(key=lambda x: x.start_datetime)

    divisions = t.getDivisionNames()
    team_list = t.getTeams()

    pods = t.getPodsActive()
    pod_names = t.getPodNamesActive()

    standings = []
    if pods:
        for pod in pods:
            standings += t.getStandings(None, pod)
    else:
        standings = t.getStandings()

    grouped_standings = t.splitStandingsByGroup(standings)

    t.genTieFlashes()
    placings = t.getPlacings()

    site_message = t.getSiteMessage()

    return render_template('show_tournament.html.j2', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, divisions=divisions,
                       pods=pod_names, team_list=team_list, site_message=site_message, title_text="Combined")


#######################################
# Player Pages
#######################################
@app.route('/players')
@app.route('/p/<player_id>')
def renderPlayerInfo(player_id=None):
    show_admin_link = False

    if player_id:
        player = getPlayerByID(player_id)

        if not player:
            abort(404)

        if current_user.is_authenticated and (current_user.admin or current_user.site_admin):
            show_admin_link = True
    else:
        # no player ID asked for, we'll just return the page for search
        player = None

    return render_template("show_player.html.j2", player=player, show_admin_link=show_admin_link)

#######################################
# Special pages
#######################################
@app.route('/t/<short_name>/tv')
def renderTouramentTV(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html.j2', message=message)

    next_page = None
    if request.args.get('offset'):
        offset = request.args.get('offset')
        if offset.isdigit():
            offset = int(offset)
            games = t.getGames(offset=offset)
            next_page = offset + 25
            if next_page > 100:
                next_page = "0"
        else:
            games = t.getGames()
    else:
        games = t.getGames()

    division = t.getDivisionNames()
    team_list = t.getTeams()

    pods = t.getPodsActive()
    pod_names = t.getPodNamesActive()

    standings = []
    if pods:
        for pod in pods:
            standings += t.getStandings(None, pod)
    else:
        standings = t.getStandings()

    t.genTieFlashes()
    placings = t.getPlacings()

    site_message = t.getSiteMessage()

    return render_template('show_tv.html.j2', tournament=t, games=games, standings=standings, placings=placings, divisions=division, team_list=team_list,
                           pods=pod_names, site_message=site_message, next_page=next_page)


@app.route('/t/<short_name>/print')
def renderTouramentPrint(short_name):
    t = getTournamentByShortName(short_name)
    if not t:
        abort(404)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html.j2', message=message)

    games = t.getGames()
    division = t.getDivisionNames()
    team_list = t.getTeams()

    pods = t.getPodsActive()
    pod_names = t.getPodNamesActive()

    standings = []
    if pods:
        for pod in pods:
            standings += t.getStandings(None, pod)
    else:
        standings = t.getStandings()

    t.genTieFlashes()
    placings = t.getPlacings()

    site_message = t.getSiteMessage()

    return render_template('show_print.html.j2', tournament=t, games=games, standings=standings, placings=placings, divisions=division, team_list=team_list,
                           pods=pod_names, site_message=site_message)


#######################################
# Static pages
#######################################
@app.route('/faq')
def renderFAQ():
    return render_template('faq.html.j2')


#######################################
# Error pages
#######################################
@app.errorhandler(404)
def page_not_found(message):
    if request.path.startswith("/api"):
        return jsonify(message="These aren't the droids you're looking for", code=404), 404
    else:
        return render_template("errors/404.html.j2", title='404', message=message), 404


@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith("/api"):
        return jsonify(message="ratelimit exceeded %s" % e.description, code=429), 429
    else:
        return render_template("errors/error.html.j2", error_code="429", message=e.name), 429
