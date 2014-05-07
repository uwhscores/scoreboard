import os
import sqlite3
import re
from flask import Flask, request, session, g, redirect, url_for, abort, \
	render_template, flash, jsonify, json, request

app = Flask(__name__)
app.config.from_object(__name__)

app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'scores.db'),
	DEBUG=True,
	SECRET_KEY='testkey',
	USERNAME='admin',
	PASSWORD='default',
	TID='1'
))

app.config.from_envvar('SCOREBOARD_SETTINGS', silent=True)

class Stats(object):
	def __init__(self, name, team_id):
		self.name = name
		self.team_id = team_id
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

def getPoints(stats):
	return stats.points

def sortTeams(team_b, team_a):
	if (team_a.points != team_b.points):
		return team_a.points - team_b.points
	elif ( whoWon(team_a, team_b) != whoWon(team_b, team_a) ):
		return whoWon(team_a, team_b) - whoWon(team_b, team_a)
	elif (team_a.wins != team_b.wins):
		return team_a.wins - team_b.wins
	elif (team_a.losses != team_b.losses):
		return team_b.losses - team_b.losses
	elif (team_a.goals_allowed != team_b.goals_allowed):
		return team_a.gaols_allowed - team_b.goals_allowed
	else:
		return 0

def calcStandings():
	standings = {}

	db = getDB()
	cur = db.execute('SELECT team_id, name FROM teams WHERE tid=?',app.config['TID'])
	team_ids = cur.fetchall()

	for row in team_ids:
		team_id = row['team_id']
		standings[team_id]= Stats(row['name'], row['team_id'])

	cur = db.execute('SELECT black_tid, white_tid, score_b, score_w FROM scores WHERE tid=?', app.config['TID'])
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

def getStandings():
	if not hasattr(g, 'standings'):
		g.standings = calcStandings()
	return g.standings

def getTeam(team_id):
	db = getDB()
	cur = db.execute('SELECT name FROM teams WHERE team_id=? AND tid=?', (team_id, app.config['TID']))
	team = cur.fetchone()

	return team['name']

def endRoundRobin():
	db = getDB()
	cur = db.execute('SELECT rr_games FROM tournaments WHERE tid=?', app.config['TID'])
	row = cur.fetchone()
	rr_games = row['rr_games']

	cur = db.execute('SELECT count(gid) as count FROM scores WHERE gid <= ? AND tid=?', (rr_games, app.config['TID']))
	row = cur.fetchone()
	games_played = row['count']

	if (games_played >= rr_games):
		return 1
	else:
		return 0

def getSeed(seed):
	if ( endRoundRobin() ):
		standings = getStandings()
		seed = int(seed) - 1	
		return standings[seed].team_id
	else:
		return -1

def getWinner(game_id):
	return -1

def getLooser(game_id):
	return -1


def praseGame(g):
	game = g

	match = re.search( '^T(\d+)$', g)
	if match:
		game = getTeam(match.group(1))

	match = re.search( '^S(\d+)$', g )
	if match:
		seed = match.group(1)
		team_id = getSeed( seed )
		if ( team_id < 0 ):
			game = "Seed " + seed
		else:
			team = getTeam(team_id)
			game = team + " (S" + seed + ")"
	
	match = re.search( '^W(\d+)$', g)
	if match:
		gid = match.group(1)
		team_id = getWinner(gid)
		if (team_id < 0):
			game = "Winner of " + gid
		else:
			team = getTeam(team_id)
			game = team + " (W" + gid + ")"

	match = re.search( '^L(\d+)$', g)
	if match:
		gid = match.group(1)
		team_id = getLooser(gid)
		if (team_id < 0):
			game = "Looser of " + gid
		else:
			team = getTeam(team_id)
			game = team + " (L" + gid + ")"

	return game

def expandGames(games):
	expanded = []
	db = getDB()
	
	for info in games:
		game = {}
		game["gid"] = info['gid']
		game["day"] = info['day']
		game["start_time"] = info['start_time']
		game["black"] = praseGame(info['black'])
		game["white"] = praseGame(info['white'])

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
		
def getGames():
	db = getDB()
	cur = db.execute('SELECT gid, day, start_time, black, white FROM games WHERE tid=? ORDER BY gid',app.config['TID'])
	games = expandGames(cur.fetchall())

	return games;

@app.route('/')
def renderMain():

	#cur = db.execute('select name from teams WHERE tid=?', app.config['TID'])
	#teams = cur.fetchall()

	games = getGames()
	teams = getStandings()

	standings = [] 
	for team in teams:
		standings.append(team.__dict__)
	
	return render_template('show_main.html', standings=standings, games=games)

@app.route('/api/getGames')
def apiGetGames():
	games = getGames()

	#return jsonify(games)
	return json.dumps(games)

@app.route('/api/getStandings')
def apiGetStandings():
	teams = getStandings()

	standings = {}
	place = 1
	for team in teams:
		standings[place]=team.__dict__
		place += 1

	return json.dumps(standings)


@app.route('/update', methods=['POST','GET'])
def renderUpdate():

	if request.method == 'POST':
		game = getGame( request.form['gid'] ) 
		return render_update('show_single.html', game=game)
	else:
		games = getGames()
		return render_template('show_update.html', games=games)
	
if __name__ == '__main__':
	app.run(host='0.0.0.0 ')
