from string import split
from app import app
# class used for calculating standings, stat object has all the values
# for the things standings are calculator against


class Stats(object):

	def __init__(self, tournament, team_id, pod=None):

		self.team_id = team_id

		tid = tournament.tid
		db = tournament.db

		cur = db.execute('SELECT t.name, t.division FROM teams t WHERE tid=? and team_id=?', (tid, team_id))
		team = cur.fetchone()

		self.name = team['name']
		self.division = team['division']

		self.pod = pod

		# stats
		self.points = 0
		self.wins = 0
		self.losses = 0
		self.ties = 0
		self.goals_allowed = 0
		self.games_played = 0
		self.wins_t = 0
		self.losses_t = 0
		self.ties_t = 0
		cur = db.execute('SELECT s.black_tid, s.white_tid, s.score_b, s.score_w, s.forfeit, g.type, g.pod  FROM scores s, games g WHERE g.gid=s.gid AND g.tid=s.tid AND (white_tid=? or black_tid=?) AND s.tid=?', (team_id, team_id, tid))

		games = cur.fetchall()

		for game in games:
			black_tid = game['black_tid']
			white_tid = game['white_tid']
			score_b = game['score_b']
			score_w = game['score_w']
			forfeit = game['forfeit']

			game_pod = None
			if game['pod']:
				game_pod = game['pod']

			self.games_played += 1

			# forfeit
			if (forfeit == "b" and black_tid == team_id):
				if game_pod == pod:
					self.losses += 1
					self.points -= 2
				self.losses_t += 1

			if (forfeit == "b" and white_tid == team_id):
				if game_pod == pod:
					self.wins += 1
					self.points += 2
				self.wins_t += 1

			if (forfeit == "w" and white_tid == team_id):
				if game_pod == pod:
					self.losses += 1
					self.points -= 2
				self.losses_t += 1

			if forfeit == "b" and black_tid == team_id:
				if game_pod == pod:
					self.wins += 1
					self.points += 2
				self.wins_t += 1

			# black won
			if score_b > score_w and black_tid == team_id:
				if game_pod == pod:
					self.wins += 1
					self.points += 2
				self.wins_t += 1
			elif score_b > score_w and white_tid == team_id:
				if game_pod == pod:
					self.losses += 1
				self.losses_t += 1

			# white won
			if score_b < score_w and white_tid == team_id:
				if game_pod == pod:
					self.wins += 1
					self.points += 2
				self.wins_t += 1
			elif score_b < score_w and black_tid == team_id:
				if game_pod == pod:
					self.losses += 1
				self.losses_t += 1

			if score_w == score_b and forfeit == None:
				if game_pod == pod:
					self.ties += 1
					self.points += 1
				self.ties_t += 1

			if game['type'] != "RR":
				continue

			if pod and game['pod'] != pod:
				continue


			if white_tid == team_id:
				self.goals_allowed += score_b
			elif black_tid == team_id:
				self.goals_allowed += score_w


		# end for game in games
		#print self

	def __repr__(self):
		return '{}({}): {} {}-{}-{}'.format(self.name,self.team_id, self.points, self.wins, self.losses, self.ties)

	def __cmp__(self, other):
		if hasattr(other, 'points'):
			return other.points.__cmp__(self.points)

	def __eq__(self, other):
		if self.cmpTeamPoints(self, other) == 0:
			return True
		else:
			return False

	# Compares teams only on points, checks division and pod first to make sure they aren't
	# in the same division, used for pre-sorting rank before applying tie breakers
	# used by __cmp__ function for Stats struct
	def cmpTeamPoints(self, team_b, team_a):
		#if (team_a.division.lower() != team_b.division.lower()):
		#	return divToInt(team_a.division) - divToInt(team_b.division)
		#elif (team_a.pod != team_b.pod):
		#	return podToInt(team_a.pod) - podToInt(team_b.pod)
		if (team_a.points != team_b.points):
			return team_a.points - team_b.points
		else:
			return 0

	def goalsAllowed(self, other):
		return self.goals_allowed

class Ranking(object):
	def __init__(self, div, pod, place, team):
		self.div = div
		self.pod = pod
		self.place = place
		self.team = team

	def __repr__(self):
		return '{}-{}-{}: {}'.format(self.div, self.pod, self.place, self.team.name)

	def __eq__(self, other):
		team_a = self.team
		team_b = other.team

		if (team_a.division.lower() != team_b.division.lower()):
			return False
		elif (team_a.wins != team_b.wins):
			return False
		elif (team_a.losses != team_b.losses):
			return False
		elif (team_a.goals_allowed != team_b.goals_allowed):
			return False
		else:
			return True


class Params(object):
	# loads in all the rows from the config table for the tournament ID
	# config table is used to store parameters for various logic in the code
	def __init__(self, tournament):
		self.t = tournament

	def getAll(self):
		db = self.t.db
		tid = self.t.tid
		params = {}

		cur = db.execute('SELECT field, val FROM params where tid=?', (tid,))

		rows = cur.fetchall()

		for config in rows:
			params[config['field']] = config['val']

		return params

	def getParam(self, field):
		params = self.getAll()
		if field in params:
			return params[field]
		else:
			return None

	# add new value to params list
	def addParam(self, field, val):
		db = self.t.db
		tid = self.t.tid

		cur = db.execute('INSERT INTO params VALUES (?,?,?)', (tid, field, val))
		db.commit()

		#g.params = self.loadParams()
		return 0

	def updateParam(self,field, val):
		db = self.t.db
		tid= self.t.tid

		cur = db.execute('UPDATE params SET val=? WHERE field=? and tid=?', (val, field, tid))
		db.commit()

		#g.params = self.loadParams()
		return 0

	def clearParam(self, field):
		db = self.t.db
		tid = self.t.tid

		cur = db.execute("DELETE FROM params where field=? AND tid=?", (field, tid))
		db.commit()

		#g.params = self.loadParams()
		return 0
