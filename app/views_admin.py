from app import app
from flask import request
from functions import *

@app.route("/admin")
def renderAdmin():
    ts = getTournamets()
    tournaments = []
    for t in ts:
        tournaments.append(ts[t])

    tournaments = sorted(tournaments)

    return render_template('/admin/show_admin.html', tournaments=tournaments)

@app.route("/admin/t/<short_name>")
def renderTAdmin(short_name):
    tid = getTournamentID(short_name)
    if tid < 1:
        flash("Unkown Tournament Name")
        return redirect(request.url_root)

    t = getTournamentByID(tid)

	# pods = getPodsActive()
    #
	# teams = []
	# if pods:
	# 	for pod in pods:
	# 		teams += getStandings(None, pod)
	# else:
	# 	teams = getStandings()

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
    redraws= []
    for div in divisions:
        l = t.getRedraw(div)
        if l:
            redraws.append(div)

	# stats = getTournamentStats()

    return render_template('admin/tournament_admin.html', tournament=t, ties=ties,\
        disable_message=t.getDisableMessage(), site_message=t.getSiteMessage(),\
        redraws=redraws)


@app.route('/admin/t/<short_name>/redraw', methods=['POST'])
@app.route('/admin/t/<short_name>/redraw/<div>', methods=['GET'])
def redraw(short_name, div=None):
    if request.method == 'GET':
        tid = getTournamentID(short_name)
        if tid < 1:
            flash("Unkown Tournament Name")
            return redirect("/admin")

        t = getTournamentByID(tid)

        if not t.isGroup(div):
            flash("Invalid division on Redraw path")
            return redirect("/admin/t/%s" % short_name)

        team_list = t.getTeams(div, None)

        div_name = t.expandGroupAbbr(div)
        if div_name:
        	div_name = div_name
        else:
        	div_name = "%s Division" % div.upper()

        return render_template('/admin/redraw.html', tournament=t, div=div, div_name=div_name, teams=team_list )
    if request.method == 'POST':
        tid = getTournamentID(short_name)
        if tid < 1:
            flash("Unkown Tournament Name")
            return redirect(request.url_root)

        t = getTournamentByID(tid)

        div = request.form.get('div')
        # check div is valid

        # get list of ids that need a redraw
        redraw_ids = t.getRedraw(div)

    	check=[]
    	redraws=[]
    	for e in request.form:
            match = re.search('^T(\d+)$', e)
            if match:
                team_id = match.group(1)
                redraw_id = request.form.get(e)
                check.append(redraw_id)
                if redraw_id == "":
                    flash("You missed a team ID")
                    return redirect("/admin/t/%s/redraw/%s" % (short_name, div))
                if redraw_id not in redraw_ids:
                    flash("Invalid ID, can't find in redraws")
                    return redirect("/admin/t/%s/redraw/%s" % (short_name, div))
                redraws.append({'team_id':team_id, 'redraw_id':redraw_id})

    	# check that each redraw ID is unique
    	if len(check) > len(set(check)):
    		flash("You put a team ID in twice!")
    		return redirect("/admin/t/%s/redraw/%s" % (short_name, div))

        res = t.redraw_teams(div, redraws)
        if res == 0:
            return redirect("/admin/t/%s" % short_name)
        else:
            return redirect("/admin/t/%s/redraw/%s" % (short_name, res))

@app.route('/admin/update', methods=['POST','GET'])
#@basic_auth.required
def renderUpdate():
    if request.method =='GET':
        if request.args.get('gid'):
            if request.args.get('tid'):
                t = getTournamentByID(request.args.get('tid'))
                if not t:
                    flash("Invalid tournament ID")
                    return redirect('/admin')
            else:
                return redirect('/admin')

            game = t.getGame( request.args.get('gid') )
            if ( game.score_b == "--"):
                game.score_b = "0"
            if ( game.score_w == "--"):
                game.score_w = "0"

            if ( game.black_tid < 0 or game.white_tid < 0):
                flash('Team(s) not determined yet. Cannot set score')
                return redirect("/admin/t/%s" % t.short_name)

            return render_template('/admin/update_single.html', tournament=t, game=game)

        elif request.args.get('tid'):
            t = getTournamentByID(request.args.get('tid'))

            games = t.getGames()
            return render_template('/admin/show_update.html', games=games, tournament=t)
        else:
            return redirect('/admin')

    elif request.method == 'POST':
        if request.form.get('tid'):
            tid = request.form.get('tid')
            t = getTournamentByID(tid)
            if not t:
                flash("Invalid tournament ID")
                return redirect('/admin')
        else:
            return redirect('/admin')


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

        t.updateGame(game)

        return redirect( "/admin/update?tid=%s" % tid )

@app.route('/admin/update_config', methods=['POST','GET'])
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

    t.updateConfig(request.form)

    return redirect("/admin/t/%s" % t.short_name)
