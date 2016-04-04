from datetime import datetime
import re

class Game(object):

    def __init__(self, tournament, gid, day, start_datetime, pool, black, white, game_type, division, pod, description):
        self.tournament = tournament
        self.gid = gid
        self.day = day
        self.start_datetime = datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S')
        self.start_time = datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S').strftime('%I:%M %p')
        self.pool = pool
        self.game_type = game_type
        self.division = division
        self.pod = pod
        self.description = description

        # functionality existed before refactor, maybe add it back in later
        self.podColor = None

        # pull the record from the scores table, if it exists use that data to fill in the game
        db = tournament.db
        cur = db.execute('SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?', (self.gid, tournament.tid))
        score = cur.fetchone()

        self.style_b = ""
        self.style_w = ""
        self.note_b = ""
        self.note_w = ""
        self.forfeit = None

        if score:
            self.black_tid = score['black_tid']
            self.white_tid = score['white_tid']

            self.black = tournament.getTeam(score['black_tid'])
            self.white = tournament.getTeam(score['white_tid'])

            self.score_b = score['score_b']
            self.score_w = score['score_w']
            if score['forfeit']:
                self.forfeit = score['forfeit']
                if score['forfeit'] == "b":
                    self.note_b = "Forfeit"
                else:
                    self.note_w = "Forfeit"
        else:
            self.score_b = "--"
            self.score_w = "--"
            (self.black_tid, self.black, self.style_b) = self.parseGame(black)
            (self.white_tid, self.white, self.style_w) = self.parseGame(white)

    def __repr__(self):
        return "{}: {} {} - {} vs {}".format(self.gid, self.day, self.start_time, self.black, self.white)

    def serialize(self):
	return {
        'tid':self.tournament.tid,
		'gid':self.gid,
		'day':self.day,
        'pool':self.pool,
		'start_time':self.start_datetime.isoformat(),
		'black':self.black,
        'black_id':self.black_tid,
        'note_b':self.note_b,
		'white':self.white,
        'white_id':self.white_tid,
        'note_w':self.note_w,
        'score_b': self.score_b,
        'score_w': self.score_w,
        'forfeit': self.forfeit
	}

    # loops through all games and creates expanded dictionary of games
    # expands database short hand into human readable form
    def expandGames(self, games):
    	expanded = []

    	return expanded

    # Converts short hand notation for game schedule into human readable names
    # Team IDs, seeding games and "winner/loser of" games
    def parseGame(self, game):
    	style = ""
    	team_id = -1
        t = self.tournament

    	# Team notation
    	match = re.search( '^T(\d+)$', game)
    	if match:
    		team_id = match.group(1)
    		game = self.tournament.getTeam(team_id)

    	# Redraw IDs
    	match = re.search( '^R(\w)(\d+)$', game)
    	if match:
    		div = match.group(1)
    		num = match.group(2)

    		game = "Redraw " + div + num
    		style="soft"

    	# seeded pods RR games
        # only for nationals 2014, what a mess
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

    		if group in t.getPods():
    			team_id = t.getSeed( seed, None, group)
    		elif group in t.getDivisions():
    			team_id = t.getSeed( seed, group, None)
    		else:
    			team_id = -1

    		if ( team_id < 0 ):
    			game = "%s Seed %s" % (group, seed)
    			style="soft"
    		else:
    			team = t.getTeam(team_id)
    			if group:
    				game = "%s (%s-%s)" % (team, group, seed)

    	# Winner of
    	match = re.search( '^W(\d+)$', game)
    	if match:
    		gid = match.group(1)
    		team_id = t.getWinner(gid)
    		if (team_id == -1):
    			game = "Winner of " + gid
    			style="soft"
    		elif (team_id == -2):
    			game = "TIE IN GAME %s!!" % gid
    		else:
    			team = t.getTeam(team_id)
    			game = team + " (W" + gid + ")"

    	# Loser of
    	match = re.search( '^L(\d+)$', game)
    	if match:
    		gid = match.group(1)
    		team_id = t.getLoser(gid)
    		if (team_id == -1):
    			game = "Loser of " + gid
    			style="soft"
    		elif (team_id == -2):
    			game = "TIE IN GAME %s!!" % gid
    		else:
    			team = t.getTeam(team_id)
    			game = team + " (L" + gid + ")"

    	# TBD Place Holder
    	match = re.search('^TBD.*', game)
    	if match:
    		style="soft"

    	team_id = int(team_id)

    	return (team_id,game,style)
