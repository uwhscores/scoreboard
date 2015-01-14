import os
import sqlite3
import re
from flask import Flask, request, session, g, redirect, url_for, abort, \
	render_template, flash, jsonify, json
from werkzeug.contrib.fixers import ProxyFix
#from flask.ext.basicauth import BasicAuth
from datetime import datetime

app = Flask(__name__)
app.config.from_object(__name__)

app.config['BASIC_AUTH_USERNAME'] = 'admin'
app.config['BASIC_AUTH_PASSWORD'] = 'dummy'

#basic_auth = BasicAuth(app)

app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'scores.db'),
	DEBUG=True,
	SECRET_KEY='testkey',
	USERNAME='admin',
	PASSWORD='default',
	TID='3'
))

app.config.from_envvar('SCOREBOARD_SETTINGS', silent=True)

# class used for calculating standings, stat object has all the values
# for the things standings are calculator against
class Stats(object):
	def __init__(self, name, team_id, div=None, pod=None):
		self.name = name
		self.team_id = team_id
		self.division = div
		self.pod = pod
		self.points = 0
		self.wins = 0
		self.losses = 0
		self.ties = 0
		self.goals_allowed = 0
		self.games_played = 0

	def __repr__(self):
		return '{}({}): {} {}-{}-{}'.format(self.name,self.team_id, self.points, self.wins, self.losses, self.ties)

	def __cmp__(self, other):
		if hasattr(other, 'points'):
			return other.points.__cmp__(self.points)

# DB logic for setting up database connection and teardown
def connectDB():
	rv = sqlite3.connect(app.config['DATABASE'])
	rv.row_factory = sqlite3.Row
	return rv

def getDB():
	if not hasattr(g, 'sqlite_db'):
		g.sqlite_db = connectDB()
	return g.sqlite_db

@app.teardown_appcontext
def closeDB(error):
	if hasattr(g, 'sqlite_db'):
		g.sqlite_db.close()

# simple function for calculating the win/loss ration between two teams
# returns number of wins team_a has over team_b, negative number if more losses
def whoWon(team_a, team_b):
	db = getDB()
	net_wins = 0

	tid_a = team_a.team_id
	tid_b = team_b.team_id

	cur = db.execute('SELECT black_tid, white_tid, score_w, score_b FROM scores \
				WHERE ((black_tid=? AND white_tid=?) OR (black_tid=? AND white_tid=?)) AND tid=?', \
				(tid_a, tid_b, tid_b, tid_a, app.config['TID']) )

	games = cur.fetchall()

	for game in games:
		black_tid = game['black_tid']
		white_tid = game['white_tid']
		score_b = game['score_b']
		score_w = game['score_w']

		if ( score_b > score_w):
			if ( black_tid == tid_a):
				net_wins += 1
			elif ( black_tid == tid_b):
				net_wins -= 1
		elif ( score_w > score_b):
			if ( white_tid == tid_a):
				net_wins += 1
			elif ( white_tid == tid_b):
				net_wins -= 1
			
	
	return net_wins

# dumb function, think its left over, clean it out
def getPoints(stats):
	return stats.points

# quick funciton used to convert divisions to an integer used in rankings
# makes an A team above a B team 
def divToInt(div):
	if (div.lower() == 'a'):
		return 3
	elif (div.lower() == 'b'):
		return 2
	elif (div.lower() == 'c'):
		return 1
	else:
		return 0

def podToInt(pod):
	sortOrder = "b,g,d,e,z,B,G,O,Y"
	sortOder = "Y,O,G,B,z,e,d,g,b,A"
	return sortOder.index(pod)

# function used for sorting Stats class for standings
# Sorts on most points, head to head, most wins, least losses, goals allowed
# Returns for coin toss in all tied <- not done
def sortTeams(team_b, team_a):
	if (team_a.division.lower() != team_b.division.lower()):
		return divToInt(team_a.division) - divToInt(team_b.division)
	elif (team_a.pod != team_b.pod):
		return podToInt(team_a.pod) - podToInt(team_b.pod)
	elif (team_a.points != team_b.points):
		return team_a.points - team_b.points
	elif ( whoWon(team_a, team_b) != whoWon(team_b, team_a) ):
		return whoWon(team_a, team_b) - whoWon(team_b, team_a)
	elif (team_a.wins != team_b.wins):
		return team_a.wins - team_b.wins
	elif (team_a.losses != team_b.losses):
		return team_b.losses - team_a.losses
	elif (team_a.goals_allowed != team_b.goals_allowed):
		return team_b.goals_allowed - team_a.goals_allowed
	else:
		addTie(team_a.team_id, team_b.team_id)
		return 0

# creates flash for tie only if the round robin for the division is finished
def addTie(tid_a, tid_b):
	db = getDB()
	#cur = db.execute('SELECT pod FROM pods WHERE team_id=? AND TID=? LIMIT 1',(tid_a,app.config['TID']))
	#row = cur.fetchone()
	#division = row['division']
	#pod = row['pod']
	
	#a = getTeam(tid_a)
	#b = getTeam(tid_b)

	#if endRoundRobin(None, pod):
		#flash("We have a real tie " + a + " & " + b)
	return 0


# master function for calculating standings of all teams
# shouldn't be called directly, use getStandings() to avoid
# recalculating multiple times per load
def calcStandings(pod=None):
	standings = {}

	db = getDB()
	if (pod == None):
		cur = db.execute('SELECT team_id FROM teams WHERE tid=?',app.config['TID'])
	else:
		cur = db.execute('SELECT team_id FROM pods WHERE tid=? AND pod=?',(app.config['TID'], pod)) 
				
		
	team_ids = cur.fetchall()

	for team in team_ids:
		team_id = team['team_id']
		cur = db.execute('SELECT name, division FROM teams WHERE team_id=? AND tid=?',(team_id, app.config['TID']))
		row = cur.fetchone()
		standings[team_id]= Stats(row['name'], team_id, row['division'], pod)

	if (pod == None):
		cur = db.execute('SELECT s.black_tid, s.white_tid, s.score_b, s.score_w FROM scores s, games g \
							WHERE g.gid=s.gid AND g.tid=s.tid AND g.type="RR" AND s.tid=?', (app.config['TID']))
	else:
		cur = db.execute('SELECT s.black_tid, s.white_tid, s.score_b, s.score_w FROM scores s, games g \
							WHERE g.gid=s.gid AND g.tid=s.tid AND g.pod=?  AND g.type="RR" AND s.tid=?', (pod,app.config['TID']))
	games = cur.fetchall()

	for game in games:
		black_tid = game['black_tid']
		white_tid = game['white_tid']
		score_b = game['score_b']
		score_w = game['score_w']
	
		standings[black_tid].games_played += 1
		standings[white_tid].games_played += 1

		if (score_b >= 0 & score_w >= 0 ): 
			standings[black_tid].goals_allowed += score_w
			standings[white_tid].goals_allowed += score_b

		if (score_b == -1): #black forfit
			standings[black_tid].points -= 2
			standings[black_tid].losses += 1

			standings[white_tid].wins += 1
			standings[white_tid].points += 2

		elif (score_w == -1): #white forfit
			standings[white_tid].points -= 2
			standings[white_tid].losses += 1
	
			standings[black_tid].wins += 1
			standings[black_tid].points += 2
	
		elif ( score_b > score_w ):
			standings[black_tid].wins += 1
			standings[white_tid].losses += 1

			standings[black_tid].points += 2
				
		elif (score_w > score_b): 
			standings[white_tid].wins +=1 
			standings[black_tid].losses += 1 
	
			standings[white_tid].points += 2

		elif (score_w == score_b):
			standings[black_tid].ties += 1;
			standings[white_tid].ties += 1;
		
			standings[black_tid].points += 1;
			standings[white_tid].points += 1;


	return sorted(standings.values(), cmp=sortTeams)

# wrapper function for standings, use to ger dictionary of standings
# dictionary indexed by rank and contains all the team information in Stat class
def getStandings(div=None, pod=None):
	#if not hasattr(g, 'standings'):
	#	g.standings = calcStandings(division)
	#return g.standings

	db = getDB()
	standings = []

	if ( pod == None and div == None ):
		cur = db.execute('SELECT DISTINCT pod FROM pods WHERE tid=?', app.config['TID'])
		rows = cur.fetchall()		
		if (len(rows) > 0):
			for row in rows:
				pod = row['pod']
				standings = standings + calcStandings(pod)
		else:
			standings = calcStandings()
			
	elif (pod == None):
		cur = db.execute('SELECT DISTINCT p.pod FROM pods p, teams t WHERE p.team_id=t.team_id AND t.division=? AND p.tid=?',\
			(div, app.config['TID']))

		rows = cur.fetchall()
		for row in rows:
			standings = standings + calcStandings(row['pod'])

	else:	
		standings= calcStandings(pod)


	return standings

# simple function for converting team ID index to real name
def getTeam(team_id):
	db = getDB()
	cur = db.execute('SELECT name FROM teams WHERE team_id=? AND tid=?', (team_id, app.config['TID']))
	team = cur.fetchone()

	return team['name']

# true false function for determining if round robin play has been completed
def endRoundRobin(division=None, pod=None):
	db = getDB()
	if (division == None and pod  == None):
		cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND tid=?', app.config['TID'])
	elif (division == None):
		cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND pod=? AND tid=?',(pod, app.config['TID']))
	else:
		cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND division LIKE ? AND tid=?', \
			(division, app.config['TID']))
	row = cur.fetchone()

	rr_games = row['games']

	if (division == None and pod == None):
		cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.tid=s.tid AND s.tid=?', \
			app.config['TID'])
	elif (division == None):
		cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.pod=? AND g.tid=s.tid AND g.tid=?', \
			(pod, app.config['TID']))	
	else:
		cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.tid=s.tid AND g.division=? AND s.tid=?',\
			(division, app.config['TID']))
	
	row = cur.fetchone()
	games_played = row['count']

	app.logger.debug("division |%s| and pod |%s|" % (division, pod))
	app.logger.debug("RR Games = %s and we've played %s games" % (rr_games, games_played))

	if (games_played >= rr_games):
		return 1
	else:
		return 0

# gets team ID back from seed ranking, returns -1 if seeding isn't final
def getSeed(seed, division=None, pod=None):
	if ( endRoundRobin(division, pod) ):
		standings = getStandings(division, pod)
		seed = int(seed) - 1	
		return standings[seed].team_id
	else:
		return -1

def getPodID(pod, pod_id):
	db = getDB()
	cur = db.execute("SELECT team_id FROM pods WHERE pod=? AND pod_id=? AND tid=? LIMIT 1",(pod, pod_id, app.config['TID']))

	row = cur.fetchone()
	if (row):
		return row['team_id']
	else:
		return -1


def getPlacings(div=None):
	db = getDB()
	if (div):
		cur = db.execute("SELECT place, game FROM rankings WHERE division=? AND tid=?", (div,app.config['TID']))
	else:
		cur = db.execute("SELECT place, game FROM rankings WHERE tid=?", app.config['TID'])

	rankings = cur.fetchall()

	final = [] 
	for rank in rankings:
		entry = {}
		style=""
		place = rank['place']
		game = rank['game']	

		#Seeded Pod notation
		match = re.search( '^S([\w])(\d+)$', game)
		if match:
			pod = match.group(1)
			seed = match.group(2)
			team_id = getSeed( seed, None, pod)

			if ( team_id < 0 ):	
				game = "Pod " + pod + " seed " + seed
				style="soft"
			else:
				name = getTeam(team_id)
				game = name 

		# Winner of	
		match = re.search( '^W(\d+)$', game)
		if match:
			gid = match.group(1)
			team_id = getWinner(gid)
			if (team_id == -1):
				game = "Winner of " + gid
				style="soft"
			elif (team_id == -2):
				game = "TIE IN BRACKET!!"
			else:
				team = getTeam(team_id)
				game = team

		# Loser of
		match = re.search( '^L(\d+)$', game)
		if match:
			gid = match.group(1)
			team_id = getLoser(gid)
			if (team_id == -1):
				game = "Loser of " + gid
				style="soft"
			elif (team_id == -2):
				game = "TIE IN BRACKET!!"
			else:
				team = getTeam(team_id)
				game = team

		entry['place']= place
		entry['name'] = game	
		entry['style'] = style

		final.append(entry)

	return final

# returns winner team ID of game by ID
def getWinner(game_id):
	db = getDB()
	cur = db.execute("SELECT black_tid, white_tid, score_b, score_w FROM scores WHERE gid=? AND tid=?", (game_id,app.config['TID']))
	game = cur.fetchone()
	if game:
		if (game['score_b'] > game['score_w']):
			return game['black_tid']
		elif ( game['score_b'] < game['score_w']):
			return game['white_tid']
		else:
			return -2
	else:
		return -1 

# returns loser team ID of game by ID
def getLoser(game_id):
	db = getDB()
	cur = db.execute("SELECT black_tid, white_tid, score_b, score_w FROM scores WHERE gid=? AND tid=?", (game_id,app.config['TID']))
	game = cur.fetchone()
	if game:
		if (game['score_b'] < game['score_w']):
			return game['black_tid']
		elif ( game['score_b'] > game['score_w']):
			return game['white_tid']
		else:
			return -2
	else:
		return -1 
	
# Converts short hand notation for game schedule into human readable names
# Team IDs, seeding games and "winner/loser of" games
def parseGame(game):
	style = ""
	team_id = -1
	
	# Team notation
	match = re.search( '^T(\d+)$', game)
	if match:
		team_id = match.group(1)
		game = getTeam(team_id)

	# seeded pods RR games
	match = re.search('^([begdz])(\d+)$', game)
	if match:
		pod = match.group(1)
		pod_id = match.group(2)
		team_id = getPodID(pod, pod_id)		

		if ( team_id < 0):
			game = "Pod " + pod + " team " + pod_id
			style="soft"
		else:
			name = getTeam(team_id)
			game = name + " ("+pod+pod_id+")"
 
	# Seed notation
	match = re.search( '^S([A|B|C])?(\d+)$', game )
	if match:
		division = match.group(1)
		seed = match.group(2)
		team_id = getSeed( seed, None, division )
		if ( team_id < 0 ):
			if division:
				game = "Seed " + division + seed
			else:
				game = "Seed " + seed
			style="soft"
		else:
			team = getTeam(team_id)
			if division:
				game = "%s (S%s%s)" % (team, division, seed)
			else:
				game = "%s (S%s)" % (team, seed)

	#Seeded Pod notation
	match = re.search( '^S([begdz])(\d+)$', game)
	if match:
		pod = match.group(1)
		seed = match.group(2)
		team_id = getSeed( seed, None, pod)

		if ( team_id < 0 ):	
			game = "Pod " + pod + " seed " + seed
			style="soft"
		else:
			name = getTeam(team_id)
			game = name + " ("+pod+"-S"+seed+")"

	# Winner of	
	match = re.search( '^W(\d+)$', game)
	if match:
		gid = match.group(1)
		team_id = getWinner(gid)
		if (team_id == -1):
			game = "Winner of " + gid
			style="soft"
		elif (team_id == -2):
			game = "TIE IN BRACKET!!"
		else:
			team = getTeam(team_id)
			game = team + " (W" + gid + ")"

	# Loser of
	match = re.search( '^L(\d+)$', game)
	if match:
		gid = match.group(1)
		team_id = getLoser(gid)
		if (team_id == -1):
			game = "Loser of " + gid
			style="soft"
		elif (team_id == -2):
			game = "TIE IN BRACKET!!"
		else:
			team = getTeam(team_id)
			game = team + " (L" + gid + ")"

	team_id = int(team_id)
	return (team_id,game,style)

# loops through all games and creates expanded dictionary of games
# expands database short hand into human readable form
def expandGames(games):
	expanded = []
	db = getDB()

	podColors = {'A':'#BDBDBD','B':'#2E2EFE','G':'#04B404','O':'#FF8000','Y':'#FFFF00',\
			'b':'#81F7F3','g':'#81F781','d':'#FF0000','e':'#F5D0A9','z':'#948A54',\
			'D':'#FF00FF'
		}
	
	for info in games:
		game = {}
		game["gid"] = info['gid']
		game["day"] = info['day']
		start_time = info['start_time']
		game["start_time"] = datetime.strptime(start_time, '%H:%M').strftime('%I:%M %p')
		game["pool"] = info['pool']
		if hasattr(info,'pod'):
			game["pod"] = info['pod']
			game["pod_color"] = podColors[info['pod']]
			b

		(game["black_tid"],game["black"],game["style_b"]) = parseGame(info['black'])
		(game["white_tid"],game["white"],game["style_w"]) = parseGame(info['white'])

		pod = getGamePod(game["gid"])
		game["pod"] = pod
		if pod in podColors:
			game["pod_color"] = podColors[pod]
		else:
			game["pod_color"] = None
		

		cur = db.execute('SELECT score_b, score_w FROM scores WHERE gid=? AND tid=?', (game['gid'],app.config['TID']))
		score = cur.fetchone()

		if score:
			game['score_b'] = score['score_b']		
			game['score_w'] = score['score_w']
		else:
			game['score_b'] = "--"
			game['score_w'] = "--"
		
		expanded.append(game)

	return expanded 
	
# gets full list of games for display	
# returns list of dictionaries for each game
def getGames(division= None, pod=None, offset=None ):
	db = getDB()
	if (offset != None):
		cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
						WHERE tid=? ORDER BY day, start_time LIMIT ?,45",\
						(app.config['TID'], offset))
	elif (division == None and pod == None):
		cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
							WHERE tid=? ORDER BY day, start_time",app.config['TID'])
	elif (pod == None):
		cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
							WHERE division LIKE ? AND tid=? ORDER BY day, start_time", \
							(division, app.config['TID']))
	elif (division == None):
		cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
							WHERE POD like ? AND tid=? ORDER BY day, start_time",\
			 				(pod, app.config['TID']))
	
	#if (division == None and pod==None and offset):
	#	cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
	#					WHERE tid=? ORDER BY day, start_time LIMIT ?,40",\
	#					(app.config['TID'], offset))
	#else:
	#	cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
	#					WHERE tid=? ORDER BY day, start_time",\
	#					(app.config['TID']))	
		
	games = expandGames(cur.fetchall())

	return games;

# gets single game by ID, returns single dictionary
def getGame(gid):
	db = getDB()
	cur = db.execute('SELECT gid, day, strftime("%H:%M", start_time) as start_time, pool, black, white, pod FROM games WHERE gid=? AND tid=? ',(gid, app.config['TID']))
	game = expandGames(cur.fetchall())

	return game[0];

def getTeamGames(team_id):
	db = getDB()

	cur = db.execute('SELECT gid, day, strftime("%H:%M", start_time) as start_time, pool, black, white FROM games WHERE tid=? ORDER BY day, start_time',(app.config['TID']))
	allGames = expandGames(cur.fetchall())

	games = []
	for game in allGames: 
		if game['black_tid'] == team_id or game['white_tid'] == team_id: 
		#if (game['black_tid'] == team_id or game['white_tid'] == team_id) or (game['black_tid'] < 0 or game['white_tid'] < 0):
			if game['black_tid'] == team_id:
				game['style_b'] = "strong"
			elif game['white_tid'] == team_id:
				game['style_w'] = "strong"
			games.append(game)
							
	return games;

# get list of pods that have teams assigned to them
def getPodsActive(div=None):
	db = getDB()
	if (div):	
		cur = db.execute('SELECT DISTINCT p.pod FROM pods p, teams t WHERE p.team_id=t.team_id\
			 AND t.division=? and p.tid=?',(div,app.config['TID']))
	else:
		cur = db.execute('SELECT DISTINCT p.pod FROM pods p WHERE p.tid=?',(app.config['TID']))
	pods = ()
	return( cur.fetchall())

def getPodsInPlay(div=None):
	pods = getPodsActive(div)
	inPlay = []
	for pod in pods:
		if not endRoundRobin(None, pod['pod']):
			inPlay.append(pod)

	return inPlay

# return division as string from team_id
def getDivision(team_id):
	db = getDB()
	cur = db.execute('SELECT division FROM teams WHERE team_id=? AND tid=?', (team_id, app.config['TID']))
	row = cur.fetchone()

	return row['division']

def getTeamPod(team_id):
	db = getDB()
	cur = db.execute('SELECT pod from pods WHERE team_id=? AND tid=?', (team_id, app.config['TID']))
	row = cur.fetchall()

	if len(row) > 0:
		return row
	else:
		return None

def getGamePod(gid):
	db = getDB()
	cur = db.execute('SELECT pod from games WHERE gid=? AND tid=?', (gid, app.config['TID']))
	row = cur.fetchone()

	return row['pod']


# takes in form dictionary from POST and updates/creates score for single game
def updateGame(form):
	db = getDB()
	gid = form['gid']
	score_b = form['score_b']
	score_w = form['score_w']
	black_tid = form['btid']
	white_tid = form['wtid']
	pod = form['pod']
	
        cur = db.execute("INSERT OR IGNORE INTO scores (black_tid, white_tid, score_b, score_w,tid, gid, pod) VALUES(?,?,?,?,?,?,?)", \
			(black_tid,white_tid,score_w,score_b,app.config['TID'],gid, pod))
        db.commit()
	cur = db.execute("UPDATE scores SET score_b=?,score_w=? WHERE tid=? AND gid=?", (score_b,score_w,app.config['TID'],gid))
	db.commit()

	return 1

# total hack for Nationals seeded pod. Not dynamic at all but its what had to happen
def popSeededPods():
	db = getDB()

	seededPods = ['b','g','d','e','z']
	pod_id = 1

	# green, blue, orange, yellow
	for pod in ("G","B","O","Y"):
		podStandings = getStandings(None,pod)

		pod_offset=0
		for team in podStandings:
			team_id = team.team_id
			pod = seededPods[pod_offset]
			cur = db.execute("INSERT INTO pods (tid, team_id, pod, pod_id) VALUES (?,?,?,?)",(app.config['TID'], team_id, pod, pod_id))
			db.commit()
			pod_offset +=1

		pod_id +=1

	return 1

	
def getTournamentName():
	db = getDB()
	cur = db.execute("SELECT name FROM tournaments WHERE tid=?", app.config['TID'])
	row = cur.fetchone()

	return row['name']

@app.route('/')
def renderMain():

	games = getGames()
	teams = getStandings()
	pods = getPodsActive()
	placings = getPlacings()
	
	titleText="Full "	
	standings = [] 
	for team in teams:
		standings.append(team.__dict__)

		
	return render_template('show_main.html', tournament=getTournamentName(), standings=standings, games=games, pods=pods, titleText=titleText, placings=placings)

@app.route('/div/<division>')
def renderDivision(division):
	games = getGames(division)
	teams = getStandings(division)
	pods = getPodsActive()

	standings = []
	for team in teams:
		standings.append(team.__dict__)

	titleText = division.upper() + " Division"

	#return render_template('show_individual.html', tournament=getTournamentName(), standings=standings, games=games, titleText=titleText)
	return render_template('show_main.html', tournament=getTournamentName(), standings=standings, games=games, titleText=titleText, pods=pods)

@app.route('/pod/<pod>')
def renderPod(pod):
	games = getGames(None,pod)
	teams = getStandings(None, pod)
	pods = getPodsActive()

	standings = []
	for team in teams:
		standings.append(team.__dict__)

	titleText = pod.upper() + " Pod"
	return render_template('show_main.html', tournament=getTournamentName(), standings=standings, games=games, titleText=titleText, pods=pods)


@app.route('/team/<team_id>')
def renderTeam(team_id):
	team_id = int(team_id)
	division = getDivision(team_id)
	#pods = getPodsActive(division)

	teams = []
	games = getTeamGames(team_id)
	

	pods = getTeamPod(team_id)
	if pods:
		for pod in pods:
			teams.append(getStandings(None, pod['pod']))
	else:
		teams.append(getStandings())
	
	standings = []
	for div in teams:
		for team in div:
			standings.append(team.__dict__)

	titleText = getTeam(team_id)
	#noteText="Only showing confirmed games. Subsequent games will be added as determined by seeding. Check back."
	noteText = "WARNING: The schedule above will be incomplete until all games are seeded (ie. bracket games, \
	games determined by win/loss, etc. for the finals). Check schedule throughout tournament for updates."
	return render_template('show_main.html', tournament=getTournamentName(), standings=standings, games=games, titleText=titleText, pods=pods, noteText=noteText)


@app.route('/tv')
@app.route('/tv/<offset>')
def renderTV(offset=None):
	#if (division == "A"):
	#	games = getGames(division)
	#	teams = getStandings(division)
	#	placings = getPlacings(division)
	#else:
	
	division=None
	
	games = getGames(division,None,offset)
	#pods = getPodsInPlay(division)
	placings = getPlacings(division)

	teams = []		
	teams = getStandings()
	
	titleText="Full "	
	standings = [] 
	for team in teams:
		standings.append(team.__dict__)

	return render_template('show_tv.html', tournament=getTournamentName(), standings=standings, games=games, titleText=titleText, request=request, placings=placings)

@app.route('/whiterabbitobject')
#@basic_auth.required
def callToSeed():
	output = popSeededPods()
	return json.dumps(output)

@app.route('/api/getGames')
@app.route('/api/getGames/<division>')
def apiGetGames(division=None):
	if (division == None):
		games = getGames()
	else:
		games = getGames(division)

	#return jsonify(games)
	return json.dumps(games)

@app.route('/api/getStandings')
@app.route('/api/getStandings/<division>')
def apiGetStandings(division=None):
	if (division == None):
		teams = getStandings()
	else:
		teams = getStandings(division)

	standings = {}
	place = 1
	for team in teams:
		standings[place]=team.__dict__
		place += 1

	return json.dumps(standings)


@app.route('/update', methods=['POST','GET'])
#@basic_auth.required
def renderUpdate():
	if request.method =='GET':
		if request.args.get('gid'):
			game = getGame( request.args.get('gid') ) 
			if ( game['score_b'] == "--"):
				game['score_b'] = ""
			if ( game['score_w'] == "--"):
				game['score_w'] = ""

			if ( game['black_tid'] < 0 or game['white_tid'] < 0):
				flash('Team(s) not determined yet. Cannot set score')
				return redirect(request.base_url)
			return render_template('update_single.html', game=game)
		else:
			games = getGames()
			return render_template('show_update.html', games=games, tournament=getTournamentName())
	if request.method == 'POST':
		updateGame(request.form)
		return redirect(request.base_url)

app.wsgi_app = ProxyFix(app.wsgi_app)
	
if __name__ == '__main__':
	app.run(host='0.0.0.0 ')
