import os
import sqlite3
import re
from flask import Flask, request, session, g, redirect, url_for, abort, \
	render_template, flash, jsonify, json
from werkzeug.contrib.fixers import ProxyFix
#from flask.ext.basicauth import BasicAuth
from datetime import datetime
from string import split
from collections import OrderedDict

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
	TID='8'
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
		self.wins_t = 0
		self.losses_t = 0
		self.ties_t = 0

	def __repr__(self):
		return '{}({}): {} {}-{}-{}'.format(self.name,self.team_id, self.points, self.wins, self.losses, self.ties)

	def __cmp__(self, other):
		if hasattr(other, 'points'):
			return other.points.__cmp__(self.points)
	def __eq__(self, other):
		if cmpTeamPoints(self, other) == 0:
			return True
		else:
			return False

class Ranking(object):
	def __init__(self, div, pod, place, team):
		self.div = div
		self.pod = pod
		self.place = place
		self.team = team

	def __repr__(self):
		return '{}-{}-{}: {}'.format(self.div, self.pod, self.place, self.team.name)

	def __eq__(self, other):
		if cmpTeamsSort(self.team, other.team) == 0:
			return True
		else:
			return False

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

# loads in all the rows from the config table for the tournament ID
# config table is used to store parameters for various logic in the code
def loadParams():
	db = getDB()
	params = {}

	cur = db.execute('SELECT field, val FROM params where tid=?', app.config['TID'])

	rows = cur.fetchall()

	for config in rows:
		params[config['field']] = config['val']

	return params

def getParams():
	if not hasattr(g, 'params'):
		g.params = loadParams()
	return g.params

def getParam(param):
	params = getParams()

	if param in params:
		return params[param]
	else:
		return None

# add new value to params list
def addParam(field, val):
	db = getDB()

	cur = db.execute('INSERT INTO params VALUES (?,?,?)', (app.config['TID'], field, val))
	db.commit()

	g.params = loadParams()
	return 0

def updateParam(field, val):
	db = getDB()

	cur = db.execute('UPDATE params SET val=? WHERE field=? and tid=?', (val, field, app.config['TID']))
	db.commit()

	g.params = loadParams()
	return 0

def clearParam(field):
	db = getDB()

	cur = db.execute("DELETE FROM params where field=? AND tid=?", (field, app.config['TID']))
	db.commit()

	g.params = loadParams()
	return 0


# simple function for calculating the win/loss ration between two teams
# returns number of wins team_a has over team_b, negative number if more losses
def whoWon(team_a, team_b):
	db = getDB()
	net_wins = 0

	tid_a = team_a.team_id
	tid_b = team_b.team_id


	if team_a.pod != team_b.pod:
		app.logger.debug("Comparing two teams that aren't in the same pod, that's ok")

	pod = team_a.pod

	if pod:
		cur = db.execute('SELECT s.black_tid, s.white_tid, s.score_w, s.score_b FROM scores s, games g \
						WHERE s.gid = g.gid AND s.tid=g.tid AND ((s.black_tid=? AND s.white_tid=?)\
						OR (s.black_tid=? AND s.white_tid=?)) AND g.type="RR" AND g.pod=? AND g.tid=?', \
						(tid_a, tid_b, tid_b, tid_a, pod, app.config['TID']) )
	else:
		cur = db.execute('SELECT s.black_tid, s.white_tid, s.score_w, s.score_b FROM scores s, games g \
						WHERE s.gid = g.gid AND s.tid=g.tid AND ((s.black_tid=? AND s.white_tid=?)\
						OR (s.black_tid=? AND s.white_tid=?)) AND g.type="RR" AND g.tid=?', \
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
	elif (div.lower() == 'e'):
		return 2
	elif (div.lower() == 'o'):
		return 1
	else:
		return 0

def podToInt(pod):
	#sortOrder = "b,g,d,e,z,B,G,O,Y"
	#sortOrder = "Y,O,G,B,z,e,d,g,b,A"
	#sortOrder = "w,x,y,z,A,B,C,D"
	sortOrder = "A,B,C,1P,2P,3P,4P,5P,6P,7P"
	if pod in SortOrder:
		return sortOrder.index(pod)
	else:
		return 0

# function used for sorting Stats class for standings
# Compares on most points, head to head, most wins, least losses, goals allowed
#
# ONLY USE WHEN COMPARING TEAMS DIRECTLY, DON'T USE IN SORT
#
def cmpTeams(team_b, team_a, pod=None):
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
		flip = getCoinFlip(team_a.team_id, team_b.team_id)
		if flip == team_a.team_id:
			return 1
		if flip == team_b.team_id:
			return -1
		else:
			addTie(team_a.team_id, team_b.team_id)
			return 0

## Compares teams w/o head-to-head, needed for sorting sets of three or more teams
def cmpTeamsSort(team_b, team_a):
	if (team_a.division.lower() != team_b.division.lower()):
		return divToInt(team_a.division) - divToInt(team_b.division)
	elif (team_a.wins != team_b.wins):
		return team_a.wins - team_b.wins
	elif (team_a.losses != team_b.losses):
		return team_b.losses - team_a.losses
	elif (team_a.goals_allowed != team_b.goals_allowed):
		return team_b.goals_allowed - team_a.goals_allowed
	else:
		return 0

## Compares teams only on points, checks division and pod first to make sure they aren't
## in the same division, used for pre-sorting rank before applying tie breakers
## used by __cmp__ function for Stats struct
def cmpTeamPoints(team_b, team_a):
	if (team_a.division.lower() != team_b.division.lower()):
		return divToInt(team_a.division) - divToInt(team_b.division)
	elif (team_a.pod != team_b.pod):
		return podToInt(team_a.pod) - podToInt(team_b.pod)
	elif (team_a.points != team_b.points):
		return team_a.points - team_b.points
	else:
		return 0

def cmpRankSort(rank_b, rank_a):
	return cmpTeamsSort(rank_b.team, rank_a.team)

# Sorts a list of Stats objects, one per team.
# Returns ordered list of Ranging objects, ranking object has team stat objects
# along with the division, pod and place
# Wherever place is displayed/used it would reference the place field, don't use the index for place
def sortStandings(team_stats, pod=None):
	#if not pod:
	#	app.logger.debug("sorting standings without pod")
	#else:
	#	app.logger.debug("sorting for pod %s" % pod)

	for team in team_stats.values():
		#team = team_stats[place]
		if team.pod != pod:
			app.logger.debug("I have standings that aren't for my pod")

	# pre-sort required for three-way ties
	ordered = sorted(team_stats.values(), cmp=cmpTeamsSort)
	ordered = sorted(ordered, cmp=cmpTeams)

	# first go through the list and assign a place to everybody based on only points
	# doesn't settle tie breakers yet
	i = 1
	standings= []
	lastDiv = None
	lastPod = None
	last = None
	skipped = 0
	for team in ordered:
		# reset rank number of its a new division or pod
		if team.division != lastDiv or team.pod != lastPod:
			i = 1
			skipped = 0
		elif team != last and skipped > 0:
			i = i + skipped + 1
			skipped = 0
		elif team != last:
			i += 1
		else:
			skipped += 1

		rank = i
		standings.append(Ranking(team.division, team.pod, rank, team))

		lastDiv = team.division
		lastPod = team.pod
		last = team

	divisions = getDivisions()
	pods = getPodsActive()
	is_pods = False
	if pods:
		divisions = pods
		is_pods = True

	# use list Comprehensions to find all the tied teams, have to iterate over divisions
	# to keep 1st in the A from being confused with 1st in the B
	for div in divisions:
		if is_pods:
			#app.logger.debug("working on pod %s" % div)
			div_standings = [x for x in standings if x.team.pod == div]
		else:
			div_standings = [x for x in standings if x.team.division == div]

		places = len(div_standings)
		place = 1
		while place <= places:
			place_teams = [x for x in div_standings if x.place == place]
			count = len(place_teams)
			#app.logger.debug("place_teams =  %s" % place_teams)
			if count == 0: # nobody is in this place, probably do to ties, move on
				place += 1
			elif count == 1: # one team alone, nothing to do
				place += 1
			elif count == 2: # head to head tie, break based on head-to-head first
				place += 1
				a = place_teams[0].team
				b = place_teams[1].team
				if cmpTeams(a, b) < 0:
					place_teams[1].place += 1
				elif cmpTeams(a, b) > 0:
					place_teams[0].place += 1
				else:
 					#flip = getCoinFlip(a.team_id, b.team_id)
 					#if flip == a.team_id:
 					#	place_teams[1] += 1
 					#if flip == b.team_id:
 					#	place_Teams[0] += 1
					continue

			elif count == 3:
				#app.logger.debug("working a three-way in %s" % div)

				# unlikely, but if one team beat both others, then win
				if whoWon(place_teams[0].team, place_teams[1].team) > 0 and whoWon(place_teams[0].team, place_teams[2].team) > 0:
					place_teams[1].place += 1
					place_teams[2].place += 1
					continue
				elif whoWon(place_teams[1].team, place_teams[0].team) > 0 and whoWon(place_teams[1].team, place_teams[2].team) > 0:
					place_teams[0].place += 1
					place_teams[2].place += 1
					continue
				elif whoWon(place_teams[2].team, place_teams[0].team) > 0 and whoWon(place_teams[2].team, place_teams[1].team) > 0:
					place_teams[0].place += 1
					place_teams[1].place += 1
					continue

				# Check if all the tie breakers are ties
				if place_teams[1:] == place_teams[:-1]:
					app.logger.debug("three way tie all equal in %s" % div)
					place += 1
					#continue
				else:
					place_teams = sorted(place_teams, cmp=cmpRankSort) #sort teams based on rules w/o head-to-head

					last = place_teams[-1].team
					second_last = place_teams[-2].team
					# don't use head-to-head cmp even though its two because its the 3-way tie braker
					result = cmpTeamsSort(last, second_last)

					if result == 0:
						place_teams[-1].place += 1
						place_teams[-2].place += 1
					elif result < 0:
						place_teams[-2].place += 2
					else:
						place_teams[-1].place += 2
			else:
				app.logger.debug("Greater than three way tie, go home")
				place += 1


	# resort to make sure in order by place and division
	tmp=sorted(standings, key=lambda x: x.place)
	return sorted(tmp, key=lambda x: x.div)

# creates flash for tie only if the round robin for the division is finished
def addTie(tid_a, tid_b):
# 	db = getDB()
# 	cur = db.execute('SELECT pod FROM pods WHERE team_id=? AND TID=? LIMIT 1',(tid_a,app.config['TID']))
# 	row = cur.fetchone()
# 	division = row['division']
# 	pod = row['pod']

	div_a = getDivision(tid_a)
	div_b = getDivision(tid_b)

	# not quite sure how this would happen, but protecting myself
	if div_a != div_b:
		return 0

	db = getDB()
	#cur = db.execute("SELECT DISTINCT g.pod FROM games g, scores s WHERE g.gid=s.gid AND \
	#	((s.white_tid=? AND s.black_tid=?) OR (s.white_tid=? AND s.black_tid=?)) AND g.type='RR' \
	#	AND g.tid=s.tid AND g.tid=?", (tid_a, tid_b, tid_b, tid_a, app.config['TID']))

	cur = db.execute("SELECT DISTINCT p.pod FROM pods p WHERE (team_id=? OR team_id=?) AND tid=?", (tid_a, tid_b, app.config['TID']))
	rows = cur.fetchall()

	if len(rows) > 0:
		for row in rows:
			pod = row['pod']
			if not endRoundRobin(None, pod):
				return 1
	else:
		pod = None
		if not endRoundRobin(div_a, None):
			return 1
		# code to add divisional check goes here

	#flash("There is a tie in the standings between %s & %s!" %  (teams[0], teams[1]))

	if tid_a < tid_b:
		if not hasattr(g, 'ties'):
			g.ties = []
			g.ties.append((tid_a, tid_b))
		else:
			g.ties.append((tid_a, tid_b))
	else:
		if not hasattr(g, 'ties'):
			g.ties = []
			g.ties.append((tid_b, tid_a))
		else:
			g.ties.append((tid_b, tid_a))

	return 0

# gets the winning team id for a coin flip, returns -1 if no coin flip yet entered
def getCoinFlip(tid_a, tid_b):
	params = getParams()
	#app.logger.debug("looking for a coin flip between %s and %s " % (tid_a, tid_b))

	if 'coin_flips' in params:
		flips = split(params['coin_flips'],";")
		for i in flips:
			(a,b,coin) = split(i,",")
			a = int(a)
			b = int(b)
			if (tid_a == a or tid_a == b) and (tid_b == a or tid_b == b):
				#app.logger.debug("returning a coin %s" % coin)
				return int(coin)
		else:
			return -1

# fuction to add winner of a coin flip
def addCoinFlip(tid_a, tid_b, winner):
	db = getDB()
	val = "%s,%s,%s" % (tid_a, tid_b, winner)

	params = getParams()

	if 'coin_flips' in params:
		val = "%s;%s" %(params['coin_flips'], val)
		updateParam("coin_flips", val)
	else:
		addParam("coin_flips", val)

	popSeededPods()

	return 0

# master function for calculating standings of all teams
# shouldn't be called directly, use getStandings() to avoid
# recalculating multiple times per load
def calcStandings(pod=None):
	#app.logger.debug("calculating standings, pod = %s" , (pod,))

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

	cur = db.execute('SELECT s.black_tid, s.white_tid, s.score_b, s.score_w, s.forfeit, g.type, g.pod  FROM scores s, games g \
							WHERE g.gid=s.gid AND g.tid=s.tid  AND s.tid=?', (app.config['TID']))

	games = cur.fetchall()

	for game in games:


		black_tid = game['black_tid']
		white_tid = game['white_tid']
		score_b = game['score_b']
		score_w = game['score_w']
		forfeit = game['forfeit']


		if forfeit == "b":
			if black_tid in standings: standings[black_tid].losses_t += 1
			if white_tid in standings: standings[white_tid].wins_t += 1
		elif forfeit == "w":
			if black_tid in standings: standings[black_tid].wins_t += 1
			if white_tid in standings: standings[white_tid].losses_t += 1
		elif ( score_b > score_w ):
			if black_tid in standings: standings[black_tid].wins_t += 1
			if white_tid in standings: standings[white_tid].losses_t += 1
		elif (score_w > score_b):
			if white_tid in standings: standings[white_tid].wins_t +=1
			if black_tid in standings: standings[black_tid].losses_t += 1
		elif (score_w == score_b):
			if black_tid in standings: standings[black_tid].ties_t += 1
			if white_tid in standings: standings[white_tid].ties_t += 1


		if game['type'] != "RR":
			continue

		if pod and game['pod'] != pod:
			continue

		standings[black_tid].games_played += 1
		standings[white_tid].games_played += 1

		if (score_b >= 0 and score_w >= 0 ):
			standings[black_tid].goals_allowed += score_w
			standings[white_tid].goals_allowed += score_b


		if (score_b == -1 or forfeit == "b"): #black forfeit
			standings[black_tid].points -= 2
			standings[black_tid].losses += 1

			standings[white_tid].wins += 1
			standings[white_tid].points += 2

		elif (score_w == -1 or forfeit == "w"): #white forfeit
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

	return sortStandings(standings, pod)


# wrapper function for standings, use to ger dictionary of standings
# dictionary indexed by rank and contains all the team information in Stat class
def getStandings(div=None, pod=None):
	#if not hasattr(g, 'standings'):
	#	g.standings = calcStandings()

	# filter for pod and div
	#if pod:
	#	standings = [x for x in g.standings if x.pod == pod]
	#elif div:
	#	standings = [x for x in g.standings if x.div == div]
	#else:
	#	standings = g.standings

	if pod:
		standings = calcStandings(pod)
	elif div :
		standings = calcStandings()
		standings = [x for x in standings if x.div == div]
	else:
		standings = calcStandings()

	return standings

# simple function for converting team ID index to real name
def getTeam(team_id):
	db = getDB()
	cur = db.execute('SELECT name FROM teams WHERE team_id=? AND tid=?', (team_id, app.config['TID']))
	team = cur.fetchone()

	if team:
		return team['name']
	else:
		return None

# true false function for determining if round robin play has been completed
def endRoundRobin(division=None, pod=None):
	#app.logger.debug("Running endRoundRobin - %s or %s" % (division, pod))

	db = getDB()
	if (division == None and pod  == None):
		cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND tid=?', app.config['TID'])
	elif (division == None and pod ):
		cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND pod=? AND tid=?',(pod, app.config['TID']))
	elif division:
		cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND division LIKE ? AND tid=?', \
			(division, app.config['TID']))
	else:
		cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND division LIKE ? POD=? AND tid=?', (division, pod, app.config['TID']))

	row = cur.fetchone()

	rr_games = row['games']

	if (division == None and pod == None):
		cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.tid=s.tid AND s.tid=?', \
			app.config['TID'])
	elif (division == None and pod):
		cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.pod=? AND g.tid=s.tid AND g.tid=?', \
			(pod, app.config['TID']))
	elif division:
		cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.tid=s.tid AND g.division=? AND s.tid=?',\
			(division, app.config['TID']))
	else:
		cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" \
			AND division LIKE ? and pod=? AND g.tid=s.tid AND s.tid=?',(division, pod, app.config['TID']))


	row = cur.fetchone()
	games_played = row['count']

	#app.logger.debug("%s-%s: RR Games = %s and we've played %s games" % (division, pod, rr_games, games_played))

	# first check if all games have been played
	if (games_played >= rr_games):
		#app.logger.debug("endRoundRobin returing true")
		return True
	else:
		#app.logger.debug("endRoundRobin returing false")
		return False

def checkForTies(standings):
	x=0
	while x < len(standings)-1:
		if cmpTeams(standings[x].team, standings[x+1].team) == 0:
			return True
		x = x+1

	x=0
	last=0
	while x < len(standings)-1:
		if cmpTeamsSort(standings[x].team, standings[x+1].team) == 0:
			if last == 1:
				flash("You need a three sided die, give up and go home")
				return True
			else:
				last = 1
		else:
			last = 0
		x = x+1

	return False

# gets team ID back from seed ranking, returns -1 if seeding isn't final
def getSeed(seed, division=None, pod=None):
	if ( endRoundRobin(division, pod) ):
		standings = getStandings(division, pod)
		if checkForTies(standings):
			return -1
		seed = int(seed) - 1
		return standings[seed].team.team_id
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

		# Winner of
		match = re.search( '^W(\d+)$', game)
		if match:
			gid = match.group(1)
			team_id = getWinner(gid)
			if (team_id == -1):
				game = "Winner of " + gid
				style="soft"
			elif (team_id == -2):
				game = "TIE IN GAME %s!!" % gid
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
				game = "TIE IN GAME %s!!" % gid
			else:
				team = getTeam(team_id)
				game = team

		#Seeded div/pod notation
		match = re.search( '^S([\w])(\d+)$', game)
		if match:
			group = match.group(1)
			seed = match.group(2)

			if group in getPods():
				team_id = getSeed( seed, None, group)
			elif group in getDivision():
				team_id = getSeed( seed, group, None)
			else:
				team_id = -1

			if ( team_id < 0 ):
				game = "Pod " + pod + " seed " + seed
				style="soft"
			else:
				name = getTeam(team_id)
				game = name
		# broken logic
		#else:
		#	app.logger.debug("Failure in getPlacings, no regex match: %s" % game)



		entry['place']= place
		entry['name'] = game
		entry['style'] = style

		final.append(entry)

	return final

# returns winner team ID of game by ID
def getWinner(game_id):
	db = getDB()
	cur = db.execute("SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?", (game_id,app.config['TID']))
	game = cur.fetchone()
	if game:
		if game['forfeit']:
			if game['forfeit'] == "b":
				return game['white_tid']
			elif game ['forfeit'] == "w":
				return game['black_tid']
		elif (game['score_b'] > game['score_w']):
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
	cur = db.execute("SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?", (game_id,app.config['TID']))
	game = cur.fetchone()
	if game:
		if game['forfeit']:
			if game['forfeit'] == "b":
				return game['black_tid']
			elif game ['forfeit'] == "w":
				return game['white_tid']
		elif (game['score_b'] < game['score_w']):
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

	# Redraw IDs
	match = re.search( '^R(\w)(\d+)$', game)
	if match:
		div = match.group(1)
		num = match.group(2)

		game = "Redraw " + div + num
		style="soft"

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

	# Seed notation - Division or Pod
	#match = re.search( '^S([A|B|C|O|E])?(\d+)$', game )
	match = re.search( '^S(\d\w|\w)(\d+)$', game )
	if match:
		group = match.group(1)
		seed = match.group(2)
		#app.logger.debug("Matching pod or division - %s" % group)

		if group in getPods():
			team_id = getSeed( seed, None, group)
		elif group in getDivisions():
			team_id = getSeed( seed, group, None)
		else:
			team_id = -1

		if ( team_id < 0 ):
			game = "%s Seed %s" % (group, seed)
			style="soft"
		else:
			team = getTeam(team_id)
			if group:
				game = "%s (%s-%s)" % (team, group, seed)

	# Winner of
	match = re.search( '^W(\d+)$', game)
	if match:
		gid = match.group(1)
		team_id = getWinner(gid)
		if (team_id == -1):
			game = "Winner of " + gid
			style="soft"
		elif (team_id == -2):
			game = "TIE IN GAME %s!!" % gid
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
			game = "TIE IN GAME %s!!" % gid
		else:
			team = getTeam(team_id)
			game = team + " (L" + gid + ")"

	# TBD Place Holder
	match = re.search('^TBD.*', game)
	if match:
		style="soft"

	team_id = int(team_id)

	return (team_id,game,style)

# loops through all games and creates expanded dictionary of games
# expands database short hand into human readable form
def expandGames(games):
	expanded = []
	db = getDB()

	#podColors = {'A':'#BDBDBD','B':'#2E2EFE','G':'#04B404','O':'#FF8000','Y':'#FFFF00',\
	#		'b':'#81F7F3','g':'#81F781','d':'#FF0000','e':'#F5D0A9','z':'#948A54',\
	#		'D':'#FF00FF'
	#	}

	podColors = {}

	for info in games:
		game = {}
		game["gid"] = info['gid']
		game["day"] = info['day']
		start_time = info['start_time']
		game["start_time"] = datetime.strptime(start_time, '%H:%M').strftime('%I:%M %p')
		game["pool"] = info['pool']
		game["type"] = info['type']
		game["description"] = info['description']
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


		cur = db.execute('SELECT score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?', (game['gid'],app.config['TID']))
		score = cur.fetchone()

		game['note_b'] = ""
		game['note_w'] = ""
		if score:
			game['score_b'] = score['score_b']
			game['score_w'] = score['score_w']
			if score['forfeit']:
				game['forfeit'] = score['forfeit']
				if score['forfeit'] == "b":
					game['note_b'] = "Forfeit"
				else:
					game['note_w'] = "Forfeit"
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
		cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod, type, description FROM games \
						WHERE tid=? ORDER BY day, start_time LIMIT ?,45",\
						(app.config['TID'], offset))
	# whole schedule
	elif (division == None and pod == None):
		cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod, type, description FROM games \
							WHERE tid=? ORDER BY day, start_time",app.config['TID'])
	# division schedule
	elif (pod == None):
		cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod, type, description FROM games \
							WHERE (division LIKE ? or type='CO') AND tid=? ORDER BY day, start_time", \
							(division, app.config['TID']))
	# pod schedule
	elif (division == None):
		# trickery to see if it is a division pod and get crossover games or not
		if pod in getDivisions():
			cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod, type, description FROM games \
								WHERE (pod like ? or type='CO') AND tid=? ORDER BY day, start_time",\
								(pod, app.config['TID']))
		else:
			cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod, type, description FROM games \
								WHERE pod like ? AND tid=? ORDER BY day, start_time",\
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
	cur = db.execute('SELECT gid, day, strftime("%H:%M", start_time) as start_time, pool, black, white, pod, type, description FROM games WHERE gid=? AND tid=? ',(gid, app.config['TID']))
	game = expandGames(cur.fetchall())

	return game[0];

def getTeamGames(team_id):
	db = getDB()

	cur = db.execute('SELECT gid, day, strftime("%H:%M", start_time) as start_time, pool, black, white, pod, type, description FROM games WHERE tid=? ORDER BY day, start_time',(app.config['TID']))
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

# returns dictionary of teams indexed by team id
def getTeams(div=None, pod=None):
	db = getDB()
	if (div == None and pod == None):
		cur = db.execute("SELECT team_id, name FROM teams WHERE tid=? ORDER BY name",app.config['TID'])
	elif (pod == None):
		cur = db.execute("SELECT team_id, name FROM teams WHERE division=? AND tid=? ORDER BY name", \
							(div, app.config['TID']))
	elif (div == None):
		cur = db.execute("SELECT t.team_id, t.name FROM teams t, pods p WHERE t.team_id=p.team_id AND p.pod=? AND t.tid=p.tid AND t.tid=?",\
			 				(pod, app.config['TID']))

	teams = []
	for team in cur.fetchall():
		teams.append({'team_id':team['team_id'],'name':team['name']})

	return teams

# returns list of all pod abbreviations that have teams assigned
def getPodsActive(div=None):
	db = getDB()
	if (div):
		cur = db.execute('SELECT DISTINCT p.pod FROM pods p, teams t WHERE p.team_id=t.team_id\
			 AND t.division=? and p.tid=? ORDER BY p.pod + 0 ASC',(div,app.config['TID']))
	else:
		cur = db.execute('SELECT DISTINCT p.pod FROM pods p WHERE p.tid=? ORDER BY p.pod + 0 ASC',(app.config['TID']))

	pods = []
	for r in cur.fetchall():
		pods.append(r['pod'])

	return pods

def getPodNamesActive(div=None):
	pods = getPodsActive(div)

	pod_names = []
	for pod in pods:
		name = expandGroupAbbr(pod)
		pod_names.append({'id':pod,'name':name})

	return pod_names

# returns list of all pod abbreviations
def getPods(div=None):
	db = getDB()
	if (div):
		cur = db.execute('SELECT DISTINCT g.pod FROM games g WHERE g.division=? AND g.tid=? ORDER BY g.pod + 0 ASC', (div, app.config['TID']))
	else:
		cur = db.execute('SELECT DISTINCT g.pod FROM games g WHERE g.tid=? ORDER BY g.pod + 0 ASC', app.config['TID'])

	pods = []
	for r in cur.fetchall():
		pods.append(r['pod'])

	return pods

# returns list of division abbreviations
def getDivisions():
	db = getDB()
	cur = db.execute("SELECT DISTINCT division FROM games WHERE tid=?", app.config['TID'])

	divisions = []
	for r in cur.fetchall():
		if r['division'] != "":
			divisions.append(r['division'])

	return divisions

# returns dictionary of division abbreviation and full name
def getDivisionNames():
	divs = getDivisions()

	div_names = []
	for div in divs:
		name = expandGroupAbbr(div)
		div_names.append({'id':div,'name':name})

	return div_names

# return division as string from team_id
def getDivision(team_id):
	db = getDB()
	cur = db.execute('SELECT division FROM teams WHERE team_id=? AND tid=?', (team_id, app.config['TID']))
	row = cur.fetchone()

	if row:
		return row['division']
	else:
		return None

# takes in short name for division or pod and returns full string for display
def expandGroupAbbr(group):
	db = getDB()
	cur = db.execute('SELECT name FROM groups WHERE group_id=? and tid=?', (group, app.config['TID']))

	row = cur.fetchone()

	if row:
		return row['name']
	else:
		return None

# returns list of Pods as strings, list is required because a single team might be in multiple pods
def getTeamPods(team_id):
	db = getDB()
	cur = db.execute('SELECT pod from pods WHERE team_id=? AND tid=?', (team_id, app.config['TID']))

	pods = []
	for r in cur.fetchall():
		pods.append(r['pod'])

	return pods

def getGamePod(gid):
	db = getDB()
	cur = db.execute('SELECT pod from games WHERE gid=? AND tid=?', (gid, app.config['TID']))
	row = cur.fetchone()

	return row['pod']

def getTournamentName():
	db = getDB()
	cur = db.execute("SELECT name FROM tournaments WHERE tid=?", app.config['TID'])
	row = cur.fetchone()

	return row['name']

def getTournamentID(short_name):
	db = getDB()

	cur = db.execute("SELECT tid FROM tournaments WHERE short_name=?", short_name)

	row = cur.fetchone()
	if row:
		return row['tid']
	else:
		return None

def getTournamentDetails(short_name=None):
	if short_name:
		tid = getTournamentID(short_name)
		if not tid:
			return None
	else:
		tid= app.config['TID']

	db = getDB()
	cur = db.execute("SELECT name, short_name, start_date, end_date, location FROM tournaments WHERE tid=?", tid)

	row = cur.fetchone()
	info = {}
	info['name'] = row['name']
	info['short_name'] = row['short_name']

	start_date = datetime.strptime(row['start_date'],"%Y-%m-%d")
	info['start_date'] = start_date
	end_date = datetime.strptime(row['end_date'],"%Y-%m-%d")
	info['end_date'] = end_date
	info['location'] = row['location']

	info['date_string'] = "%s-%s" % (start_date.strftime("%B %d"), end_date.strftime("%d, %Y" ))

	return info


def isGroup(group):
	db = getDB()
	cur = db.execute("SELECT count(*) FROM games WHERE (pod=? OR division=?) AND tid=?", (group, group, app.config['TID']))

	count = cur.fetchone()[0]

	if count > 0:
		return True
	else:
		return False

def genTieFlashes():
	if not hasattr(g, 'ties'):
		return 0

	ties = g.ties

	seen = set()
	list = [x for x in ties if x not in seen and not seen.add(x)]

	for tie in list:
		name_a = getTeam(tie[0])
		name_b = getTeam(tie[1])
		flash("There is a tie in the standings between %s & %s" % (name_a, name_b))

	flash("A coin flip is required, please see tournament director or head ref")
	return 0

def getTies():
	if not hasattr(g, 'ties'):
		return None

	ties = g.ties
	seen = set()
	list = [x for x in ties if x not in seen and not seen.add(x)]

	ties = []
	for tie in list:
		id_a = tie[0]
		id_b = tie[1]
		team_a = getTeam(id_a)
		team_b = getTeam(id_b)

		ties.append({'id_a':id_a, 'id_b':id_b,'team_a':team_a,'team_b':team_b})

	return ties

def getTournamentStats():
	db = getDB()
	stats = {}

	# total games
	cur = db.execute("SELECT count(*) as count FROM games WHERE tid=?", app.config['TID'])
	row = cur.fetchone()
	total = row['count']

	# games played
	cur = db.execute("SELECT count(*) as count FROM scores WHERE tid=?", app.config['TID'])
	row = cur.fetchone()
 	played = row['count']

	stats['total_games'] = (played, total)

	# round robin games
	cur = db.execute("SELECT count(*) as count FROM games WHERE type='RR' AND tid=?", app.config['TID'])
	row = cur.fetchone()
	total = row['count']

	# round robin games played
	cur  = db.execute("SELECT count(*) as count FROM games g, scores s WHERE g.gid=s.gid \
		AND g.type='RR' AND g.tid=s.tid AND g.tid=?", app.config['TID'])
	row = cur.fetchone()
	played = row['count']

	stats['round_robin'] = (played, total)
	return stats


# takes in form dictionary from POST and updates/creates score for single game
def updateGame(form):
	db = getDB()
	gid = int(form.get('gid'))
	score_b = int(form.get('score_b'))
	score_w = int(form.get('score_w'))
	black_tid = int(form.get('btid'))
	white_tid = int(form.get('wtid'))
	pod = form.get('pod')

	forfeit_w = form.get('forfeit_w')
	forfeit_b = form.get('forfeit_b')

	if forfeit_b:
		forfeit = "b"
	elif forfeit_w:
		forfeit = "w"
	else:
		forfeit = None

	if not isinstance(score_b, int):
		return -1

	if not isinstance(score_w, int):
		return -1

	cur = db.execute("INSERT OR IGNORE INTO scores (black_tid, white_tid, score_b, score_w,tid, gid, pod, forfeit) VALUES(?,?,?,?,?,?,?,?)", \
		(black_tid,white_tid,score_w,score_b,app.config['TID'],gid, pod, forfeit))
	db.commit()

	cur = db.execute("UPDATE scores SET score_b=?,score_w=?, forfeit=? WHERE tid=? AND gid=?", (score_b,score_w, forfeit, app.config['TID'],gid))
	db.commit()

	popSeededPods()

	return 1

# Checks if first round of pods is all finished and populates seeded pods if necessary
# NOT DYNAMIC requires hard coding right now
def popSeededPods():
	app.logger.debug("popping some pods")

	params = getParams()

	if 'seeded_pods' in params:
		if params['seeded_pods'] == 1:
			return 0
	else:
		return 0

	round1 = ("7P","1P","2P","3P","4P","5P")

	pods_done =[]
	for pod in round1:
		pods_done.append(endRoundRobin(None, pod))

	if not all(done == True for done in pods_done):
		return 0

	ties = []
	for pod in round1:
			ties.append(checkForTies(getStandings(None,pod)))

	if not all(tie == False for tie in ties):
		return 0

 	app.logger.debug("All round-robins done - seeding the pods %s" % pods_done)

	db = getDB()

	seededPods = ['A','B','C']
	pod_id = 1
	seeding = {}
# 	seeding['7P'] = {'1':'A','2':'A','3':'A'}
# 	seeding['1P'] = {'1':'A','2':'A','3':'A','4':'B'}
# 	seeding['2P'] = {'1':'A','2':'A','3':'B','4':'B'}
# 	seeding['3P'] = {'1':'B','2':'B','3':'C','4':'C'}
# 	seeding['4P'] = {'1':'B','2':'B','3':'C','4':'C'}
# 	seeding['5P'] = {'1':'B','2':'C','3':'C','4':'C'}
	seeding['7P'] = ['A','A','A']
	seeding['1P'] = ['A','A','A','B']
	seeding['2P'] = ['A','A','B','B']
	seeding['3P'] = ['B','B','C','C']
	seeding['4P'] = ['B','B','C','C']
	seeding['5P'] = ['B','C','C','C']


	for pod in round1:
		podStandings = getStandings(None,pod)

# 		pod_offset=0
# 		for rank in podStandings:
# 			team = rank.team
# 			team_id = team.team_id
# 			pod = seededPods[pod_offset]
# 			cur = db.execute("INSERT INTO pods (tid, team_id, pod, pod_id) VALUES (?,?,?,?)",(app.config['TID'], team_id, pod, pod_id))
# 			db.commit()
# 			pod_offset +=1
#
# 		pod_id +=1

		rules = seeding[pod]
		offset = 0
		for rank in podStandings:
			team = rank.team
			team_id = team.team_id
			pod = rules[offset]
			cur = db.execute("INSERT INTO pods (tid, team_id, pod) VALUES (?,?,?)",(app.config['TID'], team_id, pod))
 			db.commit()
 			cur = db.execute("UPDATE teams SET division=? WHERE team_id=? and tid=?",(pod, team_id, app.config['TID']))
 			db.commit()
 			offset +=1


	cur = db.execute("UPDATE params SET val=1 WHERE tid=? and field='seeded_pods'" , (app.config['TID'],))
	db.commit()

	return 1

def updateSiteStatus(active, message=None):
	# delete first incase message is being updated
	clearParam("site_disabled")

	if not active:
		if message == "":
			message = "Site disabled temporarily, please check back later."

		addParam("site_disabled", message)

	return 0

def getDisableMessage():
	db = getDB()

	cur = db.execute("SELECT val FROM params WHERE field=? AND tid=?", ("site_disabled", app.config['TID']))
	row = cur.fetchone()

	if row:
		return row['val']
	else:
		return False

def updateSiteMessage(message):
	db = getDB()

	if message:
		clearParam("site_message")
		addParam("site_message", message)
	else:
		clearParam("site_message")

	return 0

# redraws team for a division with POST from /admin/redraw
def redraw_teams(form):
	if not "div" in form:
		flash("Invalid form, no idea what you did")
		return 0

	div = form.get('div')
	app.logger.debug(form)
	check=[]
	redraws=[]

	# get list of ids that need a redraw
	redraw_ids = getRedraw(div)

	for e in form:
		match = re.search('^T(\d+)$', e)
		if match:
			team_id = match.group(1)
			redraw_id = form.get(e)
			check.append(redraw_id)
			if redraw_id == "":
				flash("You missed a team ID")
				return div
			if redraw_id not in redraw_ids:
				flash("Invalid ID, can't find in redraws")
				return div
			redraws.append({'team_id':team_id, 'redraw_id':redraw_id})

	# check that each redraw ID is unique
	if len(check) > len(set(check)):
		flash("You put a team ID in twice!")
		return div

	# everything looks good, cross your fingers and go
	for draw in redraws:
		redraw_execute(div, draw['redraw_id'], draw['team_id'])

	# once the redraw is complete, we need to change the tyoe on the played
	# head to head games to E so they aren't counted towards standings
	#
	### SHOULD ADD CHECK THAT THIS IS WHAT THE TOURNAMENTS WANTS ###
	trimRoundRobin(div)

	flash("Redraw Complete!")
	return 0

# return list of redraws needed
def getRedraw(div):
	db = getDB()
	ids = []

	cur = db.execute('SELECT white, black FROM games WHERE white LIKE "R%" or black LIKE "R%" AND division=? AND tid=?', (div,app.config['TID']))
	for r in cur.fetchall():
		match = re.search('^R(\w)(\d+)',r['white'])
		if match:
			if match.group(1) == div:
				ids.append(match.group(2))
		match = re.search('^R(\w)(\d+)',r['black'])
		if match:
			if match.group(1) == div:
				ids.append(match.group(2))

	return list(set(ids))

# executes an individal redraw update
# takes in division name, redraw number and team id
def redraw_execute(div, redraw_id, team_id):
	app.logger.debug("Execute redraw for division: %s - R%s is now T%s" % (div, redraw_id, team_id))

	redraw_string = "R%s%s" % (div, redraw_id)
	team_string = "T%s" % (team_id)

	if not getTeam(team_id):
		app.logger.debug("Team ID doesn't exist, somethings really broke")
		return 1

	db = getDB()
	cur = db.execute("UPDATE games SET white=? WHERE white=? AND tid=?" , (team_string, redraw_string,app.config['TID'] ))
	db.commit()
	cur = db.execute("UPDATE games SET black=? WHERE black=? AND tid=?" , (team_string, redraw_string,app.config['TID'] ))
	db.commit()

	return 0

# function trims a round-robin down to only one head-to-head game per team_string
# required for partial round-robin tournaments
# team redraw must already be comleted
def trimRoundRobin(div):
	db = getDB()

	team_list = getTeams(div)

	while len(team_list) > 0:
		cur_team = team_list.pop()
		for opponent in team_list:
			a="T%s" % cur_team['team_id']
			b="T%s" % opponent['team_id']
			cur = db.execute("SELECT gid FROM games WHERE ((white=? AND black=?) or (white=? and black=?))\
				AND division=? AND type='RR' AND tid=? ORDER BY gid", (a,b,b,a,div,app.config['TID']))
			games = cur.fetchall()

			if len(games) > 2:
				app.logger.debug("Found 3+ h2h between %s and %s, doing nothing" % (a,b))
			if len(games) == 2:
				gid = games[0]['gid']
				app.logger.debug("Found 2 h2h games between %s and %s, trimming game %s" % (a,b, gid))
				cur = db.execute("UPDATE games SET type='E' WHERE gid=? and tid=?", (gid, app.config['TID']))
				db.commit()

	return 0

def updateConfig(form):
	if not "config_id" in form:
		flash("You didn't give me an ID, go away")
		return 0

	config_id = form.get('config_id')
	if config_id == "site_active":
		switch = form.get('active_toggle')
		message = form.get('message')
		if (switch == "on"):
			updateSiteStatus(False, message)
		else:
			updateSiteStatus(True)
	elif config_id == "coin_flip":
		id_a = form.get('id_a')
		id_b = form.get('id_b')
		winner = form.get('winner')

		addCoinFlip(id_a, id_b, winner)
	elif config_id == "site_message":
		switch = form.get('active_toggle')
		message = form.get('message')
		if (switch == "on"):
			updateSiteMessage(message)
		else:
			updateSiteMessage(None)
	else:
		flash("I don't understand that config option, nothing changed")

	return 0

#######################################
## Main Routes
#######################################

@app.route('/')
def renderMain():

	message = getDisableMessage()
	if message:
		return render_template('site_down.html', message=message)

	games = getGames()
	pods = getPodsActive()
	placings = getPlacings()
	divisions = getDivisionNames()
	pods = getPodsActive()
	team_list = getTeams()
	pod_names = getPodNamesActive()

	teams = []
	if pods:
		for pod in pods:
			teams += getStandings(None, pod)
	else:
		teams = getStandings()

	titleText="Full "
	standings = []
	for team in teams:
		standings.append(team.__dict__)

	genTieFlashes()

	return render_template('show_main.html', tournament=getTournamentDetails(),\
		standings=standings, games=games, pods=pod_names, titleText=titleText, \
		placings=placings, divisions=divisions, team_list=team_list, site_message=getParam('site_message'))

@app.route('/div/<division>')
def renderDivision(division):

	message = getDisableMessage()
	if message:
		return render_template('site_down.html', message=message)

	if not isGroup(division):
		flash("Invalid division")
		return redirect(request.url_root)

	games = getGames(division)
	divisions = getDivisionNames()
	team_list = getTeams(division, None)
	pod_names = getPodNamesActive(division)

	pods = getPodsActive(division)


	teams = []
	if len(pods) > 0:
		for pod in pods:
			teams += getStandings(None, pod)
	else:
		teams = getStandings(division)

	standings = []
	for team in teams:
		standings.append(team.__dict__)

	div_name = expandGroupAbbr(division)
	if div_name:
		titleText = div_name
	else:
		titleText = "%s Div" % division.upper()

	genTieFlashes()

	#return render_template('show_individual.html', tournament=getTournamentName(), standings=standings, games=games, titleText=titleText)
	return render_template('show_main.html', tournament=getTournamentDetails(), standings=standings,\
		 games=games, titleText=titleText, pods=pod_names, divisions=divisions, team_list=team_list, site_message=getParam('site_message'))

@app.route('/pod/<pod>')
def renderPod(pod):

	message = getDisableMessage()
	if message:
		return render_template('site_down.html', message=message)

	if not isGroup(pod):
		flash("Invalid pod")
		return redirect(request.url_root)

	games = getGames(None,pod)
	teams = getStandings(None, pod)
	pods = getPodsActive()
	team_list = getTeams(None, pod)
	pod_names = getPodNamesActive()


	standings = []
	for team in teams:
		standings.append(team.__dict__)


	pod_name = expandGroupAbbr(pod)
	if pod_name:
		titleText = pod_name
	else:
		titleText = pod.upper() + " Pod"

	genTieFlashes()

	return render_template('show_main.html', tournament=getTournamentDetails(), standings=standings,\
		games=games, titleText=titleText, pods=pod_names, team_list=team_list, site_message=getParam('site_message'))


@app.route('/team/<team_id>')
def renderTeam(team_id):

	message = getDisableMessage()
	if message:
		return render_template('site_down.html', message=message)

	divisions = getDivisionNames()

	if not team_id.isdigit():
		flash("Invalid team ID, must be integer")
		return redirect(request.url_root)

	team_id = int(team_id)

	titleText = getTeam(team_id)

	if titleText == None:
		flash("Team ID %s doesn't exist" % team_id)
		return redirect(request.url_root)

	division = getDivision(team_id)
	pod_names = getPodNamesActive(division)

	teams = []
	games = getTeamGames(team_id)

	pods = getTeamPods(team_id)
	if len(pods) > 0:
		for pod in pods:
			teams.append(getStandings(None, pod))
	else:
		teams.append(getStandings(division))

	standings = []
	for div in teams:
		for team in div:
			standings.append(team.__dict__)


	#team_list = getTeams(division)

	#noteText="Only showing confirmed games. Subsequent games will be added as determined by seeding. Check back."
	#noteText = "WARNING: The schedule above will be incomplete until all games are seeded (ie. bracket games, \
	#games determined by win/loss, etc. for the finals). Check schedule throughout tournament for updates."
	noteText=None

	genTieFlashes()

	return render_template('show_main.html', tournament=getTournamentDetails(), standings=standings, games=games,\
		titleText=titleText, pods=pod_names, noteText=noteText, divisions=division, site_message=getParam('site_message'))


@app.route('/tv')
@app.route('/tv/<offset>')
def renderTV(offset=None):

	message = getDisableMessage()
	if message:
		return render_template('site_down.html', message=message)

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

	return render_template('show_tv.html', standings=standings, games=games, titleText=titleText, request=request, placings=placings)

@app.route('/print')
@app.route('/print/<offset>')
def renderPrint(offset=None):

	message = getDisableMessage()
	if message:
		return render_template('site_down.html', message=message)

	division=None

	games = getGames(division,None,offset)
	#pods = getPodsInPlay(division)
	#placings = getPlacings(division)

	#teams = []
	#teams = getStandings()

	days_games = []
	days = {}
	days['Fri'] = []
	days['Sat'] = []
	days['Sun'] = []
	for game in games:
		days[game['day']].append( game )

	days_games.append({'name':'Friday', 'games':days['Fri']})
	days_games.append({'name':'Saturday', 'games':days['Sat']})
	days_games.append({'name':'Sunday', 'games':days['Sun']})


	titleText="Day "

	return render_template('show_print_groups.html', group_games=days_games, titleText=titleText, tournament=getTournamentDetails())

@app.route('/print/pod')
@app.route('/print/pod/<pod>')
def renderPrintPods(pod=None):

	message = getDisableMessage()
	if message:
		return render_template('site_down.html', message=message)

	pods_games = []
	if pod:
		single = {}
		single['pod'] = pod
		single['name'] = expandGroupAbbr(pod)
		single['games'] = getGames(None,pod)
		pods_games.append(single)
	else:
		pod_names = getPods()
		for pod in pod_names:
			if pod == "":
				continue
			single = {}
			single['name'] = expandGroupAbbr(pod)
			single['games'] = getGames(None,pod)
			pods_games.append(single)

	titleText="Pods "

	return render_template('show_print_groups.html', group_games=pods_games, titleText=titleText, tournament=getTournamentDetails())

#######################################
## APIs
#######################################
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

#######################################
## Admin panel functions
#######################################
@app.route("/admin")
def renderAdmin():
	pods = getPodsActive()

	teams = []
	if pods:
		for pod in pods:
			teams += getStandings(None, pod)
	else:
		teams = getStandings()

	ties = getTies()
	genTieFlashes()

	divisions = getDivisions()
	redraws= []
	for div in divisions:
		l = getRedraw(div)
		if l:
			redraws.append(div)

	stats = getTournamentStats()

	return render_template('admin/show_admin.html', tournament=getTournamentDetails(), stats=stats, \
		ties=ties, disable_message=getDisableMessage(), site_message=getParam('site_message'), redraws=redraws)

@app.route('/admin/update', methods=['POST','GET'])
#@basic_auth.required
def renderUpdate():
	if request.method =='GET':
		if request.args.get('gid'):
			game = getGame( request.args.get('gid') )
			if ( game['score_b'] == "--"):
				game['score_b'] = "0"
			if ( game['score_w'] == "--"):
				game['score_w'] = "0"

			if ( game['black_tid'] < 0 or game['white_tid'] < 0):
				flash('Team(s) not determined yet. Cannot set score')
				return redirect(request.base_url)
			return render_template('/admin/update_single.html', game=game)
		else:
			games = getGames()
			return render_template('/admin/show_update.html', games=games, tournament=getTournamentName())
	if request.method == 'POST':
		updateGame(request.form)
		return redirect(request.base_url)

@app.route('/admin/update_config', methods=['POST','GET'])
def updateConfigPost():
	if request.method == 'GET':
		flash("You're not supposed to do that")
		return redirect("/admin")
	elif request.method == 'POST':
		updateConfig(request.form)
		return redirect("/admin")

@app.route('/admin/redraw', methods=['POST'])
@app.route('/admin/redraw/<div>', methods=['GET'])
def redraw(div=None):
	if request.method == 'GET':
		if not isGroup(div):
			flash("Invalid division")
			return redirect("/admin")

		team_list = getTeams(div, None)

		div_name = expandGroupAbbr(div)
		if div_name:
			div_name = div_name
		else:
			div_name = "%s Division" % div.upper()

		return render_template('/admin/redraw.html', div=div, div_name=div_name, teams=team_list, tournament=getTournamentDetails())
	if request.method == 'POST':
		res = redraw_teams(request.form)
		if res == 0:
			return redirect("/admin")
		else:
			return redirect("/admin/redraw/%s" % res)


#######################################
## Static pages
#######################################
@app.route('/faq')
def renderFAQ():
	divisions = getDivisionNames()
	team_list = getTeams()
	pod_names = getPodNamesActive()

	return render_template('faq.html', pods=pod_names, divisions=divisions, team_list=team_list)

app.wsgi_app = ProxyFix(app.wsgi_app)

if __name__ == '__main__':
	app.run(host='0.0.0.0 ')
