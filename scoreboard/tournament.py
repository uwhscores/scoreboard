from datetime import datetime
from flask import current_app as app
from flask import flash
from flask import g as flask_g
import json
import os
import re

from scoreboard import functions, audit_logger
from scoreboard.game import Game
from scoreboard.models import Stats, Ranking, Params
from scoreboard.exceptions import UpdateError


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
        self.context = flask_g

        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        # human readable date range string, "Month ##-##, Year"
        self.date_string = "%s-%s" % (
            self.start_date.strftime("%B %d"), self.end_date.strftime("%d, %Y"))

        days = []
        # TODO: Going to need an update function when building tournament ahead of games
        # cur = db.execute("SELECT DISTINCT day from games WHERE tid=?", (tid,))
        # for r in cur.fetchall():
        #     days.append(r['day'])
        cur = db.execute("SELECT DISTINCT start_time FROM games WHERE tid=?", (tid,))
        day_names = ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]
        for r in cur.fetchall():
            # extract day of the month 2018-07-25 17:40:00
            dt = datetime.strptime(r['start_time'], '%Y-%m-%d %H:%M:%S')
            date_string = "%s-%s" % (day_names[dt.weekday()], functions.ordinalize(dt.day))
            if date_string not in days:
                days.append(date_string)

        self.days = days

        params = self.getParams()
        if params.getParam('points_win'):
            self.POINTS_WIN = int(params.getParam('points_win'))
        else:
            self.POINTS_WIN = 2

        if params.getParam('points_forfeit'):
            self.POINTS_FORFEIT = int(params.getParam('points_forfeit'))
        else:
            self.POINTS_FORFEIT = 2

        self.use_24hour = False
        if params.getParam('use_24hour') == 1:
            self.use_24hour = True

        self.sm_logo = None
        if os.path.isfile(os.path.join("scoreboard/static/flags", self.short_name, "sm_logo.png")):
            self.sm_logo = os.path.join("static/flags", self.short_name, "sm_logo.png")

        self.banner = None
        self.banner_sm = None
        if os.path.isfile(os.path.join("scoreboard/static/flags", self.short_name, "banner_sm.png")):
            self.banner_sm = os.path.join("static/flags", self.short_name, "banner_sm.png")
        if os.path.isfile(os.path.join("scoreboard/static/flags", self.short_name, "banner.png")):
            self.banner = os.path.join("static/flags", self.short_name, "banner.png")

    def __repr__(self):
        """ String reper only really used for log and debug """
        return "{} - {} - {}".format(self.name, self.start_date, self.location.encode('utf8'))

    def __cmp__(self, other):
        """ sort compare based on start_date """
        delta = other.start_date - self.start_date
        return delta.days

    def __lt__(self, other):
        """ sort compare based on start_date """
        return other.start_date < self.start_date

    def serialize(self, verbose=False):
        if verbose:
            divisions = self.getDivisions()
            pools = self.getPools()
            pods = self.getPodsActive()
            return {
                'tid': self.tid,
                'name': self.name,
                'short_name': self.short_name,
                'start_date': self.start_date.isoformat(),
                'end_date': self.end_date.isoformat(),
                'location': self.location,
                'is_active': self.is_active,
                'divisions': divisions,
                'pods': pods,
                'pools': pools
            }
        else:
            return {
                'tid': self.tid,
                'name': self.name,
                'short_name': self.short_name,
                'start_date': self.start_date.isoformat(),
                'end_date': self.end_date.isoformat(),
                'location': self.location,
                'is_active': self.is_active
            }

    def commitToDB(self):
        """ Commit tournament details to the databse either insert or update """
        db = self.db

        cur = db.execute("SELECT tid, name FROM TOURNAMENTS WHERE tid=?", (self.tid,))
        row = cur.fetchone()

        start_date_str = datetime.strftime(self.start_date, "%Y-%m-%d")
        end_date_str = datetime.strftime(self.end_date, "%Y-%m-%d")

        if row:
            db.execute("UPDATE TOURNAMENTS SET name=?, short_name=?, start_date=?, end_date=?, location=?, active=? WHERE tid=?",
                       (self.name, self.short_name, start_date_str, end_date_str, self.location, self.is_active, self.tid))
        else:
            db.execute("INSERT INTO TOURNAMENTS (tid, name, short_name, start_date, end_date, location, active) VALUES (?,?,?,?,?,?,?)",
                       (self.tid, self.name, self.short_name, start_date_str, end_date_str, self.location, self.is_active))
        db.commit()

        return True

    def getTeam(self, team_id):
        """ return team name from ID """
        db = self.db
        cur = db.execute(
            'SELECT name FROM teams WHERE team_id=? AND tid=?', (team_id, self.tid))
        team = cur.fetchone()

        if team:
            return team['name']
        else:
            return None

    def getTeamInfo(self, team_id):
        """ return dictionary of team info from ID """
        try:
            team_id = int(team_id)
        except ValueError:
            return None

        db = self.db
        cur = db.execute('SELECT name, short_name, division, flag_file FROM teams WHERE team_id=? and tid=?', (team_id, self.tid))
        team = cur.fetchone()

        if not team:
            return None

        team_info = {
                "name": team['name'],
                "team_id": team_id,
                "short_name": team['short_name'],
                "division": team['division'],
                "flag_url": team['flag_file'],
                # TODO: sort rosters and coaches since jinja isn't sorting
                "roster": self.getTeamRoster(team_id),
                "coaches": self.getTeamCoaches(team_id)
            }

        return team_info

    def getTeamFlag(self, team_id):
        """ returns dictionary with flag url and thumbnail url """
        flag_url = None

        try:
            team_id = int(team_id)
        except (ValueError, TypeError):
            return None

        db = self.db
        cur = db.execute('SELECT flag_file FROM teams WHERE flag_file IS NOT NULL AND team_id=? AND tid=?', (team_id, self.tid))
        row = cur.fetchone()
        if row:
            flag_url = {}
            flag_url['full_res'] = row['flag_file']
            flag_url['thumb'] = row['flag_file']

        return flag_url

    def getTeamRoster(self, team_id):
        """ return a list of dictionaries of the players for the team """
        roster = None

        db = self.db
        cur = db.execute("SELECT p.player_id, p.display_name, r.cap_number FROM players p, rosters r WHERE r.player_id = p.player_id AND r.is_coach=0 AND r.team_id = ? AND r.tid=?",
                         (team_id, self.tid))

        roster_table = cur.fetchall()

        if len(roster_table) > 0:
            roster = []
            for row in roster_table:
                roster.append({"name": row['display_name'], "number": row['cap_number'], "player_id": row['player_id']})

        return roster

    def getTeamCoaches(self, team_id):
        """ return a list of dictionaries of the coaches for the team """
        coaches = None

        db = self.db
        cur = db.execute("SELECT p.player_id, p.display_name, r.coach_title FROM players p, rosters r WHERE r.player_id=p.player_id AND r.is_coach=1\
                         AND r.team_id=? AND r.tid=?", (team_id, self.tid))

        coaches_table = cur.fetchall()

        if len(coaches_table) > 0:
            coaches = []
            for row in coaches_table:
                coaches.append({"name": row['display_name'], "title": row['coach_title'], "player_id": row['player_id']})

        return coaches

    def getTeams(self, div=None, pod=None):
        """ return dictionary of all teams indexed by ID """
        db = self.db
        if (div is None and pod is None):
            cur = db.execute(
                "SELECT team_id, name, division, flag_file FROM teams WHERE tid=? ORDER BY name", (self.tid,))
        elif (pod is None):
            cur = db.execute("SELECT team_id, name, division, flag_file FROM teams WHERE division=? AND tid=? ORDER BY name",
                             (div, self.tid))
        elif (div is None):
            cur = db.execute("SELECT t.team_id, t.name, t.division, t.flag_file FROM teams t, pods p WHERE t.team_id=p.team_id AND p.pod=? AND t.tid=p.tid AND t.tid=?",
                             (pod, self.tid))

        teams = []
        # TODO: standardize flag url format
        for team in cur.fetchall():
            teams.append({'team_id': team['team_id'], 'name': team['name'], 'division': team['division'], 'flag_url': team['flag_file']})

        return teams

    def getTeamsLike(self, group):
        """ searches for teams given a name, like "USA" to get "USA Mens" and "USA Womens"
        return list of team IDs """
        db = self.db

        search_string = "%%%s%%" % group
        cur = db.execute("SELECT team_id FROM teams WHERE name LIKE ? AND tid=? COLLATE NOCASE", (search_string, self.tid))

        team_ids = []
        for r in cur.fetchall():
            team_ids.append(r['team_id'])

        if len(team_ids) > 0:
            return team_ids
        else:
            return None

    def getGames(self, division=None, pod=None, offset=None):
        """ Get all games, allows for filter by division or pod and offset which was used for legacy TV display
        division and pod should be short names as would appear in DB

        returns list of games as objects
        """
        if offset:
            cur = self.db.execute("SELECT gid, day, start_time, pool, black, white, division, pod, type, description FROM games \
                                   WHERE tid=? ORDER BY start_time LIMIT ?,45", (self.tid, offset))
        # whole schedule
        elif not (division or pod):
            cur = self.db.execute("SELECT gid, day, start_time, pool, black, white, pod, division, type, description FROM games \
                                   WHERE tid=? ORDER BY start_time", (self.tid,))
        # division schedule
        elif not pod:
            cur = self.db.execute("SELECT gid, day, start_time, pool, black, white, pod, division, type, description FROM games \
                                   WHERE (division LIKE ? or type='CO') AND tid=? ORDER BY start_time", (division, self.tid))
        # pod schedule
        elif not devision:
            cur = self.db.execute("SELECT gid, day, start_time, pool, black, white, division, pod, type, description FROM games \
                                   WHERE (pod like ? or type='CO') AND tid=? ORDER BY start_time", (pod, self.tid))

        games = []
        for game in cur.fetchall():
            games.append(Game(self, game['gid'], game['day'], game['start_time'], game['pool'], game['black'], game['white'],
                              game['type'], game['division'], game['pod'], game['description']))

        return games

    def getTeamGames(self, team_id):
        """ get games filtered by team id
        returns list of dictionary of games
        """
        db = self.db

        cur = db.execute('SELECT gid, day, start_time, pool, black, white, division, pod, type, description \
                        FROM games WHERE tid=? ORDER BY start_time', (self.tid,))
        # allGames = self.expandGames(cur.fetchall())
        team_games = cur.fetchall()

        games = []
        for game in team_games:
            game = Game(self, game['gid'], game['day'], game['start_time'], game['pool'], game['black'], game['white'],
                        game['type'], game['division'], game['pod'], game['description'])
            if game.black_tid == team_id or game.white_tid == team_id:
                # style hint used in template to accent team's color
                if game.black_tid == team_id:
                    game.style_b = "strong"
                elif game.white_tid == team_id:
                    game.style_w = "strong"

                games.append(game)

        return games

    def getGame(self, gid):
        """ Get single game by game ID, returns game object """
        db = self.db
        cur = db.execute('SELECT gid, day, start_time, pool, black, white, division, pod, type, description \
                FROM games WHERE gid=? AND tid=? ', (gid, self.tid))
        row = cur.fetchone()

        if row:
            game = Game(self, row['gid'], row['day'], row['start_time'], row['pool'], row['black'], row['white'],
                        row['type'], row['division'], row['pod'], row['description'])
            return game
        else:
            return None

    def getWinner(self, game_id):
        """ get team ID of winner by game ID
        returns negative number if no winner """
        db = self.db
        cur = db.execute("SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?", (game_id, self.tid))
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
        """ get team ID of loser by game ID
        returns negative number if no loser """
        db = self.db
        cur = db.execute("SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?", (game_id, self.tid))
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

    def getDivisions(self):
        """ list of divisions by ID as appears in database """
        db = self.db
        cur = db.execute(
            "SELECT DISTINCT division FROM games WHERE tid=? ORDER BY division", (self.tid,))

        divisions = []
        for r in cur.fetchall():
            if r['division'] != "":
                divisions.append(r['division'])

        return divisions

    def getDivisionNames(self):
        """ dictionary of divisions indexed by ID with human readable name """
        divs = self.getDivisions()

        div_names = []
        for div in divs:
            name = self.expandGroupAbbr(div)
            if not name:
                name = div
            div_names.append({'id': div, 'name': name})

        return div_names

    def getDivision(self, team_id):
        """ return division ID for team ID """
        db = self.db
        cur = db.execute('SELECT division FROM teams WHERE team_id=? AND tid=?', (team_id, self.tid))
        row = cur.fetchone()

        if row:
            return row['division']
        else:
            return None

    def getPods(self, div=None):
        """ return list of POD IDs """
        db = self.db
        if (div):
            cur = db.execute('SELECT DISTINCT g.pod FROM games g WHERE g.division=? AND g.tid=? ORDER BY g.pod + 0 ASC', (div, self.tid))
        else:
            cur = db.execute('SELECT DISTINCT g.pod FROM games g WHERE g.tid=? ORDER BY g.pod + 0 ASC', (self.tid,))

        rows = cur.fetchall()
        if rows:
            pods = []
            for r in rows:
                pods.append(r['pod'])

            return pods
        else:
            return None

    def getPodsActive(self, div=None, team=None):
        """ return list of all pod IDs that have team (aka active), can be filtered by division or team """

        db = self.db
        if team:
            cur = db.execute('SELECT DISTINCT p.pod FROM pods p WHERE p.tid=? AND p.team_id=? ORDER BY p.pod + 0 ASC', (self.tid, team))
        elif div:
            cur = db.execute('SELECT DISTINCT p.pod FROM pods p, teams t WHERE p.team_id=t.team_id AND t.division=? and p.tid=? ORDER BY p.pod + 0 ASC',
                             (div, self.tid))
        else:
            cur = db.execute('SELECT DISTINCT p.pod FROM pods p WHERE p.tid=? ORDER BY p.pod + 0 ASC', (self.tid,))

        rows = cur.fetchall()
        if rows:
            pods = []
            for r in rows:
                pods.append(r['pod'])

            return pods
        else:
            return None

    def getPodNamesActive(self, div=None, team=None):
        """ return list of pod names (human readable) that have team assigned, filtered by division or team """
        pods = self.getPodsActive(div=div, team=team)
        pod_names = None
        if pods:
            pod_names = []
            for pod in pods:
                name = self.expandGroupAbbr(pod)
                if not name:
                    name = pod
                pod_names.append({'id': pod, 'name': name})

        return pod_names

    def getPools(self):
        """ list of pool surfaces for the tournament """
        db = self.db
        cur = db.execute("SELECT DISTINCT pool FROM games WHERE tid=?", (self.tid,))

        pools = []
        for r in cur.fetchall():
            if r['pool'] != "":
                pools.append(r['pool'])

        return pools

    def getGroups(self):
        """ get full list of groups indexed by ID """
        cur = self.db.execute("SELECT group_id, name FROM groups WHERE tid=?", (self.tid,))
        rows = cur.fetchall()

        groups = {}
        for row in rows:
            groups[row['group_id']] = row['name']

        return groups

    def expandGroupAbbr(self, group):
        """ takes short name for division or pod and returns expanded human readable name """
        db = self.db
        cur = db.execute('SELECT name FROM groups WHERE group_id=? and tid=?', (group, self.tid))

        row = cur.fetchone()

        if row:
            return row['name']
        else:
            return None

    def isGroup(self, group):
        """ boolean test if group exists or not """
        # TODO: see where tournament.isGroup is used from
        db = self.db
        cur = db.execute("SELECT count(*) FROM games WHERE (pod=? OR division=?) AND tid=?", (group, group, self.tid))

        count = cur.fetchone()[0]

        if count > 0:
            return True
        else:
            return False

    def isPod(self, pod):
        """ boolean test if pod exists """
        db = self.db
        cur = db.execute("SELECT count(*) FROM pods where pod=? AND tid=?", (pod, self.tid))

        count = cur.fetchone()[0]

        if count > 0:
            return True
        else:
            return False

    def getGroupColor(self, group_id):
        """ gets an HTML color code for the group if its part of the group table """
        db = self.db
        cur = db.execute("SELECT group_color FROM groups where group_id = ? AND tid=?", (group_id, self.tid))
        row = cur.fetchone()

        if row:
            return row[0]
        else:
            return None

    def getGroupRound(self, pod):
        """ Gets a round number for the pod if its set, used for sorting pods by round """
        db = self.db
        cur = db.execute("SELECT pod_round FROM groups WHERE group_id = ? AND tid = ?", (pod, self.tid))

        row = cur.fetchone()

        if row:
            return row[0]
        else:
            return None

    def getSeed(self, seed, division=None, pod=None):
        """ get seed for team in a division or pod from the team ID
        returns team ID or None if not seeded yet, e.g. round-robin isn't finished """
        if (self.endRoundRobin(division, pod)):
            standings = self.getStandings(division, pod)
            if len(standings) < 1:
                return None
            # BUG: used to check pods standings for ties but the pod get lots when net wins gets run so if the teams see eachother again
            # in a later pod then it can get a false positive on a tie in an older pod. This way avoids that but means that no pod can be seeded
            # if any pod has ties
            if self.checkForTies(standings):
                return None

            seed = int(seed) - 1
            try:
                if pod:
                    team_id = standings[pod][seed].team.team_id
                else:
                    team_id = standings[division][seed].team.team_id
            except IndexError:
                app.logger.debug("Asking for seed that is out of range: seed %s, div %s, pod %s" % (seed + 1, division, pod))
                return None

            return team_id
        else:
            return None

    def getPlacings(self, div=None):
        """ get list of placings, will be populated with teams if outcome can be determined
        returns list place dictionaries
        """
        db = self.db
        if div:
            cur = db.execute("SELECT division, place, game FROM rankings WHERE division=? AND tid=? ORDER BY CAST(place AS INTEGER)", (div, self.tid))
        else:
            cur = db.execute("SELECT division, place, game FROM rankings WHERE tid=? ORDER BY CAST(place AS INTEGER)", (self.tid,))

        placings = cur.fetchall()

        final = []
        for r in placings:
            entry = {}
            div = r['division']
            place = r['place']
            match = re.match(r"^\w+?(\d+)$", place)
            if match:
                place = match.group(1)

            game = json.loads(r['game'])
            placing_type = game['type']

            team_id = 0
            if placing_type == "winner":
                team_id = self.getWinner(game['game'])
                game_text = f"Winner of {game['game']}"
            elif placing_type == "loser":
                team_id = self.getLoser(game['game'])
                game_text = f"Loser of {game['game']}"
            elif placing_type == "seed":
                group_abriviation = game['group']
                seed = game['seed']
                if group_abriviation in self.getPods():
                    team_id = self.getSeed(seed, pod=group_abriviation)
                elif group_abriviation in self.getDivisions():
                    team_id = self.getSeed(seed, division=group_abriviation)

                group = self.expandGroupAbbr(group_abriviation)
                if not group:
                    group = group_abriviation

                if team_id:
                    team = self.getTeam(team_id)
                    if group:
                        game_text = f"{team} ({group}-{seed})"
                else:
                    game_text = f"{group} Seed {seed}"

            if team_id and team_id < 0:
                # temp hack while changing from using -1 for return values all over the place
                team_id = None

            if self.expandGroupAbbr(div):
                entry['div'] = self.expandGroupAbbr(div)
            else:
                entry['div'] = div

            entry['place'] = functions.ordinalize(place)
            if team_id:
                entry['team_id'] = team_id
                entry['name'] = self.getTeam(team_id)
                entry['flag_url'] = self.getTeamFlag(team_id)
            else:
                entry['name'] = game_text
                entry['flag_url'] = None
                entry['style'] = "soft"

            final.append(entry)

        return sorted(final, key=lambda k: k['div'])

    def getPlacingForTeam(self, team_id):
        """ get the final placing for a team if it has been determined

        return place diectionary
        """
        place = None
        all_placings = self.getPlacings()

        for p in all_placings:
            if "team_id" in p and p["team_id"] == team_id:
                place = p
                break

        return place

    def getParams(self):
        """ retrieve parameters for the tournament
        Keeps them stashed in the context store for performance"""
        if 'params' not in self.context:
            self.context.params = Params(self)

        return self.context.params

    def getTieBreak(self, tid_a, tid_b):
        """ Gets winner of tie breaker, returns team ID for winner or None if no tie-breaker found """
        params = self.getParams()
        # app.logger.debug("looking for a coin flip between %s and %s " % (tid_a,
        # tid_b))

        tid_a = int(tid_a)
        tid_b = int(tid_b)
        if params.getParam('tie-breaks'):
            tie_breaks = json.loads(params.getParam('tie-breaks'))
            for i in tie_breaks['tie-breaks']:
                team_list = i['teams']
                winner = i['winner']
                if tid_a in team_list and tid_b in team_list:
                    return winner
        else:
            return None

    def getTies(self):
        """ get list of any ties in the standings in the tournament
        Doesn't test that ties required action, e.g. all teams would be tied at start of tournament
        """
        # TODO: Definitely need test case for tournament.getTies, function shouldn't have worked before adding self to getTeam calls
        if 'ties' not in self.context:
            return None

        ties = self.context.get('ties', default=[])
        seen = set()
        list = [x for x in ties if x not in seen and not seen.add(x)]

        ties = []
        for tie in list:
            id_a = tie[0]
            id_b = tie[1]
            team_a = self.getTeam(id_a)
            team_b = self.getTeam(id_b)

            ties.append({'id_a': id_a, 'id_b': id_b, 'team_a': team_a, 'team_b': team_b})

        return ties

    def addTie(self, tid_a, tid_b, tid_c=None):
        """ Adds ties to the list of ties on the global environment, used to generate the warnings on the webpage """
        # # TODO: see how flaseshs are generated since they aren't here
        div_a = self.getDivision(tid_a)
        div_b = self.getDivision(tid_b)

        # not quite sure how this would happen, but protecting myself
        if div_a != div_b:
            return None

        # makes ties a [] if its not already set
        self.context.setdefault("ties", default=[])

        db = self.db

        cur = db.execute("SELECT DISTINCT p.pod FROM pods p WHERE (team_id=? OR team_id=?) AND tid=?", (tid_a, tid_b, self.tid))
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
            # TODO:  code to add divisional check goes here

        if tid_c:
            self.context.ties.append((tid_a, tid_b, tid_c))

        if tid_a < tid_b:
            self.context.ties.append((tid_a, tid_b))
        else:
            self.context.ties.append((tid_b, tid_a))

        return 0

    def genTieFlashes(self):
        if 'ties' not in self.context or len(self.context.ties) == 0:
            return

        ties = self.context.ties

        seen = set()
        list = [x for x in ties if x not in seen and not seen.add(x)]

        for tie in list:
            if len(tie) == 2:
                name_a = self.getTeam(tie[0])
                name_b = self.getTeam(tie[1])
                flash("There is a tie in the standings between %s & %s" % (name_a, name_b))
            elif len(tie) == 3:
                name_a = self.getTeam(tie[0])
                name_b = self.getTeam(tie[1])
                name_c = self.getTeam(tie[2])
                flash("There is a three-way tie with %s, %s and %s" % (name_a, name_b, name_c))

        flash("A coin flip is required, please see tournament director or head ref")
        return

    def endRoundRobin(self, division=None, pod=None):
        """ Test if round-robin play for division or pod is finished, true when all games have scores """
        # app.logger.debug("Running endRoundRobin - %s or %s" % (division, pod))

        db = self.db
        if (division is None and pod is None):
            cur = db.execute('SELECT count(*) as games FROM games WHERE type LIKE "RR%" AND tid=?', self.tid)
        elif (division is None and pod):
            cur = db.execute('SELECT count(*) as games FROM games WHERE type LIKE "RR%" AND pod=? AND tid=?', (pod, self.tid))
        elif division:
            cur = db.execute('SELECT count(*) as games FROM games WHERE type LIKE "RR%" AND division LIKE ? AND tid=?', (division, self.tid))
        else:
            cur = db.execute('SELECT count(*) as games FROM games WHERE type LIKE "RR%" AND division LIKE ? AND POD=? AND tid=?', (division, pod, self.tid))

        row = cur.fetchone()
        rr_games = row['games']

        if (division is None and pod is None):
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type LIKE "RR%" AND g.tid=s.tid AND s.tid=?',
                             self.tid)
        elif (division is None and pod):
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type LIKE "RR%" AND g.pod=? AND g.tid=s.tid AND g.tid=?',
                             (pod, self.tid))
        elif division:
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type LIKE "RR%" AND g.tid=s.tid AND g.division=? AND s.tid=?',
                             (division, self.tid))
        else:
            cur = db.execute('SELECT count(s.gid) as count FROM scores s, games g WHERE s.gid=g.gid AND g.type LIKE "RR%" \
                              AND division LIKE ? AND pod=? AND g.tid=s.tid AND s.tid=?', (division, pod, self.tid))

        row = cur.fetchone()
        games_played = row['count']

        # app.logger.debug("%s-%s: RR Games = %s and we've played %s games" %\
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
        """ converts the division ID into an integer, uses the index of the division in the division list as integer
        getDivisions underlying SQL call isn't ordered, so it should return based on the order the divisions where added
        """
        # TODO: there has to be a better way to do this tournament.divToInt()
        div_list = self.getDivisions()
        if div in div_list:
            return div_list.index(div)
        else:
            return 0

    def podToInt(self, pod):
        """ converts pod ID to an integer based on its index in the list of pods, see above, totally janky """
        # TODO: there has to be a better way to do this tournament.podToInt()
        pod_list = self.getPods()
        if pod in pod_list:
            return pod_list.index(pod)
        else:
            return 0

    def netWins(self, team_a, team_b, pod=None):
        """ returns win differential between two teams. Returns postive or negative based on team_a's differential with team_b
        e.g. if team_a beat team_b in the RR play return would be 1, if team_a lost to team_b return would be -1"""
        db = self.db
        net_wins = 0

        tid_a = team_a.team_id
        tid_b = team_b.team_id

        if team_a.pod != team_b.pod:
            app.logger.debug("Comparing two teams that aren't in the same pod, that's ok")

        if pod and not self.isPod(pod):
            pod = None
            # app.logger.debug("Comparing netWins with pod that isn't a pod, setting to None")

        # app.logger.debug("Checking %s v %s in pod %s" % (team_a.name, team_b.name, pod))

        if pod:
            cur = db.execute('SELECT s.gid, s.black_tid, s.white_tid, s.score_w, s.score_b, s.forfeit FROM scores s, games g \
                            WHERE s.gid = g.gid AND s.tid=g.tid AND ((s.black_tid=? AND s.white_tid=?)\
                            OR (s.black_tid=? AND s.white_tid=?)) AND g.type LIKE "RR%" AND g.pod=? AND g.tid=?',
                             (tid_a, tid_b, tid_b, tid_a, pod, self.tid))
        else:
            cur = db.execute('SELECT s.gid, s.black_tid, s.white_tid, s.score_w, s.score_b, s.forfeit FROM scores s, games g \
                            WHERE s.gid = g.gid AND s.tid=g.tid AND ((s.black_tid=? AND s.white_tid=?)\
                            OR (s.black_tid=? AND s.white_tid=?)) AND g.type LIKE "RR%" AND g.tid=?',
                             (tid_a, tid_b, tid_b, tid_a, self.tid))

        games = cur.fetchall()

        for game in games:
            black_tid = game['black_tid']
            white_tid = game['white_tid']
            score_b = game['score_b']
            score_w = game['score_w']
            forfeit = game['forfeit']
            # app.logger.debug("%s - %s v %s - %s to %s" % (game['gid'], black_tid, white_tid, score_b, score_w))

            if forfeit:
                if forfeit == "w":
                    if white_tid == tid_a:
                        net_wins -= 1
                    elif black_tid == tid_a:
                        net_wins += 1
                if forfeit == "b":
                    if black_tid == tid_a:
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

        # app.logger.debug("net wins: %s" % net_wins)
        return net_wins

    def cmpTeams(self, team_b, team_a, pod=None):
        """ function use for sorting Stats class for standings
        Compares two teams for most points, head-to-head, most wins, least loses and goals allowed
        Will look up coin-flips for required tie breaks if fully tied and return the winner of the tie breaker

        ONLY USE WHEN COMPARING TWO TEAMS DIRECTLY, DO NOT USE TO SORT TEAMS """
        # app.logger.debug("in cmpTeams between %s and %s for pod %s" % (team_a, team_b, pod))
        if not team_a.pod and team_a.division.lower() != team_b.division.lower():
            # no pods and not in same division
            return self.divToInt(team_a.division) - self.divToInt(team_b.division)
        elif team_a.pod != team_b.pod and team_a.division.lower() != team_b.division.lower():
            # app.logger.debug("not same division")
            return self.divToInt(team_a.division) - self.divToInt(team_b.division)
        elif team_a.pod != team_b.pod:
            # app.logger.debug("not same pod")
            return self.podToInt(team_a.pod) - self.podToInt(team_b.pod)
        elif team_a.points != team_b.points:
            # app.logger.debug("breaking on points")
            return team_a.points - team_b.points
        elif self.netWins(team_a, team_b, pod) != self.netWins(team_b, team_a, pod):
            # app.logger.debug("breaking on netwins")
            return self.netWins(team_a, team_b, pod) - self.netWins(team_b, team_a, pod)
        elif team_a.wins != team_b.wins:
            # app.logger.debug("breaking on wins")
            return team_a.wins - team_b.wins
        elif team_a.losses != team_b.losses:
            # app.logger.debug("breaking on losses")
            return team_b.losses - team_a.losses
        elif team_a.goals_allowed != team_b.goals_allowed:
            # app.logger.debug("breaking on gloas allowed")
            return team_b.goals_allowed - team_a.goals_allowed
        else:
            # app.logger.debug("straight up tie")
            winner = self.getTieBreak(team_a.team_id, team_b.team_id)
            if winner == team_a.team_id:
                return 1
            elif winner == team_b.team_id:
                return -1
            else:
                self.addTie(team_a.team_id, team_b.team_id)
                return 0

    def cmpTeamsSort(self, team_b, team_a):
        """ Compares teams without including head-to-head, required for sorting sets of three or more teams """
        if team_a.division.lower() != team_b.division.lower():
            return self.divToInt(team_a.division) - self.divToInt(team_b.division)
        elif team_a.wins != team_b.wins:
            return team_a.wins - team_b.wins
        elif team_a.losses != team_b.losses:
            return team_b.losses - team_a.losses
        elif team_a.goals_allowed != team_b.goals_allowed:
            return team_b.goals_allowed - team_a.goals_allowed
        else:
            return 0

    def cmpRankSort(self, rank_b, rank_a):
        """ wrapper function for cmpTeamsSort """
        return self.cmpTeamsSort(rank_b.team, rank_a.team)

    def checkForTies(self, standings):
        """ boolean test to check standings for ties """
        x = 0
        last = 0
        for group in standings.keys():
            group_standings = standings[group]
            while x < len(group_standings) - 1:
                if self.cmpTeamsSort(group_standings[x].team, group_standings[x + 1].team) == 0:
                    if last == 1:
                        app.logger.debug("You need a three sided die, give up and go home")
                        return True
                    else:
                        last = 1
                else:
                    last = 0
                x = x + 1

            x = 0
            while x < len(group_standings) - 1:
                if self.cmpTeams(group_standings[x].team, group_standings[x + 1].team) == 0:
                    return True
                x = x + 1

        return False

    def sortStandings(self, team_stats, pod=None):
        """ Sort a list of team stats into the rankings
        Returns ordered list of ranking objects, ranking object contains original team stat object along with division, pod and place
        Place field should be used whenever standings are displayed, multiple teams can be displayed as in the same place when ties are present
        Do not try to use the index of the list as the place """

        # # TODO: scrub tournaments.sortStandings()
        # if not pod:
        #    app.logger.debug("sorting standings without pod")
        # else:
        #    app.logger.debug("sorting for pod %s" % pod)

        for team in team_stats:
            # team = team_stats[place]
            if team.pod != pod:
                # TODO: maybe raise an exception?
                app.logger.debug("I have standings that aren't for my pod")

        ordered = sorted(team_stats)

        # first go through the list and assign a place to everybody based on only points
        # doesn't settle tie breakers yet
        i = 1
        standings = []
        last = None
        skipped = 0
        for team in ordered:
            # reset rank number of its a new division or pod
            if not last:
                i = 1
            elif team != last and skipped > 0:
                i = i + skipped + 1
                skipped = 0
            elif team != last:
                i += 1
            else:
                skipped += 1

            rank = i
            standings.append(Ranking(team.division, team.pod, rank, team))

            last = team

        # use list Comprehensions to find all the tied teams

        places = len(standings)
        place = 1
        while place <= places:
            place_teams = [x for x in standings if x.place == place]
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
                if self.cmpTeams(a, b, pod) < 0:
                    place_teams[1].place += 1
                elif self.cmpTeams(a, b, pod) > 0:
                    place_teams[0].place += 1
                else:
                    # Tied, no coin clip, and that's ok for now
                    continue
            elif count == 3:
                app.logger.debug("working a three-way in %s" % pod)
                app.logger.debug(place_teams)

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
                    place += 1
                    if pod and self.endRoundRobin(pod=pod):
                        app.logger.debug("three way tie all equal in %s" % pod)
                        app.logger.debug("end of round robin and three-way tie")
                        self.addTie(place_teams[0].team.team_id, place_teams[1].team.team_id, place_teams[2].team.team_id)
                    else:
                        # TODO: probably should verify everybody is the same division
                        div = place_teams[0].div
                        if self.endRoundRobin(division=div):
                            app.logger.debug("three way tie all equal in %s" % div)
                            app.logger.debug("end of round robin and three-way tie")
                            self.addTie(place_teams[0].team.team_id, place_teams[1].team.team_id, place_teams[2].team.team_id)

                    continue
                else:
                    # sort teams based on rules w/o head-to-head
                    place_teams = sorted(place_teams)

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
                app.logger.debug("%s teams tied in pod %s" % (count, pod))

                place_teams = sorted(place_teams)

                most_goals = place_teams[-1].team.goals_allowed
                tied = [x for x in place_teams if x.team.goals_allowed == most_goals]

                if len(tied) == len(place_teams):
                    place += 1
                else:
                    for r in tied:
                        r.place += len(place_teams) - len(tied)

        # resort to make sure in order by place, pod and division
        tmp = sorted(standings, key=lambda x: x.place)
        if pod:
            return sorted(tmp, key=lambda x: x.pod)
        else:
            return sorted(tmp, key=lambda x: x.div)

    # master function for calculating standings of all teams
    # shouldn't be called directly, use getStandings() to avoid
    # recalculating multiple times per load
    def calcStandings(self):
        """ worker function to calculate the standings of all the teams
        Do not call directly, use getStandings() wrapper to avoid recalculating """
        standings = {}

        active_pods = self.getPodsActive()
        if active_pods:
            for pod in active_pods:
                team_stats = []
                group_teams = self.getTeams(pod=pod)
                for team in group_teams:
                    team_stats.append(Stats(self, team, pod))
                standings[pod] = self.sortStandings(team_stats, pod)
        else:
            for div in self.getDivisions():
                team_stats = []
                group_teams = self.getTeams(div=div)
                for team in group_teams:
                    team_stats.append(Stats(self, team))
                standings[div] = self.sortStandings(team_stats)

        return standings

    def getStandings(self, div=None, pod=None):
        """ wrapper function for standings, uses app context to cache standings calculations
        since standings are cached filtinging for div or pod has to be done in loops
        """

        if 'standings' not in self.context:
            app.logger.debug("Calculating standings")
            if 'ties' in self.context:
                self.context.pop('ties')
            self.context.standings = self.calcStandings()

        # filter for pod and div
        standings = {}
        if pod:
            if pod in self.context.standings:
                standings[pod] = self.context.standings[pod]
            else:
                standings = None
        elif div:
            if div in self.context.standings:
                standings[div] = self.context.standings[div]
            else:
                div_pods = self.getPodsActive(div=div)
                if not div_pods:
                    # pod has no division, so the best we can do is return everything
                    standings = self.context.standings
                else:
                    for pod in div_pods:
                        standings[pod] = self.context.standings[pod]
        else:
            standings = self.context.standings

        return standings

    def shakeTree(self):
        """ Stupid function that needs to be renamed, but shakes the tree so to speak after
        updates that would change standings and require any recaluclations
        """
        if 'standings' in self.context:
            self.context.pop('standings')
        if 'ties' in self.context:
            self.context.pop('ties')
        if 'params' in self.context:
            self.context.pop('params')

        self.popSeededPods()

        return

    def splitStandingsByGroup(self, standings):
        """ Helper function that takes in a standings list and groups them into a dictionary
        by group (aka div or div and pod together)
        """
        return standings

        grouped_standings = {}

        for entry in standings:
            group_name = None
            if self.expandGroupAbbr(entry.pod):
                pod_name = self.expandGroupAbbr(entry.pod)
            else:
                pod_name = entry.pod
            if self.expandGroupAbbr(entry.div):
                div_name = self.expandGroupAbbr(entry.div)
            else:
                div_name = entry.div

            group_round = self.getGroupRound(entry.pod)

            if pod_name == div_name:
                div_name = None


            if group_round and div_name and pod_name:
                group_name = "Round %s: %s - %s" % (group_round, div_name, pod_name)
            elif group_round and div_name:
                group_name = "Round %s: %s" % (group_round, div_name)
            elif group_round and pod_name:
                group_name = "Round %s: %s" % (group_round, pod_name)
            elif div_name and pod_name:
                group_name = "%s - %s" % (div_name, pod_name)
            elif div_name:
                group_name = div_name
            elif pod_name:
                group_name = pod_name
            else:
                group_name = "Standings"

            if group_name in grouped_standings:
                grouped_standings[group_name].append(entry)
            else:
                grouped_standings[group_name] = [entry]

        return grouped_standings

    def getTimingRules(self, game_type=None):
        """ gets timing rules for a specific game type,
        returns the default timing rules if game type not passed or game type cannot be found

        returns dictionary of timing rules"""

        timing_rules = None
        params = self.getParams()
        timing_rule_set = params.getParam("timing_rules")
        if not timing_rule_set:
            return None

        timing_rule_set = json.loads(timing_rule_set)

        # set default rules
        timing_rules = timing_rule_set['default_rules']

        # if game_type passed in and rule_set has list of game_types, see if there is a match
        if game_type and 'game_types' in timing_rule_set:
            for entry in timing_rule_set['game_types']:
                if entry['game_type'] == game_type:
                    timing_rules = entry['timing_rules']

        return timing_rules

    def getTimingRuleSet(self):
        """ get full timing rule set parameter, returns dictionary """
        params = self.getParams()
        timing_rule_set = params.getParam("timing_rules")

        if timing_rule_set:
            return json.loads(timing_rule_set)
        else:
            return None

    ##########################################################################
    # Admin functions
    ##########################################################################
    def isAuthorized(self, user):
        """ test if user is authorized to manage this tournament """
        # first check if the tournament is active, just a little safety mech
        if not self.is_active:
            return False

        # app.logger.debug("checking on admin")
        # first check if they are a site_admin or admin, if yes, just return true
        if user.site_admin or user.admin:
            return True

        # app.logger.debug("guess user isn't a super admin")
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

    def getAuthorizedUserIDs(self):
        """ return list of user IDs that are allowed to managed this tournament explicitly
        won't include admins who have global permissions """
        authorized_ids = []

        db = self.db
        cur = db.execute("SELECT admin_ids FROM tournaments WHERE tid=?", (self.tid,))
        row = cur.fetchone()
        if row['admin_ids']:
            id_string = row['admin_ids']
        else:
            return []

        authorized_ids = id_string.split(",")

        return authorized_ids

    def updateAdminStatus(self, make_admin, user_id):
        """ updates the admin status of a given user ID, will either insert or remove (if present) user ID
        based on is_admin boolean. Removing an ID that is not an admin is considered a success.
        """
        user = functions.getUserByID(user_id)
        if not user:
            app.logger.debug("Tried to add non-existant ID %s to tournament %s" % (user_id, self.short_name))
            raise UpdateError("notfound", message=f"User ID {user_id} does not exist")

        if flask_g.current_user_id == user_id:
            app.logger.debug("User tried to change their own status")
            raise UpdateError("self", message="Can't change admin status of yourself")

        authorized_ids = self.getAuthorizedUserIDs()
        if make_admin and user not in authorized_ids:
            authorized_ids.append(user_id)
        elif user_id in authorized_ids:
            authorized_ids.remove(user_id)
        else:
            # nothing to do
            return

        authorized_ids_string = ",".join(authorized_ids)
        db = self.db
        db.execute("UPDATE tournaments SET admin_ids=? WHERE tid=?", (authorized_ids_string, self.tid))
        db.commit()

        audit_logger.info(f"{self.short_name} - Admin status updated: {user.short_name} ({user.user_id}) admin: {make_admin}")

        return

    # takes in dictionary from POST and updates/creates score for single game
    # does not provide authorization check, that needs to be done pre-call
    def updateGame(self, game):
        """ update game score in databse
        game input from POST and updates/creates score for single game
        does not provide for authorization check """
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
            raise UpdateError("Black score is not an integer")
        elif not isinstance(score_w, int):
            raise UpdateError("White score is not an integer")
        elif not black_tid:
            raise UpdateError("Missing black team ID")
        elif not white_tid:
            raise UpdateError("Missing white team ID")

        db.execute("INSERT OR IGNORE INTO scores (black_tid, white_tid, score_b, score_w,tid, gid, pod, forfeit) VALUES(?,?,?,?,?,?,?,?)",
                   (black_tid, white_tid, score_w, score_b, self.tid, gid, pod, forfeit))
        db.execute("UPDATE scores SET score_b=?,score_w=?, forfeit=? WHERE tid=? AND gid=?",
                   (score_b, score_w, forfeit, self.tid, gid))
        db.commit()

        self.shakeTree()

        return 1

    def updateTimingRules(self, rule_set):
        """ Set a timing rule for a specific game type and save it to the parameters table
            game_type should match schedule game types of RR, BR or E
            timing_rules should be full timing_rules JSON part from timing_rules schema
        """

        params = self.getParams()
        current_rule_set = params.getParam("timing_rules")

        rule_set = json.dumps(rule_set)
        if not current_rule_set:
            params.addParam("timing_rules", rule_set)
        else:
            params.updateParam("timing_rules", rule_set)

        return True

    def popSeededPods(self):
        """ Checks if first round of pods is all finished and populates seeded pods
        Uses seeded_mod_matrix param to fill in the seedings from the first round pods to the second round pods
        example: seeded_pod_matrix={"1P":["A","B","C"], "2P":["A","B","C"], "3P":["A","B","C"], "4P":["A","B","C"], "5P":["A","B","C"]}
        Takes the teams from pods "1P" - "5P" in the first round and seeds them into "A", "B" and "C" pods
        Works sequentially through the rankings for the first pod.
        """

        params = self.getParams()

        seeded_pods = params.getParam('seeded_pods')
        if not seeded_pods or seeded_pods == "0":   # seeded pods could be none or 0, this should handle both
            return None

        if seeded_pods == 1:  # pods already seeded, nothing to do here
            return True

        pod_matrix = params.getParam('seeded_pod_matrix')
        if not pod_matrix:
            app.logger.debug("Trying to populate seeded pods but can't find seeded_pod_matrix param, that's an issue")
            return None

        try:
            pod_matrix = json.loads(pod_matrix)
        except ValueError as e:
            app.logger.debug("Unable to parse seeded_mod_matrix JSON, probably bad json")
            app.logger.debug(e)
            return None

        app.logger.debug("popSeededPods: checking if roundrobin is complete")

        round1 = list(pod_matrix.keys())

        # test if all pods are done, list of endRoundRobin booleans
        pods_done = []
        for pod in round1:
            pods_done.append(self.endRoundRobin(None, pod))

        # check all endRoundRobin results were True
        if not all(done is True for done in pods_done):
            return 0

        # test that there are no ties in any of the round-robins, can't seat until all ties are resolved
        ties = []
        for pod in round1:
            ties.append(self.checkForTies(self.getStandings(None, pod)))

        if not all(has_tie is False for has_tie in ties):
            return 0

        if "DirectRules" in pod_matrix:
            # Need to verify that any direct mapping rule games are done
            for rule in pod_matrix["DirectRules"]:
                app.logger.debug("Checking directrule: %s" % rule)
                match = re.search(r"^[W|L](\d+)$", rule)
                if match:
                    gid = match.group(1)
                    team_id = self.getWinner(gid)
                    app.logger.debug("Team ID for winner game: %s= %s" % (gid, team_id))
                    if team_id < 1:
                        return 0

        app.logger.debug("All round-robins done - seeding the pods %s" % pods_done)

        db = self.db

        for pod in round1:
            # check if its really a pod
            podStandings = self.getStandings(None, pod)

            rules = pod_matrix[pod]
            offset = 0

            for rank in podStandings:
                app.logger.debug("Offset = %s" % offset)
                new_pod = rules[offset]
                if not new_pod:
                    # Spot in JSON is "None", used when a seed is determened with extra logic like a crossover game
                    offset += 1
                    continue
                team = rank.team
                team_id = team.team_id
                cur = db.execute("INSERT INTO pods (tid, team_id, pod) VALUES (?,?,?)", (self.tid, team_id, new_pod))
                db.commit()
                # cur = db.execute("UPDATE teams SET division=? WHERE team_id=? and tid=?",(pod, team_id, app.config['TID']))
                # db.commit()
                offset += 1

        if "DirectRules" in pod_matrix:
            # direct placement rules, directionary of key pairs liks  {"W23": "A", "L23": "B"} indicating that the Winnder of game 23
            # goes to the A pod and the loser goes to the B pod
            for rule, new_pod in pod_matrix["DirectRules"].items():
                # parse the game
                team_id = None

                match = re.search(r"^W(\d+)$", rule)
                if match:
                    gid = match.group(1)
                    team_id = self.getWinner(gid)

                # Loser of
                match = re.search(r"^L(\d+)$", rule)
                if match:
                    gid = match.group(1)
                    team_id = self.getLoser(gid)

                if team_id > 0:
                    db.execute("INSERT INTO pods (tid, team_id, pod) VALUES (?,?,?)", (self.tid, team_id, new_pod))
                    db.commit()
                else:
                    app.logger.debug("Didn't find a team while parting a direct rule, bad")

        # set seeded pods to 1 to indicated that pods have been seeded, short circuits the function from being called again
        params.updateParam('seeded_pods', 1)

        return True

    def updateConfig(self, config_id, config_options):
        """ update a tournament configuration state. config_id keys the config that is changing, config_optoins is
        a dictionary with the optional necessary paraemters """

        if config_id == "blackout":
            if config_options['enabled']:
                self.setBlackout(blackout=True, message=config_options['message'])
            else:
                self.setBlackout(blackout=False)
        elif config_id == "coin_flip":
            id_a = config_options['id_a']
            id_b = config_options['id_b']
            winner = config_options['winner']
            self.addCoinFlip(id_a, id_b, winner)
        elif config_id == 'tie_break':
            self.addTieBreak(config_options)
        elif config_id == "banner":
            self.updateSiteMessage(enabled=config_options['enabled'], message=config_options['message'])
        elif config_id == "admin":
            self.updateAdminStatus(config_options['make_admin'], config_options['user_id'])
        elif config_id == "timing_rules":
            self.updateTimingRules(config_options['timing_rule_set'])
        elif config_id == "finalize" and config_options['finalize']:
            # nobody should be sending finalize: false but just to be safe
            self.finalize()
            audit_logger.info("Finalizing %s" % self.name)
        else:
            raise UpdateError("Unknown config_id", message="I don't understand that config option, nothing changed")

        return

    def addTieBreak(self, tie_break):
        """ add outcome of coin flip """

        try:
            teams = list(map(int, tie_break['teams']))
            tie_break['teams'] = teams
        except ValueError:
            raise UpdateError("notint", message="Teams in tie break must be IDs")

        params = self.getParams()
        raw_tie_breaks = params.getParam('tie-breaks')
        if raw_tie_breaks:
            tie_break_json = json.loads(raw_tie_breaks)
        else:
            tie_break_json = {'tie-breaks': []}

        # overkill but lets verify that there isn't already a tie for these teams
        tie_break_list = tie_break_json['tie-breaks']
        for e in tie_break_list:
            if sorted(e['teams']) == tie_break['teams']:
                raise UpdateError("duplicate", "there is already a tie break for these two teams")

        tie_break_json['tie-breaks'].append(tie_break)
        params.setParam('tie-breaks', json.dumps(tie_break_json))

        self.shakeTree()
        return

    def setBlackout(self, blackout, message=None):
        """ Set if tournameent should be blacked out (true/false) and set message if passed
        Used to disable schedule/standings in case where data is wrong and would cause confusion

        Users will not be able to see schedule/standings until blackout is lifted

        (used to be called site status)
        """
        # delete first incase message is being updated
        params = self.getParams()
        params.clearParam("blackout")

        if not message:
            message = "Tournament is temporary blacked out, please check back later."

        if blackout:
            params.addParam("blackout", message)

        audit_logger.info(f"{self.short_name}: Blackout status set {blackout}")
        return 0

    def getBlackoutMessage(self):
        """ Gets message of site is disabled """
        params = self.getParams()

        disable_message = params.getParam("blackout")

        return disable_message

    def updateSiteMessage(self, enabled, message):
        """ Set site message (aka banner) enable/disable and set message
        site message should be used for annoucments or info (e.g. what time is beer served?), doesn't disable site
        """
        params = self.getParams()

        if enabled and not message:
            raise UpdateError("nullvalue", message="Site message cannot be empty")

        if enabled:
            params.clearParam("site_message")
            params.addParam("site_message", message)
            audit_logger.info(f"{self.short_name}: Banner set: {message}")
        else:
            params.clearParam("site_message")
            audit_logger.info(f"{self.short_name}: Banner cleared")

        return 0

    def getSiteMessage(self, html=True):
        """ get site_message if set, returns None if no message
        supports expanding markdown link notation to HML when html=True, default
        """
        params = self.getParams()

        site_message = params.getParam("site_message")
        if not site_message:
            return None

        if not html:
            return site_message
        else:
            # look for markdown notation links and expand to HTML
            links = re.findall(r"\[(.*?)\]\((.*?)\)", site_message)
            for link in links:
                text = link[0]
                url = link[1]
                site_message = site_message.replace(f"[{text}]({url})", f"<a href=\"{url}\">{text}</a>")

        return site_message

    def finalize(self):
        """ Finalize the tournament by setting active to 0 which should stop any updates to the tournament """
        # don't allow finalizing when not all scores have been entered
        games = self.getGames()
        for game in games:
            if not game.played:
                raise UpdateError("notfinished", message="Cannot finalize without all scores")

        db = self.db
        db.execute("UPDATE tournaments SET active=0 WHERE tid=?", (self.tid,))
        db.commit()

        return True
