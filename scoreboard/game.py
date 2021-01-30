from datetime import datetime
from flask import current_app as app
import json
import re

from scoreboard import functions

def getPodID(a, b):
    """ Leftover function from original Nationals Pod Logic """
    return -1

def getTeam(a):
    """ Leftover function from original Nationals Pod Logic """
    return -1

class Game(object):

    def __init__(self, tournament, gid, day, start_datetime, pool, black, white, game_type, division, pod, description):
        self.tournament = tournament
        self.gid = gid
        self.black_tid = None
        self.white_tid = None
        #self.day = day

        self.start_datetime = datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S')
        if self.tournament.use_24hour:
            self.start_time = datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
        else:
            self.start_time = datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S').strftime('%I:%M %p')

        day_names = ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]
        self.day = "%s-%s" % (day_names[self.start_datetime.weekday()], functions.ordinalize(self.start_datetime.day))
        self.pool = pool
        self.game_type = game_type
        self.division = division
        self.pod = pod
        self.description = description

        # functionality existed before refactor, maybe add it back in later
        self.pod_color = None
        if self.pod:
            self.pod_color = tournament.getGroupColor(pod)

        self.pod_name = tournament.expandGroupAbbr(self.pod)
        self.division_name = tournament.expandGroupAbbr(self.division)

        # pull the record from the scores table, if it exists use that data to fill in the game
        db = tournament.db
        cur = db.execute('SELECT black_tid, white_tid, score_b, score_w, forfeit FROM scores WHERE gid=? AND tid=?', (self.gid, tournament.tid))
        score = cur.fetchone()


        self.style_b = ""
        self.style_w = ""
        self.note_b = None
        self.note_w = None
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
            try:
                (self.black_tid, self.black, self.style_b) = self.__processGameJSON(black)
            except json.decoder.JSONDecodeError:
                app.logger.debug(f"Failure decoding JSON for black: {self.tournament.short_name}:{self.gid} - {black}")
                self.black = "Error with Game!"

            try:
                (self.white_tid, self.white, self.style_w) = self.__processGameJSON(white)
            except json.decoder.JSONDecodeError:
                app.logger.debug(f"Failure decoding JSON for white: {self.tournament.short_name}:{self.gid} - {black}")
                self.white = "Error with Game!"

        self.black_flag = tournament.getTeamFlag(self.black_tid)
        self.white_flag = tournament.getTeamFlag(self.white_tid)

        self.timing_rules = self.tournament.getTimingRules(self.game_type)

    def __repr__(self):
        return "{}: {} {} - {} vs {}".format(self.gid, self.day, self.start_time, self.black, self.white)

    def serialize(self):
        score_b = self.score_b
        if not isinstance(score_b, int):
            score_b = None

        score_w = self.score_w
        if not isinstance(score_w, int):
            score_w = None

        description = self.description
        if description == "":
            description = None

        # refresh timing rules incase there were changes
        timing_rules = self.tournament.getTimingRules(self.game_type)

        return {
            'tid': self.tournament.tid,
            'gid': self.gid,
            'day': self.day,
            'pool': self.pool,
            'start_time': self.start_datetime.isoformat(),
            'black': self.black,
            'black_id': self.black_tid,
            'note_b': self.note_b,
            'white': self.white,
            'white_id': self.white_tid,
            'note_w': self.note_w,
            'score_b': score_b,
            'score_w': score_w,
            'forfeit': self.forfeit,
            'timing_rules': timing_rules,
            'game_type': self.game_type,
            'description': description
        }

    # loops through all games and creates expanded dictionary of games
    # expands database short hand into human readable form
    def expandGames(self, games):
        expanded = []

        return expanded

    def __processGameJSON(self, game_json):
        """ Expand the JSON that defines a game into either a specific team or a description of the game

        """
        style = ""
        team_id = None

        game = json.loads(game_json)

        game_type = game['type']

        if game_type == 'team':
            # straight up team in schedule, pull team name
            team_id = game['team_id']
            game_text = self.tournament.getTeam(team_id)
            # team names might not be defined, in this case just make it "Team #"
            if not game:
                game_text = f"Team {team_id}"
                style = "soft"

        elif game_type == "redraw":
            # redraw place holder in schedule
            # currently not implimented by leaving parser here
            game_text = f"Redraw {game['group']} - {game['number']}"
            style = "soft"

        elif game_type == "seed":
            group_abriviation = game['group']
            seed = game['seed']
            # app.logger.debug("Matching pod or division - %s" % group_abriviation)
            # app.logger.debug("Seed notation: group= %s, seed= %s" % (group_abriviation, seed))

            if group_abriviation in self.tournament.getPods():
                team_id = self.tournament.getSeed(seed, pod=group_abriviation)
            elif group_abriviation in self.tournament.getDivisions():
                team_id = self.tournament.getSeed(seed, division=group_abriviation)

            group = self.tournament.expandGroupAbbr(group_abriviation)
            if not group:
                group = group_abriviation

            if team_id:
                team = self.tournament.getTeam(team_id)
                if group:
                    game_text = f"{team} ({group}-{seed})"
            else:
                game_text = f"{group} Seed {seed}"
                style = "soft"

        elif game_type == "winner":
            gid = game['game']
            team_id = self.tournament.getWinner(gid)
            if (team_id == -1):
                game_text = f"Winner of {gid}"
                style = "soft"
            elif (team_id == -2):
                game_text = f"TIE IN GAME {gid}!!"
            else:
                team = self.tournament.getTeam(team_id)
                game_text = f"{team} (W{gid})"

        elif game_type == "loser":
            gid = game['game']
            team_id = self.tournament.getLoser(gid)
            if (team_id == -1):
                game_text = f"Loser of {gid}"
                style = "soft"
            elif (team_id == -2):
                game_text = f"TIE IN GAME {gid}!!"
            else:
                team = self.tournament.getTeam(team_id)
                game_text = f"{team} (L{gid})"

        elif game_type == "nongame":
            game_text = game['text']
            style = "nongame"
        else:
            game_text = "Error with game!"

        if team_id:
            team_id = int(team_id)

        return (team_id, game_text, style)
