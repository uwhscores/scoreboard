from datetime import datetime
import re
from game import Game
from models import Stats, Ranking, Params
from flask import g, flash
from string import split
from app import app

# main struction for a tournament


class Tournament(object):

    def __init__(self, tid, name, short_name, start_date, end_date, location, active, db):
        self.tid = tid
        self.name = name
        self.short_name = short_name
        # self.start_date = start_date
        self.end_date = end_date
        self.location = location
        self.is_active = active
        self.db = db

        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.date_string = "%s-%s" % (
            self.start_date.strftime("%B %d"), self.end_date.strftime("%d, %Y"))


        days = []
        cur = db.execute("SELECT DISTINCT day from games WHERE tid=?", (tid,))
        for r in cur.fetchall():
            days.append(r['day'])

        self.days = days

    def __repr__(self):
        return "{} - {} - {}".format(self.name, self.start_date, self.location)

    # for sorted by start_date descending (most recent first)
    def __cmp__(self, other):
        delta = other.start_date - self.start_date
        return delta.days

    # simple function for converting team ID index to real name
    def getTeam(self, team_id):
        db = self.db
        cur = db.execute(
            'SELECT name FROM teams WHERE team_id=? AND tid=?', (team_id, self.tid))
        team = cur.fetchone()

        if team:
            return team['name']
        else:
            return None

    # returns dictionary of teams indexed by team id
    def getTeams(self, div=None, pod=None):
        db = self.db
        if (div == None and pod == None):
            cur = db.execute(
                "SELECT team_id, name, division FROM teams WHERE tid=? ORDER BY name", (self.tid,))
        elif (pod == None):
            cur = db.execute("SELECT team_id, name, division FROM teams WHERE division=? AND tid=? ORDER BY name",
                             (div, self.tid))
        elif (div == None):
            cur = db.execute("SELECT t.team_id, t.name, t.division FROM teams t, pods p WHERE t.team_id=p.team_id AND p.pod=? AND t.tid=p.tid AND t.tid=?",
                             (pod, self.tid))

        teams = []
        for team in cur.fetchall():
            teams.append({'team_id': team['team_id'], 'name': team['name'], 'division': team['division']})

        return teams

    # gets full list of games for display
    # returns list of dictionaries for each game
    def getGames(self, division=None, pod=None, offset=None):
        db = self.db

        if (offset != None):
            cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, division, pod, type, description FROM games \
    						WHERE tid=? ORDER BY day, start_time LIMIT ?,45",
                             (self.tid, offset))
        # whole schedule
        elif (division == None and pod == None):
            cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod, division, type, description FROM games \
    							WHERE tid=? ORDER BY day, start_time", (self.tid,))
        # division schedule
        elif (pod == None):
            cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod, division, type, description FROM games \
    							WHERE (division LIKE ? or type='CO') AND tid=? ORDER BY day, start_time",
                             (division, self.tid))
        # pod schedule
        elif (division == None):
            # trickery to see if it is a division pod and get crossover games
            # or not
            if pod in getDivisions():
                cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, division, pod, type, description FROM games \
    								WHERE (pod like ? or type='CO') AND tid=? ORDER BY day, start_time",
                                 (pod, self.tid))
            else:
                cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, division, pod, type, description FROM games \
    								WHERE pod like ? AND tid=? ORDER BY day, start_time",
                                 (pod, self.tid))

        # if (division == None and pod==None and offset):
        #	cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
        #					WHERE tid=? ORDER BY day, start_time LIMIT ?,40",\
        #					(self.tid, offset))
        # else:
        #	cur = db.execute("SELECT gid, day, strftime(\"%H:%M\", start_time) as start_time, pool, black, white, pod FROM games \
        #					WHERE tid=? ORDER BY day, start_time",\
        #					(self.tid))

        # games = self.expandGames(cur.fetchall())
        games = []
        for g in cur.fetchall():
            games.append(Game(self, g['gid'], g['day'], g['start_time'], g['pool'], g['black'], g['white'],
                              g['type'], g['division'], g['pod'], g['description']))

        return games

    def getTeamGames(self, team_id):
        db = self.db

        cur = db.execute('SELECT gid, day, strftime("%H:%M", start_time) as start_time, pool, black, white, division, pod, type, description \
                        FROM games WHERE tid=? ORDER BY day, start_time', (self.tid,))
        # allGames = self.expandGames(cur.fetchall())
        team_games = cur.fetchall()

        games = []
        for g in team_games:
            game = Game(self, g['gid'], g['day'], g['start_time'], g['pool'], g['black'], g['white'],
                        g['type'], g['division'], g['pod'], g['description'])
            if game.black_tid == team_id or game.white_tid == team_id:
                # if (game['black_tid'] == team_id or game['white_tid'] == team_id) or
                # (game['black_tid'] < 0 or game['white_tid'] < 0):
                if game.black_tid == team_id:
                    game.style_b = "strong"
                elif game.white_tid == team_id:
                    game.style_w = "strong"

                games.append(game)

        return games

    # gets single game by ID, returns single dictionary
    def getGame(self, gid):
        db = self.db
        cur = db.execute('SELECT gid, day, strftime("%H:%M", start_time) as start_time, pool, black, white, division, pod, type, description \
                FROM games WHERE gid=? AND tid=? ', (gid, self.tid))
        g = cur.fetchone()

        if g:
            game = Game(self, g['gid'], g['day'], g['start_time'], g['pool'], g['black'], g['white'],
                    g['type'], g['division'], g['pod'], g['description'])
            return game
        else:
            return None

    # returns winner team ID of game by ID
    def getWinner(self, game_id):
        db = self.db
        cur = db.execute(
            "SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?", (game_id, self.tid))
        game = cur.fetchone()
        if game:
            if game['forfeit']:
                if game['forfeit'] == "b":
                    return game['white_tid']
                elif game['forfeit'] == "w":
                    return game['black_tid']
            elif (game['score_b'] > game['score_w']):
                return game['black_tid']
            elif (game['score_b'] < game['score_w']):
                return game['white_tid']
            else:
                return -2
        else:
            return -1

    # returns loser team ID of game by ID
    def getLoser(self, game_id):
        db = self.db
        cur = db.execute(
            "SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?", (game_id, self.tid))
        game = cur.fetchone()
        if game:
            if game['forfeit']:
                if game['forfeit'] == "b":
                    return game['black_tid']
                elif game['forfeit'] == "w":
                    return game['white_tid']
            elif (game['score_b'] < game['score_w']):
                return game['black_tid']
            elif (game['score_b'] > game['score_w']):
                return game['white_tid']
            else:
                return -2
        else:
            return -1

    # returns list of division abbreviations
    def getDivisions(self):
        db = self.db
        cur = db.execute(
            "SELECT DISTINCT division FROM games WHERE tid=?", (self.tid,))

        divisions = []
        for r in cur.fetchall():
            if r['division'] != "":
                divisions.append(r['division'])

        return divisions

    # returns dictionary of division abbreviation and full name
    def getDivisionNames(self):
        divs = self.getDivisions()

        div_names = []
        for div in divs:
            name = self.expandGroupAbbr(div)
            div_names.append({'id': div, 'name': name})

        return div_names

    # return division as string from team_id
    def getDivision(self, team_id):
        db = self.db
        cur = db.execute(
            'SELECT division FROM teams WHERE team_id=? AND tid=?', (team_id, self.tid))
        row = cur.fetchone()

        if row:
            return row['division']
        else:
            return None

    # returns list of all pod abbreviations
    def getPods(self, div=None):
        db = self.db
        if (div):
            cur = db.execute(
                'SELECT DISTINCT g.pod FROM games g WHERE g.division=? AND g.tid=? ORDER BY g.pod + 0 ASC', (div, self.tid))
        else:
            cur = db.execute(
                'SELECT DISTINCT g.pod FROM games g WHERE g.tid=? ORDER BY g.pod + 0 ASC', (self.tid,))

        pods = []
        for r in cur.fetchall():
            pods.append(r['pod'])

        return pods

    # returns list of all pod abbreviations that have teams assigned
    def getPodsActive(self, div=None):
        db = self.db
        if (div):
            cur = db.execute('SELECT DISTINCT p.pod FROM pods p, teams t WHERE p.team_id=t.team_id\
    			 AND t.division=? and p.tid=? ORDER BY p.pod + 0 ASC', (div, self.tid))
        else:
            cur = db.execute(
                'SELECT DISTINCT p.pod FROM pods p WHERE p.tid=? ORDER BY p.pod + 0 ASC', (self.tid,))

        pods = []
        for r in cur.fetchall():
            pods.append(r['pod'])

        return pods

    def getPodNamesActive(self, div=None):
        pods = self.getPodsActive(div)

        pod_names = []
        for pod in pods:
            name = self.expandGroupAbbr(pod)
            pod_names.append({'id': pod, 'name': name})

        return pod_names

    # takes in short name for division or pod and returns full string for
    # display
    def expandGroupAbbr(self, group):
        db = self.db
        cur = db.execute(
            'SELECT name FROM groups WHERE group_id=? and tid=?', (group, self.tid))

        row = cur.fetchone()

        if row:
            return row['name']
        else:
            return None

    def isGroup(self, group):
        db = self.db
        cur = db.execute(
            "SELECT count(*) FROM games WHERE (pod=? OR division=?) AND tid=?", (group, group, self.tid))

        count = cur.fetchone()[0]

        if count > 0:
            return True
        else:
            return False

    # gets team ID back from seed ranking, returns -1 if seeding isn't final
    def getSeed(self, seed, division=None, pod=None):
        if (self.endRoundRobin(division, pod)):
            standings = self.getStandings(division, pod)
            if self.checkForTies(standings):
                return -1
            seed = int(seed) - 1
            return standings[seed].team.team_id
        else:
            return -1


    def getPlacings(self, div=None):
    	db = self.db
    	if (div):
    		cur = db.execute("SELECT place, game FROM rankings WHERE division=? AND tid=?", (div,self.tid))
    	else:
    		cur = db.execute("SELECT place, game FROM rankings WHERE tid=?", (self.tid,))

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
    			team_id = self.getWinner(gid)
    			if (team_id == -1):
    				game = "Winner of " + gid
    				style="soft"
    			elif (team_id == -2):
    				game = "TIE IN GAME %s!!" % gid
    			else:
    				team = self.getTeam(team_id)
    				game = team

    		# Loser of
    		match = re.search( '^L(\d+)$', game)
    		if match:
    			gid = match.group(1)
    			team_id = self.getLoser(gid)
    			if (team_id == -1):
    				game = "Loser of " + gid
    				style="soft"
    			elif (team_id == -2):
    				game = "TIE IN GAME %s!!" % gid
    			else:
    				team = self.getTeam(team_id)
    				game = team

    		#Seeded div/pod notation
    		match = re.search( '^S([\w])(\d+)$', game)
    		if match:
    			group = match.group(1)
    			seed = match.group(2)

    			if group in self.getPods():
    				team_id = self.getSeed( seed, None, group)
    			elif group in self.getDivision():
    				team_id = self.getSeed( seed, group, None)
    			else:
    				team_id = -1

    			if ( team_id < 0 ):
    				game = "Pod " + pod + " seed " + seed
    				style="soft"
    			else:
    				name = self.getTeam(team_id)
    				game = name
    		# broken logic
    		#else:
    		#	app.logger.debug("Failure in getPlacings, no regex match: %s" % game)



    		entry['place']= place
    		entry['name'] = game
    		entry['style'] = style

    		final.append(entry)

    	return final

    # builds parameters for given tournament
    # stashes them globably to avoid having to constaly resetup
    def getParams(self):
        if not hasattr(g, 'params'):
            g.params = Params(self)
        return g.params

    # gets the winning team id for a coin flip, returns -1 if no coin flip yet
    # entered
    def getCoinFlip(self, tid_a, tid_b):
        params = self.getParams()
        # app.logger.debug("looking for a coin flip between %s and %s " % (tid_a,
        # tid_b))

        if params.getParam('coin_flips'):
            flips = split(params.getParam('coin_flips'), ";")
            for i in flips:
                (a, b, coin) = split(i, ",")
                a = int(a)
                b = int(b)
                if (tid_a == a or tid_a == b) and (tid_b == a or tid_b == b):
                    # app.logger.debug("returning a coin %s" % coin)
                    return int(coin)
        else:
            return -1

    def getTies(self):
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

    # creates flash for tie only if the round robin for the division is
    # finished
    def addTie(self, tid_a, tid_b):
        div_a = self.getDivision(tid_a)
        div_b = self.getDivision(tid_b)

        # not quite sure how this would happen, but protecting myself
        if div_a != div_b:
            return 0

        db = self.db

        cur = db.execute(
            "SELECT DISTINCT p.pod FROM pods p WHERE (team_id=? OR team_id=?) AND tid=?", (tid_a, tid_b, self.tid))
        rows = cur.fetchall()

        if len(rows) > 0:
            for row in rows:
                pod = row['pod']
                if not self.endRoundRobin(None, pod):
                    return 1
        else:
            pod = None
            if not self.endRoundRobin(div_a, None):
                return 1
            # code to add divisional check goes here

        # flash("There is a tie in the standings between %s & %s!" %  (teams[0],
        # teams[1]))

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

    # true false function for determining if round robin play has been
    # completed
    def endRoundRobin(self, division=None, pod=None):
        # app.logger.debug("Running endRoundRobin - %s or %s" % (division, pod))

        db = self.db
        if (division == None and pod == None):
            cur = db.execute(
                'SELECT count(*) as games FROM games WHERE type="RR" AND tid=?', self.tid)
        elif (division == None and pod):
            cur = db.execute(
                'SELECT count(*) as games FROM games WHERE type="RR" AND pod=? AND tid=?', (pod, self.tid))
        elif division:
            cur = db.execute('SELECT count(*) as games FROM games WHERE type="RR" AND division LIKE ? AND tid=?',
                             (division, self.tid))
        else:
            cur = db.execute(
                'SELECT count(*) as games FROM games WHERE type="RR" AND division LIKE ? POD=? AND tid=?', (division, pod, self.tid))

        row = cur.fetchone()

        rr_games = row['games']

        if (division == None and pod == None):
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.tid=s.tid AND s.tid=?',
                             self.tid)
        elif (division == None and pod):
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.pod=? AND g.tid=s.tid AND g.tid=?',
                             (pod, self.tid))
        elif division:
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" AND g.tid=s.tid AND g.division=? AND s.tid=?',
                             (division, self.tid))
        else:
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type="RR" \
    			AND division LIKE ? and pod=? AND g.tid=s.tid AND s.tid=?', (division, pod, self.tid))

        row = cur.fetchone()
        games_played = row['count']

        # app.logger.debug("%s-%s: RR Games = %s and we've played %s games" %
        # (division, pod, rr_games, games_played))

        # first check if all games have been played
        if (games_played >= rr_games):
            # app.logger.debug("endRoundRobin returing true")
            return True
        else:
            # app.logger.debug("endRoundRobin returing false")
            return False

    # quick funciton used to convert divisions to an integer used in rankings
    # makes an A team above a B team
    def divToInt(self, div):
        div_list = self.getDivisions()
        if div in div_list:
            return div_list.index(div)
        else:
            return 0

    def podToInt(self, pod):
        pod_list = self.getPods()
        if pod in pod_list:
            return pod_list.index(pod)
        else:
            return 0

    # simple function for calculating the win/loss ration between two teams
    # returns number of wins team_a has over team_b, negative number if more
    # losses
    def netWins(self, team_a, team_b, pod=None):
        db = self.db
        net_wins = 0

        tid_a = team_a.team_id
        tid_b = team_b.team_id

        if team_a.pod != team_b.pod:
            app.logger.debug(
                "Comparing two teams that aren't in the same pod, that's ok")

        #app.logger.debug("Checking %s v %s in pod %s" % (team_a.name, team_b.name, pod))

        if pod:
            cur = db.execute('SELECT s.gid, s.black_tid, s.white_tid, s.score_w, s.score_b, s.forfeit FROM scores s, games g \
    						WHERE s.gid = g.gid AND s.tid=g.tid AND ((s.black_tid=? AND s.white_tid=?)\
    						OR (s.black_tid=? AND s.white_tid=?)) AND g.type="RR" AND g.pod=? AND g.tid=?',
                             (tid_a, tid_b, tid_b, tid_a, pod, self.tid))
        else:
            cur = db.execute('SELECT s.gid, s.black_tid, s.white_tid, s.score_w, s.score_b, s.forfeit FROM scores s, games g \
    						WHERE s.gid = g.gid AND s.tid=g.tid AND ((s.black_tid=? AND s.white_tid=?)\
    						OR (s.black_tid=? AND s.white_tid=?)) AND g.type="RR" AND g.tid=?',
                             (tid_a, tid_b, tid_b, tid_a, self.tid))

        games = cur.fetchall()

        for game in games:
            black_tid = game['black_tid']
            white_tid = game['white_tid']
            score_b = game['score_b']
            score_w = game['score_w']
            forfeit = game['forfeit']
            #app.logger.debug("%s - %s v %s - %s to %s" % (game['gid'], black_tid, white_tid, score_b, score_w))

            if forfeit:
                if forfeit == "w":
                    if white.tid == tid_a:
                        net_wins -= 1
                    elif black.tid == tid_a:
                        net_wins += 1
                if forfeit == "b":
                    if black.tid == tid_a:
                        net_wins -= 1
                    elif white_tid == tid_a:
                        net_wins += 1
            elif (score_b > score_w):
                if (black_tid == tid_a):
                    net_wins += 1
                elif (black_tid == tid_b):
                    net_wins -= 1
            elif (score_w > score_b):
                if (white_tid == tid_a):
                    net_wins += 1
                elif (white_tid == tid_b):
                    net_wins -= 1

        #app.logger.debug("net wins: %s" % net_wins)
        return net_wins

    # function used for sorting Stats class for standings
    # Compares on most points, head to head, most wins, least losses, goals allowed
    #
    # ONLY USE WHEN COMPARING TEAMS DIRECTLY, DON'T USE IN SORT
    #
    def cmpTeams(self, team_b, team_a, pod=None):
        #app.logger.debug("in cmpTeams between %s and %s for pod %s" % (team_a, team_b, pod))
        if (team_a.division.lower() != team_b.division.lower()):
            #app.logger.debug("not same division")
            return self.divToInt(team_a.division) - self.divToInt(team_b.division)
        elif (team_a.pod != team_b.pod):
            #app.logger.debug("not same pod")
            return self.podToInt(team_a.pod) - self.podToInt(team_b.pod)
        elif (team_a.points != team_b.points):
            #app.logger.debug("breaking on points")
            return team_a.points - team_b.points
        elif (self.netWins(team_a, team_b, pod) != self.netWins(team_b, team_a, pod)):
            #app.logger.debug("breaking on netwins")
            return self.netWins(team_a, team_b, pod) - self.netWins(team_b, team_a, pod)
        elif (team_a.wins != team_b.wins):
            #app.logger.debug("breaking on wins")
            return team_a.wins - team_b.wins
        elif (team_a.losses != team_b.losses):
            #app.logger.debug("breaking on losses")
            return team_b.losses - team_a.losses
        elif (team_a.goals_allowed != team_b.goals_allowed):
            #app.logger.debug("breaking on gloas allowed")
            return team_b.goals_allowed - team_a.goals_allowed
        else:
            #app.logger.debug("straight up tie")
            flip = self.getCoinFlip(team_a.team_id, team_b.team_id)
            if flip == team_a.team_id:
                return 1
            elif flip == team_b.team_id:
                return -1
            else:
                self.addTie(team_a.team_id, team_b.team_id)
                return 0

    # Compares teams w/o head-to-head, needed for sorting sets of three or
    # more teams
    def cmpTeamsSort(self, team_b, team_a):
        if (team_a.division.lower() != team_b.division.lower()):
            return self.divToInt(team_a.division) - self.divToInt(team_b.division)
        elif (team_a.wins != team_b.wins):
            return team_a.wins - team_b.wins
        elif (team_a.losses != team_b.losses):
            return team_b.losses - team_a.losses
        elif (team_a.goals_allowed != team_b.goals_allowed):
            return team_b.goals_allowed - team_a.goals_allowed
        else:
            return 0

    # runs a team comparison on two of the team elements
    def cmpRankSort(self, rank_b, rank_a):
        return self.cmpTeamsSort(rank_b.team, rank_a.team)

    def checkForTies(self, standings):
        x = 0
        while x < len(standings) - 1:
            if self.cmpTeams(standings[x].team, standings[x + 1].team) == 0:
                return True
            x = x + 1

        x = 0
        last = 0
        while x < len(standings) - 1:
            if self.cmpTeamsSort(standings[x].team, standings[x + 1].team) == 0:
                if last == 1:
                    flash("You need a three sided die, give up and go home")
                    return True
                else:
                    last = 1
            else:
                last = 0
            x = x + 1

        return False

    # Sorts a list of Stats objects, one per team.
    # Returns ordered list of Ranging objects, ranking object has team stat objects
    # along with the division, pod and place
    # Wherever place is displayed/used it would reference the place field,
    # don't use the index for place
    def sortStandings(self, team_stats, pod=None):
        if not pod:
            app.logger.debug("sorting standings without pod")
        else:
            app.logger.debug("sorting for pod %s" % pod)

        for team in team_stats:
            # team = team_stats[place]
            if team.pod != pod:
                app.logger.debug("I have standings that aren't for my pod")

        # pre-sort required for three-way ties
        ordered = sorted(team_stats, cmp=self.cmpTeamsSort)
        ordered = sorted(ordered, cmp=self.cmpTeams)

        # first go through the list and assign a place to everybody based on only points
        # doesn't settle tie breakers yet
        i = 1
        standings = []
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

        divisions = self.getDivisions()
        pods = self.getPodsActive()
        is_pods = False
        if pods:
            divisions = pods
            is_pods = True


        # use list Comprehensions to find all the tied teams, have to iterate over divisions
        # to keep 1st in the A from being confused with 1st in the B
        for div in divisions:
            if is_pods:
                #app.logger.debug("-- working on pod %s" % div)
                div_standings = [x for x in standings if x.team.pod == div]
            else:
                div_standings = [
                    x for x in standings if x.team.division == div]

            places = len(div_standings)
            place = 1
            while place <= places:
                place_teams = [
                    x for x in div_standings if x.place == place]
                count = len(place_teams)
                # app.logger.debug("place_teams =  %s" % place_teams)
                # nobody is in this place, probably do to ties, move on
                if count == 0:
                    place += 1
                elif count == 1:  # one team alone, nothing to do
                    place += 1
                # head to head tie, break based on head-to-head first
                elif count == 2:
                    place += 1
                    a = place_teams[0].team
                    b = place_teams[1].team
                    if self.cmpTeams(a, b, div) < 0:
                        place_teams[1].place += 1
                    elif self.cmpTeams(a, b, div) > 0:
                        place_teams[0].place += 1
                    else:
                        # flip = getCoinFlip(a.team_id, b.team_id)
                        # if flip == a.team_id:
                        #	place_teams[1] += 1
                        # if flip == b.team_id:
                        #	place_Teams[0] += 1
                        continue
                elif count == 3:
                    app.logger.debug("working a three-way in %s" % div)

                    # unlikely, but if one team beat both others, then win
                    if self.netWins(place_teams[0].team, place_teams[1].team) > 0 and self.netWins(place_teams[0].team, place_teams[2].team) > 0:
                        place_teams[1].place += 1
                        place_teams[2].place += 1
                        continue
                    elif self.netWins(place_teams[1].team, place_teams[0].team) > 0 and self.netWins(place_teams[1].team, place_teams[2].team) > 0:
                        place_teams[0].place += 1
                        place_teams[2].place += 1
                        continue
                    elif self.netWins(place_teams[2].team, place_teams[0].team) > 0 and self.netWins(place_teams[2].team, place_teams[1].team) > 0:
                        place_teams[0].place += 1
                        place_teams[1].place += 1
                        continue

                    # Check if all the tie breakers are ties
                    if place_teams[1:] == place_teams[:-1]:
                        app.logger.debug("three way tie all equal in %s" % div)
                        place += 1
                        # continue
                    else:
                        # sort teams based on rules w/o head-to-head
                        place_teams = sorted(place_teams, cmp=self.cmpRankSort)

                        last = place_teams[-1].team
                        second_last = place_teams[-2].team
                        # don't use head-to-head cmp even though its two because its the 3-way
                        # tie braker
                        result = self.cmpTeamsSort(last, second_last)

                        if result == 0:
                            place_teams[-1].place += 1
                            place_teams[-2].place += 1
                        elif result < 0:
                            place_teams[-2].place += 2
                        else:
                            place_teams[-1].place += 2

                # more than three teams in place
                else:
                    app.logger.debug("%s teams tied" % count)

                    least_goals = place_teams[0].team.goals_allowed
                    rest = [x for x in place_teams if x.team.goals_allowed > least_goals]
                    if len(rest) > 0:
                        for r in rest:
                            r.place += 1
                    else:
                        place += 1

        # resort to make sure in order by place and division
        tmp = sorted(standings, key=lambda x: x.place)
        return sorted(tmp, key=lambda x: x.div)

    # master function for calculating standings of all teams
    # shouldn't be called directly, use getStandings() to avoid
    # recalculating multiple times per load
    def calcStandings(self, pod=None):
        # app.logger.debug("calculating standings, pod = %s" , (pod,))

        standings = []

        db = self.db
        if (pod == None):
            cur = db.execute(
                'SELECT team_id FROM teams WHERE tid=?', (self.tid,))
        else:
            cur = db.execute(
                'SELECT team_id FROM pods WHERE tid=? AND pod=?', (self.tid, pod))

        team_ids = cur.fetchall()

        for team in team_ids:
            team_id = team['team_id']
            standings.append(Stats(self, team_id, pod))

        return self.sortStandings(standings, pod)

    # wrapper function for standings, use to ger dictionary of standings
    # dictionary indexed by rank and contains all the team information in Stat
    # class
    def getStandings(self, div=None, pod=None):
        # if not hasattr(g, 'standings'):
        #	g.standings = calcStandings()

        # filter for pod and div
        # if pod:
        #	standings = [x for x in g.standings if x.pod == pod]
        # elif div:
        #	standings = [x for x in g.standings if x.div == div]
        # else:
        #	standings = g.standings

        if pod:
            standings = self.calcStandings(pod)
        elif div:
            standings = self.calcStandings()
            standings = [x for x in standings if x.div == div]
        else:
            standings = self.calcStandings()

        return standings

    def getTies(self):
    	if not hasattr(g, 'ties'):
    		return None

    	ties = g.ties
    	seen = set()
    	list = [x for x in ties if x not in seen and not seen.add(x)]

    	ties = []
    	for tie in list:
    		id_a = tie[0]
    		id_b = tie[1]
    		team_a = self.getTeam(id_a)
    		team_b = self.getTeam(id_b)

    		ties.append({'id_a':id_a, 'id_b':id_b,'team_a':team_a,'team_b':team_b})

    	return ties

    def genTieFlashes(self):
    	if not hasattr(g, 'ties'):
    		return 0

    	ties = g.ties

    	seen = set()
    	list = [x for x in ties if x not in seen and not seen.add(x)]

    	for tie in list:
    		name_a = self.getTeam(tie[0])
    		name_b = self.getTeam(tie[1])
    		flash("There is a tie in the standings between %s & %s" % (name_a, name_b))

    	flash("A coin flip is required, please see tournament director or head ref")
    	return 0

    def getTieFlashes(self):
        if not hasattr(g, 'ties'):
            return None

        ties = g.ties
        seen = set()
        t_list = [x for x in ties if x not in seen and not seen.add(x)]

        messages = []
        for tie in t_list:
            name_a = self.getTeam(tie[0])
            name_b = self.getTeam(tie[1])
            messages.append("There is a tie in the standings between %s & %s" % (name_a, name_b))

        return messages

    ##########################################################################
    # Admin functions
    ##########################################################################

    # Takes in user object and returns true if the user is authorized to manage
    # the tournament
    def isAuthorized(self, user):
        # first check if the tournament is active, just a little safety mech
        if not self.is_active:
            return False

        app.logger.debug("checking on admin")
        # first check if they are a site_admin or admin, if yes, just return true
        if user.site_admin or user.admin:
            return True

        app.logger.debug("guess user isn't a super admin")
        authorized_ids = []

        db = self.db
        cur = db.execute("SELECT admin_ids FROM tournaments WHERE tid=?", (self.tid,))
        row = cur.fetchone()
        if row['admin_ids']:
            id_string = row['admin_ids']
        else:
            return False

        authorized_ids = id_string.split(",")

        if user.get_id() in authorized_ids:
            return True
        else:
            return False


    # takes in dictionary from POST and updates/creates score for single game
    # does not provide authorization check, that needs to be done pre-call
    def updateGame(self, game):
        db = self.db
        gid = game['gid']
        score_b = game['score_b']
        score_w = game['score_w']
        black_tid = game['black_tid']
        white_tid = game['white_tid']
        pod = game['pod']

        forfeit_w = game['forfeit_w']
        forfeit_b = game['forfeit_b']

        if forfeit_b and forfeit_w:
            return -2
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

        if not (white_tid > 0 and black_tid > 0):
            return -3

        cur = db.execute("INSERT OR IGNORE INTO scores (black_tid, white_tid, score_b, score_w,tid, gid, pod, forfeit) VALUES(?,?,?,?,?,?,?,?)",
                         (black_tid, white_tid, score_w, score_b, self.tid, gid, pod, forfeit))
        db.commit()

        cur = db.execute("UPDATE scores SET score_b=?,score_w=?, forfeit=? WHERE tid=? AND gid=?",
                         (score_b, score_w, forfeit, self.tid, gid))
        db.commit()

        # self.popSeededPods()

        return 1

    def updateConfig(self, form):
    	if not "config_id" in form:
    		flash("You didn't give me an ID, go away")
    		return 0

    	config_id = form.get('config_id')
    	if config_id == "site_active":
    		switch = form.get('active_toggle')
    		message = form.get('message')
    		if (switch == "on"):
    			self.updateSiteStatus(False, message)
    		else:
    			self.updateSiteStatus(True)
    	elif config_id == "coin_flip":
    		id_a = form.get('id_a')
    		id_b = form.get('id_b')
    		winner = form.get('winner')

    		self.addCoinFlip(id_a, id_b, winner)
    	elif config_id == "site_message":
    		switch = form.get('active_toggle')
    		message = form.get('message')
    		if (switch == "on"):
    			self.updateSiteMessage(message)
    		else:
    			self.updateSiteMessage(None)
    	else:
    		flash("I don't understand that config option, nothing changed")

    	return 0

    # gets the winning team id for a coin flip, returns -1 if no coin flip yet entered
    def getCoinFlip(self, tid_a, tid_b):
        params = self.getParams()
        #app.logger.debug("looking for a coin flip between %s and %s " % (tid_a, tid_b))

        if params.getParam('coin_flips'):
            flips =  split(params.getParam('coin_flips'),";")
        else:
            return -1

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
    def addCoinFlip(self, tid_a, tid_b, winner):
    	val = "%s,%s,%s" % (tid_a, tid_b, winner)

    	params = self.getParams()

        if params.getParam('coin_flips'):
    		val = "%s;%s" %(params.getParam('coin_flips'), val)
    		params.updateParam("coin_flips", val)
    	else:
    		params.addParam("coin_flips", val)

    	#popSeededPods()

    	return 0

    def updateSiteStatus(self, active, message=None):
    	# delete first incase message is being updated
        params = self.getParams()

        params.clearParam("site_disabled")

    	if not active:
    		if message == "":
    			message = "Site disabled temporarily, please check back later."

    		params.addParam("site_disabled", message)

    	return 0

    def getDisableMessage(self):
        params = self.getParams()

        disable_message = params.getParam("site_disabled")

        return disable_message

    def updateSiteMessage(self, message):
        params = self.getParams()

    	if message:
    		params.clearParam("site_message")
    		params.addParam("site_message", message)
    	else:
    		params.clearParam("site_message")

    	return 0

    def getSiteMessage(self):
        params = self.getParams()

        return params.getParam("site_message")

    ## Functions for handling tournaments with partial roundrobins

    # redraws team for a division with POST from /admin/redraw
    def redraw_teams(self, div, redraws):
    	app.logger.debug("Redrawing teams for div %s with %s", (div, redraws))

    	# everything looks good, cross your fingers and go
    	for draw in redraws:
    		self.redraw_execute(div, draw['redraw_id'], draw['team_id'])

    	# once the redraw is complete, we need to change the tyoe on the played
    	# head to head games to E so they aren't counted towards standings
    	#
    	### SHOULD ADD CHECK THAT THIS IS WHAT THE TOURNAMENTS WANTS ###
    	self.trimRoundRobin(div)

    	flash("Redraw Complete!")
    	return 0

    # return list of redraws needed
    def getRedraw(self, div):
    	db = self.db
    	ids = []

    	cur = db.execute('SELECT white, black FROM games WHERE (white LIKE "R%" or black LIKE "R%") AND division=? AND tid=?', (div,self.tid))
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
    def redraw_execute(self, div, redraw_id, team_id):
    	app.logger.debug("Execute redraw for division: %s - R%s is now T%s" % (div, redraw_id, team_id))

    	redraw_string = "R%s%s" % (div, redraw_id)
    	team_string = "T%s" % (team_id)

    	if not self.getTeam(team_id):
    		app.logger.debug("Team ID doesn't exist, somethings really broke")
    		return 1

    	db = self.db
    	cur = db.execute("UPDATE games SET white=? WHERE white=? AND tid=?" , (team_string, redraw_string, self.tid ))
    	db.commit()
    	cur = db.execute("UPDATE games SET black=? WHERE black=? AND tid=?" , (team_string, redraw_string, self.tid ))
    	db.commit()

    	return 0

    # function trims a round-robin down to only one head-to-head game per team_string
    # required for partial round-robin tournaments
    # team redraw must already be comleted
    def trimRoundRobin(self, div):
    	db = self.db

    	team_list = self.getTeams(div)

    	while len(team_list) > 0:
    		cur_team = team_list.pop()
    		for opponent in team_list:
    			a="T%s" % cur_team['team_id']
    			b="T%s" % opponent['team_id']
    			cur = db.execute("SELECT gid FROM games WHERE ((white=? AND black=?) or (white=? and black=?))\
    				AND division=? AND type='RR' AND tid=? ORDER BY gid", (a,b,b,a,div,self.tid))
    			games = cur.fetchall()

    			if len(games) > 2:
    				app.logger.debug("Found 3+ h2h between %s and %s, doing nothing" % (a,b))
    			if len(games) == 2:
    				gid = games[0]['gid']
    				app.logger.debug("Found 2 h2h games between %s and %s, trimming game %s" % (a,b, gid))
    				cur = db.execute("UPDATE games SET type='E' WHERE gid=? and tid=?", (gid, self.tid))
    				db.commit()

    	return 0
