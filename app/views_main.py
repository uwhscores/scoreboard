from app import app
from flask import request, redirect, render_template
from functions import *

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
        flash("Unkown Tournament Name")
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

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings,\
        placings=placings, divisions=division, team_list=team_list, pods = pod_names, site_message=site_message)
#         standings=standings, games=games, pods=pod_names, titleText=titleText, \
#         placings=placings, divisions=divisions, team_list=team_list, site_message=getParam('site_message'))


@app.route('/t/<short_name>/div/<div>')
def renderTDiv(short_name, div):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
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
    division = t.getDivisionNames()
    standings = t.getStandings(div)
    team_list = t.getTeams(div)

    site_message = t.getSiteMessage()

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, divisions=division,\
        team_list=team_list, site_message=site_message)

@app.route('/t/<short_name>/pod/<pod>')
def renderTPod(short_name, pod):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
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
    team_list = t.getTeams(pod=pod)

    pods = t.getPodsActive()
    pod_names = t.getPodNamesActive()

    site_message = t.getSiteMessage()

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, divisions=division,\
        pods = pod_names, team_list=team_list, site_message=site_message)

@app.route('/t/<short_name>/team/<team_id>')
def renderTTeam(short_name, team_id):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
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
    titleText = t.getTeam(team_id)

    if titleText == None:
        flash("Team ID %s doesn't exist" % team_id)
        rdir_string = "/t/%s" % t.short_name
        return redirect(rdir_string)

    divisions = t.getDivisionNames()
    div = t.getDivision(team_id)
    team_list = t.getTeams(div)
    #pod_names = getPodNamesActive(division)

    #teams = []

    games = t.getTeamGames(team_id)
    standings = t.getStandings()

    site_message = t.getSiteMessage()

    return render_template('show_tournament.html', tournament=t, games=games, standings=standings, divisions=divisions,\
        team_list=team_list, site_message=site_message)

#######################################
## Static pages
#######################################
@app.route('/faq')
def renderFAQ():
    return render_template('faq.html')
