from base64 import b64encode
from datetime import datetime
from flask import current_app as app
from os import urandom
import bcrypt
import re

# class used for calculating standings, stat object has all the values
# for the things standings are calculator against

from scoreboard.exceptions import UpdateError
from scoreboard import audit_logger

class Stats(object):
    """ Class to hold all the stats for a given team in a given group (division or pod) a single team may have multiple stats
    instances based on how many groups the team is in. Stats include all the numarical values that would be used in calculating
    a teams standings but does not include head-to-head.

    :param tournament: {tournament} tournament object
    :param team_id: {int} team to calculate stats for
    :param pod: {str or None} Pod to use for Inner Group Play

    """

    def __init__(self, tournament, team, pod=None, unittest=False):
        self.tournament = tournament
        self.tid = tournament.tid
        self.db = tournament.db

        self.team_id = team['team_id']
        self.name = team['name']
        self.division = team['division']

        self.pod = pod

        # TODO:  standardize flag url format
        if team['flag_url']:
            self.flag_url = {'full_res': team['flag_url'], 'thumb': team['flag_url']}
        else:
            self.flag_url = None

        # define who to count for inner group play in calculating stats.
        if self.pod:
            self.inner_group = self.pod
        else:
            self.inner_group = self.division

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

        # initialize all the stat values from the database
        if not unittest:
            self.load_stats()


    def __repr__(self):
        return '{}({}): {} {}-{}-{}'.format(self.name, self.team_id, self.points, self.wins, self.losses, self.ties)

    def __eq__(self, other):
        """ Compares two teams stat objects to see if the teams should be considered "equal" in standings or not
        only checks points as tie breakers are handled elese where
        """
        if self.division.lower() != other.division.lower():
            return False
        elif self.pod and self.pod != other.pod:
            return False
        elif self.points != other.points:
            return False
        else:
            return True

    def __ne__(self, other):
        if self.division.lower() != other.division.lower():
            return True
        elif self.pod and self.pod != other.pod:
            return True
        elif self.points != other.points:
            return True
        else:
            return False

    def __lt__(self, other):
        """ Enforce underwater hockey tie breakers that can be enforce numerically so only points, wins, loses and goals allowed
        head-to-head tie-breakers has to be enforced else where
        """
        if self.points != other.points:
            return (self.points > other.points)
        elif self.wins != other.wins:
            return (self.wins > other.wins)
        elif self.losses != other.losses:
            return (self.losses < other.losses)
        elif self.goals_allowed != other.goals_allowed:
            return (self.goals_allowed < other.goals_allowed)
        else:
            return (self.name < other.name)

    def load_stats(self):
        """ Load all the games in for the team and calaculate their inner group stats
        """
        cur = self.db.execute('SELECT s.black_tid, s.white_tid, s.score_b, s.score_w, s.forfeit, g.type, g.pod  FROM scores s, games g\
                          WHERE g.gid=s.gid AND g.tid=s.tid AND (white_tid=? or black_tid=?) AND s.tid=?', (self.team_id, self.team_id, self.tid))

        games = cur.fetchall()
        for game in games:
            black_tid = game['black_tid']
            white_tid = game['white_tid']
            score_b = game['score_b']
            score_w = game['score_w']
            forfeit = game['forfeit']
            if self.team_id == black_tid:
                opponent_id = white_tid
            elif self.team_id == white_tid:
                opponent_id = black_tid
            else:
                app.logger("Got game back that I'm not in processing stats, very bad")
                continue

            # is inner group play
            is_igp = False

            if not game['type']:
                # must be a RR type game to even be considered for IGP
                is_igp = False
            elif re.match(r"^RR.*", game["type"]):
                if game["pod"] and game["pod"] == self.inner_group:
                    is_igp = True
                elif not game["pod"] and self.division == self.tournament.getDivision(opponent_id):
                    is_igp = True

            if is_igp:
                self.games_played += 1
                if white_tid == self.team_id:
                    self.goals_allowed += score_b
                elif black_tid == self.team_id:
                    self.goals_allowed += score_w

            # forfeit
            if forfeit == "b" and black_tid == self.team_id:
                if is_igp:
                    self.losses += 1
                    self.points -= self.tournament.POINTS_FORFEIT
                self.losses_t += 1

            if forfeit == "b" and white_tid == self.team_id:
                if is_igp:
                    self.wins += 1
                    self.points += self.tournament.POINTS_WIN
                self.wins_t += 1

            if forfeit == "w" and white_tid == self.team_id:
                if is_igp:
                    self.losses += 1
                    self.points -= self.tournament.POINTS_FORFEIT
                self.losses_t += 1

            if forfeit == "w" and black_tid == self.team_id:
                if is_igp:
                    self.wins += 1
                    self.points += self.tournament.POINTS_WIN
                self.wins_t += 1

            # black won
            if score_b > score_w and black_tid == self.team_id:
                if is_igp:
                    self.wins += 1
                    self.points += self.tournament.POINTS_WIN
                self.wins_t += 1
            elif score_b > score_w and white_tid == self.team_id:
                if is_igp:
                    self.losses += 1
                self.losses_t += 1

            # white won
            if score_b < score_w and white_tid == self.team_id:
                if is_igp:
                    self.wins += 1
                    self.points += self.tournament.POINTS_WIN
                self.wins_t += 1
            elif score_b < score_w and black_tid == self.team_id:
                if is_igp:
                    self.losses += 1
                self.losses_t += 1

            if score_w == score_b and forfeit is None:
                if is_igp:
                    self.ties += 1
                    self.points += 1
                self.ties_t += 1


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

    def __lt__(self, other):
        return (self.place < other.place)

    def __gt__(self, other):
        return (self.place > other.place)

    def serialize(self):

        if self.div:
            div = self.div
        else:
            div = None

        if self.pod:
            pod = self.pod
        else:
            pod = None

        return {
            'div': div,
            'pod': pod,
            'place': self.place,
            'team': self.team.name,
            'team_id': self.team.team_id,
            'stats': {
                'points': self.team.points,
                'wins': self.team.wins,
                'losses': self.team.losses,
                'ties': self.team.ties,
                'goals_allowed': self.team.goals_allowed,
                'games_played': self.team.games_played,
                'wins_total': self.team.wins_t,
                'losses_total': self.team.losses_t,
                'ties_total': self.team.ties_t
            }
        }


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

        field = str(field)
        val = str(val)

        cur = db.execute('INSERT INTO params VALUES (?,?,?)', (tid, field, val))
        db.commit()

        #g.params = self.loadParams()
        return 0

    def updateParam(self, field, val):
        db = self.t.db
        tid = self.t.tid

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


class User(object):
    def __init__(self, user_id, db):
        self.user_id = user_id

        self.db = db
        cur = db.execute("SELECT short_name, email, date_created, last_login, site_admin, admin, active FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()

        self.short_name = row['short_name']
        self.email = row['email']
        self.date_created= datetime.strptime(row['date_created'],"%Y-%m-%d %H:%M:%S")
        if row['last_login']:
            self.last_login = datetime.strptime(row['last_login'],"%Y-%m-%d %H:%M:%S")
        else:
            self.last_login = None
        self.site_admin = row['site_admin']
        self.admin = row['admin']
        self.active = row['active']

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.user_id)

    def setPassword(self, password):
        db = self.db

        password = password.encode('utf-8')
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())

        cur = db.execute("UPDATE users SET password=?, reset_token=null, failed_logins=0 WHERE user_id=?", (hashed, self.user_id))
        db.commit()

        return 0

    def resetUserPass(self):
        db = self.db

        while True:
            token = self.__genResetToken()
            cur = db.execute("SELECT user_id FROM users WHERE reset_token=?", (token,))
            if not cur.fetchone():
                break

        hashed = bcrypt.hashpw(token, bcrypt.gensalt())

        cur = db.execute("UPDATE users SET password=?, reset_token=?, active=1 WHERE user_id=?", (hashed, token.decode('utf-8'), self.user_id))
        db.commit()

        return token.decode("utf-8")

    def setActive(self, active):
        db = self.db

        cur = db.execute("UPDATE users SET active=? WHERE user_id=?", (active, self.user_id,))
        db.commit()

        return 0

    def setAdmin(self, admin_status):
        db = self.db

        if admin_status:
            cur = db.execute("UPDATE users SET admin=1 WHERE user_id=?", (self.user_id,))
            db.commit()
        else:
            cur = db.execute("UPDATE users SET admin=0 WHERE user_id=?", (self.user_id,))
            db.commit()

    def __genUserKey(self):
        return b64encode(urandom(9), b"Aa")

    def __genResetToken(self):
        return b64encode(urandom(30), b"-_")


class Player(object):
    """ Class object for players, this is the object used to represent players on teams as part of rosters. It is distinct from "users" which represent
    users of the Scoreboard system for administration purposes """

    def __init__(self, db, display_name, player_id=None):
        self.db = db
        self.date_created = None
        self.date_updated = None

        if not player_id:
            # generate a player ID and make sure its unique in the DB
            while player_id is None:
                player_id = b64encode(urandom(6), b"Aa").decode("utf-8")
                cur = self.db.execute("SELECT player_id FROM players WHERE player_id=?", (player_id,))
                exists = cur.fetchone()
                if exists:
                    player_id = None
            app.logger.info("Generated new player ID %s for player %s" % (player_id, display_name))
        else:
            cur = self.db.execute("SELECT display_name, date_created, date_updated FROM players WHERE player_id=?", (player_id,))
            row = cur.fetchone()
            display_name = row['display_name']
            self.date_created = datetime.strptime(row['date_created'], "%Y-%m-%d %H:%M:%S")
            if row['date_updated']:
                self.date_updated = datetime.strptime(row['date_updated'], "%Y-%m-%d %H:%M:%S")
            else:
                self.date_updated = self.date_created

        self.player_id = player_id
        self.display_name = display_name

        self.teams = self.findTeams()

    def __repr__(self):
        return '{}: {} - {}'.format(self.player_id, self.display_name, self.teams)

    def serialize(self):
        return {
            'player_id': self.player_id,
            'display_name': self.display_name,
            'date_created': self.date_created.isoformat(),
            'date_updated': self.date_updated.isoformat(),
            'teams': self.teams
        }

    def commit(self):

        cur = self.db.execute("SELECT player_id FROM players WHERE player_id=?", (self.player_id,))
        existing = cur.fetchone()

        if existing:
            self.db.execute("UPDATE players SET display_name=?, date_updated=datetime('now') WHERE player_id=?", (self.display_name, self.player_id))
        else:
            self.db.execute("INSERT INTO players (player_id, display_name) VALUES (?,?)", (self.player_id, self.display_name))
        self.db.commit()

        return True

    def findTeams(self):
        from scoreboard.functions import getTournamentByID

        teams = []
        cur = self.db.execute("SELECT tid, team_id, cap_number, is_coach, coach_title FROM rosters WHERE player_id=?", (self.player_id,))

        rows = cur.fetchall()
        for row in rows:
            team = {}
            tid = row['tid']
            team_id = row['team_id']

            t = getTournamentByID(tid)
            team['tournament'] = t.name
            team['t_short_name'] = t.short_name
            team['name'] = t.getTeam(team_id)
            team['team_id'] = team_id
            team['placing'] = t.getPlacingForTeam(team_id)

            if team not in teams:
                # some players are also coaches which cause teams to show up twice
                teams.append(team)

        return teams

    def updateDisplayName(self, new_display_name):
        try:
            new_display_name = str(new_display_name)
            new_display_name = new_display_name.strip()
        except TypeError:
            raise UpdateError("NotString", "Display name cannot be converted to string")

        if len(new_display_name) > 48:
            raise UpdateError("NameToLong", "Display name cannot be greater than 48 characters")

        audit_logger.info("Display name updated for player %s (%s) to %s" % (self.display_name, self.player_id, new_display_name))
        self.display_name = new_display_name
        self.commit()

        return True
