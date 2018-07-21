from app import app
from flask import request, redirect, render_template, flash
from functions import getTournamets, getTournamentByID, getTournamentID
import re

@app.route('/')
def renderHome():
    ts = getTournamets()
    tournaments = []

    for t in ts:
        tournaments.append(ts[t])

    tournaments = sorted(tournaments)

    return render_template('show_home.html', tournaments=tournaments)


@app.route('/t/<short_name>')
def renderTourament(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        # TODO: this flashes and redirects you to the main page where there is no flash display
        flash("Unknown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html', message=message)

    games = t.getGames()
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

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, placings=placings,
                           divisions=divisions, team_list=team_list, pods=pod_names, site_message=site_message, print_friendly=True)


@app.route('/t/<short_name>/div/<div>')
def renderTDiv(short_name, div):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unknown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html', message=message)

    if not t.isGroup(div):
        flash("Invalid division")
        rdir_string = "/t/%s" % t.short_name
        return redirect(rdir_string)

    games = t.getGames(div)
    divisions = t.getDivisionNames()
    team_list = t.getTeams(div)

    pods = t.getPodsActive(div=div)
    pod_names = t.getPodNamesActive()

    standings = []
    if pods:
        for pod in pods:
            standings += t.getStandings(div, pod)
    else:
        standings = t.getStandings(div)

    grouped_standings = t.splitStandingsByGroup(standings)

    division_name = t.expandGroupAbbr(div)
    if division_name is None:
        division_name = "%s Division" % div
    site_message = t.getSiteMessage()

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, divisions=divisions,
                           pods=pod_names, team_list=team_list, site_message=site_message, title_text=division_name)


@app.route('/t/<short_name>/pod/<pod>')
def renderTPod(short_name, pod):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unknown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html', message=message)

    if not t.isGroup(pod):
        flash("Invalid Pod")
        rdir_string = "/t/%s" % t.short_name
        return redirect(rdir_string)

    games = t.getGames(pod=pod)
    division = t.getDivisionNames()
    standings = t.getStandings(pod=pod)
    grouped_standings = t.splitStandingsByGroup(standings)

    team_list = t.getTeams(pod=pod)

    pods = t.getPodsActive()
    pod_names = t.getPodNamesActive()

    pod_name = t.expandGroupAbbr(pod)
    if pod_name is None:
        pod_name = "%s Pod" % pod
    site_message = t.getSiteMessage()

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, divisions=division,
                           pods=pod_names, team_list=team_list, site_message=site_message, title_text=pod_name)


@app.route('/t/<short_name>/team/<team_id>')
def renderTTeam(short_name, team_id):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unknown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html', message=message)

    if not team_id.isdigit():
        flash("Invalid team ID, must be integer")
        rdir_string = "/t/%s" % t.short_name
        return redirect(rdir_string)

    team_id = int(team_id)

    if t.getTeam(team_id) is None:
        flash("Team ID %s doesn't exist" % team_id)
        rdir_string = "/t/%s" % t.short_name
        return redirect(rdir_string)

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

    team = t.getTeam(team_id)
    team_info = t.getTeamInfo(team_id)
    site_message = t.getSiteMessage()

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, divisions=divisions,
                           pods=pod_names, team_list=team_list, site_message=site_message, title_text=team, team_warning=True, team_info=team_info)


@app.route('/t/<short_name>/multi/<group>')
def renderTGroup(short_name, group):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unknown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html', message=message)

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

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, grouped_standings=grouped_standings, divisions=divisions,
                       pods=pod_names, team_list=team_list, site_message=site_message, title_text="Combined")


#######################################
# Special pages
#######################################
@app.route('/t/<short_name>/tv')
def renderTouramentTV(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unknown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html', message=message)

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

    return render_template('show_tv.html', tournament=t, games=games, standings=standings, placings=placings, divisions=division, team_list=team_list,
                           pods=pod_names, site_message=site_message, next_page=next_page)


@app.route('/t/<short_name>/print')
def renderTouramentPrint(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unknown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

    message = t.getDisableMessage()
    if message:
        return render_template('site_down.html', message=message)

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

    return render_template('show_print.html', tournament=t, games=games, standings=standings, placings=placings, divisions=division, team_list=team_list,
                           pods=pod_names, site_message=site_message)


#######################################
# Static pages
#######################################
@app.route('/faq')
def renderFAQ():
    return render_template('faq.html')
