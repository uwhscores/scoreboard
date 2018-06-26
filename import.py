#!/usr/bin/python

""" Import script
"""

import os
import sys
import sqlite3
import csv
import re
from datetime import datetime
import ConfigParser
from base64 import b64encode
from os import urandom

class Import(object):

    def __init__(self, db_file):
        if not db_file:
            raise Exception("No DB File")

        self.db = sqlite3.connect(db_file)
        self.db.row_factory = sqlite3.Row

        # self.tid = self.__findTD()
        self.src_folder = None

    def setSource(self, src_folder):
        self.src_folder = src_folder

    def importAll(self, src_folder=None, clear=False):
        if not src_folder:
            src_folder = self.src_folder

        tid = self.__findTID(src_folder)
        if not tid:
            raise Exception("Unable to locate TID")

        if clear:
            self.__clearScores(tid)

        self.src_folder = src_folder

        teams = self.__importTeams(tid)
        self.__importSchedule(tid, teams=teams)
        self.__importPods(tid)
        self.__importGroups(tid)
        self.__importRankings(tid)
        self.__importParams(tid)
        self.__importRosters(tid)

    def __findTID(self, src_folder):
        tid = None
        tid_file = os.path.join(src_folder, "tid")
        tournament_cfg = os.path.join(src_folder, "tournament.cfg")
        if os.path.isfile(tid_file):
            with open(tid_file, 'r') as f:
                line = f.readline()
                try:
                    tid = int(line)
                except ValueError:
                    print "TID file has something other than an integer"
                    # sys.exit(1)
                    return None
        elif os.path.isfile(tournament_cfg):
            t_config = ConfigParser.RawConfigParser()
            t_config.read(tournament_cfg)

            name = t_config.get("tournament", "name")
            short_name = t_config.get("tournament", "short_name")
            start_date = t_config.get("tournament", "start_date")
            end_date = t_config.get("tournament", "end_date")
            location = t_config.get("tournament", "location")

            if not name or not short_name or not start_date or not end_date or not location:
                raise Exception("Tournaments cfg missing reuqired field")

            cur = self.db.execute("SELECT tid FROM tournaments WHERE short_name=?", (short_name,))
            row = cur.fetchone()

            if row:
                return row['tid']
            else:
                cur = self.db.execute("INSERT INTO tournaments(name, short_name, start_date, end_date, location, active) VALUES(?,?,?,?,?,?)",
                                      (name, short_name, start_date, end_date, location, 1))

                self.db.commit()
                cur = self.db.execute("SELECT tid FROM tournaments WHERE short_name=?", (short_name,))
                row = cur.fetchone()

                if row:
                    return row['tid']
                else:
                    raise Exception("Unknown error inserting tournament into DB")
        else:
            print "You need a tid file!"
            # sys.exit(1)
            return None

        cur = self.db.execute('SELECT name FROM tournaments WHERE tid=?', (tid,))
        res = cur.fetchone()

        if res:
            print "\n-- %s --\n" % res['name']
            return tid
        else:
            print "Unkown TID"
            # sys.exit(1)
            return None

    def __clearScores(self, tid):
        print "Clearing out scores ..."
        self.db.execute('DELETE FROM scores WHERE tid=?', (tid,))
        self.db.commit()

        print ("Clearing out parameters ...")
        self.db.execute('DELETE FROM params WHERE tid=?', (tid,))
        self.db.commit()

    def __importSchedule(self, tid, sched_file=None, teams=None):
        sched_file = os.path.join(self.src_folder, "schedule.csv")
        if not os.path.isfile(sched_file):
            return None

        print ("Found a schedule ...")
        cur = self.db.execute('DELETE FROM games WHERE tid=?', (tid,))
        self.db.commit()

        with open(sched_file, 'rb') as f:
            schedule = csv.DictReader(f)
            for row in schedule:
                # print "%s %s vs %s" % (row['gid'], row['black'],
                # row['white'])

                if not row['gid']:
                    continue

                # get the game ID number out of colums like #53
                gid_match = re.match(r".*?(\d+)", row['gid'])
                #import pdb; pdb.set_trace()
                if gid_match:
                    gid = gid_match.group(1)
                    gid = int(gid)
                else:
                    continue

                #print "Working on game %s" % gid
                if re.match('^\d\:\d\d', row['time']) is not None:
                    row['time'] = "0%s" % row['time']

                white = self.__processGame(row['white'], teams)
                black = self.__processGame(row['black'], teams)

                if re.match(r"T[\d+]", white) and re.match(r"T[\d+]", black):
                    white_id = white.split("T")[1]
                    div = teams[white_id]['div']
                    pod = row['white'].split(" ")[0]
                else:
                    div = row['div']
                    pod = row['pod']

                date = datetime.strptime(row['date'], '%m/%d/%y')
                if re.match(r"^\d\d:\d\d$", row['time']):
                    time = datetime.strptime(row['time'], '%H:%M')
                elif re.match(r"^\d\d:\d\d:\d\d$", row['time']):
                    time = datetime.strptime(row['time'], '%H:%M:%S')
                else:
                    print "Error parsing time for gid %s" % gid
                    continue

                start_time = datetime.combine(
                    datetime.date(date), datetime.time(time))

                cur = self.db.execute("INSERT INTO games(tid, gid, day, start_time, pool, black, white, division, pod, type, description) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                      (tid, gid, row['day'], start_time, row['pool'], black, white, div, pod, row['type'], row['desc']))
                self.db.commit()

    def __processGame(self, game_string, teams=None):

        orig_string = game_string

        m = re.match("^(\w+)\s*Seed\s*(\d+)", game_string)
        if m:
            game_string = "S%s%s" % (m.group(1), m.group(2))
            return game_string

        m = re.match("^[l|L].*?(\d+)", game_string)
        if m:
            game_string = "L%s" % m.group(1)
            return game_string

        m = re.match("^[w|W].*?(\d+)", game_string)
        if m:
            game_string = "W%s" % m.group(1)
            return game_string

        pieces = game_string.split()
        if len(pieces) == 2:
            group = pieces[0]
            name = pieces[1]
            #import pdb; pdb.set_trace()
            for team in teams:
                #import pdb; pdb.set_trace()
                if group == "MM" or group == "MW":
                    if teams[team]['short_name'] == name and teams[team]['div'] == group:
                        game_string = "T%s" % team
                elif group == "MA" or group == "MB":
                    if teams[team]['short_name'] == name and teams[team]['div'] == "EM":
                        game_string = "T%s" % team
                elif group == "WA" or group == "WB":
                    if teams[team]['short_name'] == name and teams[team]['div'] == "EW":
                        game_string = "T%s" % team
                else:
                    print "Unknown group? %s " % group
            if not re.match(r"T[\d+]", game_string):
                import pdb; pdb.set_trace()
            return game_string
        else:
            print "Not sure what happened: %s" % pieces

        #import pdb; pdb.set_trace()
        return game_string

    def __importTeams(self, tid, teams_file=None):
        team_file = os.path.join(self.src_folder, "teams.csv")
        if not os.path.isfile(team_file):
            return None

        print "Found list of teams ..."
        cur = self.db.execute('DELETE FROM teams WHERE tid=?', (tid,))
        self.db.commit()


        cur = self.db.execute("SELECT short_name FROM tournaments WHERE tid=?", (tid,))
        tournament = cur.fetchone()

        if tournament:
            short_name = tournament['short_name']
        else:
            short_name = tid

        teams_dict = {}
        with open(team_file, 'rb') as f:
            teams = csv.DictReader(f)
            for row in teams:
                team_id = row['team_id']
                flag_file = "/static/flags/%s/%s.png" % (short_name, team_id)
                # worlds hack, delete me!!
                team_name = "%s %s" % (row['div'], row['name'])

                teams_dict[team_id] = {'name': row['name'], 'short_name': row['short_name'], 'div': row['div']}

                cur = self.db.execute("INSERT INTO teams(tid, team_id, name, short_name, division, flag_file) VALUES(?,?,?,?,?,?)",
                                      (tid, row['team_id'], team_name, row['short_name'], row['div'], flag_file))
                self.db.commit()

        return teams_dict

    def __importRankings(self, tid, rankings_file=None):
        rankings_file = os.path.join(self.src_folder, "rankings.csv")
        if not os.path.isfile(rankings_file):
            return None

        print "Found rankings file ...."
        cur = self.db.execute("DELETE FROM rankings WHERE tid=?", (tid,))
        self.db.commit()

        with open(rankings_file, 'rb') as f:
            rankings = csv.DictReader(f)
            for row in rankings:
                cur = self.db.execute("INSERT INTO rankings(tid, place, game, division) VALUES(?,?,?,?)",
                                      (tid, row['place'], row['game'], row['div']))
                self.db.commit()

    def __importGroups(self, tid, groups_file=None):
        groups_file = os.path.join(self.src_folder, "groups.csv")
        if not os.path.isfile(groups_file):
            return None

        print "Found groups file ...."
        cur = self.db.execute("DELETE FROM groups WHERE tid=?", (tid,))
        self.db.commit()

        with open(groups_file, 'rb') as f:
            groups = csv.DictReader(f)
            for row in groups:
                cur = self.db.execute("INSERT INTO groups(tid,group_id,name) VALUES(?,?,?)",
                                      (tid, row['group_id'], row['name']))
                self.db.commit()

    def __importPods(self, tid, pods_file=None):
        pods_file = os.path.join(self.src_folder, "pods.csv")
        if not os.path.isfile(pods_file):
            return None

        print "Found pods file ..."
        cur = self.db.execute("DELETE FROM pods WHERE tid=?", (tid,))
        self.db.commit()

        with open(pods_file, 'rb') as f:
            pods = csv.DictReader(f)
            for row in pods:
                cur = self.db.execute("INSERT INTO pods(tid, team_id, pod) VALUES(?,?,?)",
                                      (tid, row['team_id'], row['pod']))
                self.db.commit()

    def __importParams(self, tid, params_file=None):
        params_file = os.path.join(self.src_folder, "params.cfg")

        if not os.path.isfile(params_file):
            return None

        print "Found params.cfg ..."
        params = ConfigParser.RawConfigParser()
        params.read(params_file)

        for p in params.items('params'):
            cur = self.db.execute("INSERT INTO params(tid, field, val) VALUES(?,?,?)",
                                  (tid, p[0], p[1]))
            self.db.commit()

    def __importRosters(self, tid, roster_file=None):
        if not roster_file:
            roster_file = os.path.join(self.src_folder, "rosters.csv")
        if not os.path.isfile(roster_file):
            return None

        print "Found rosters file ..."
        cur = self.db.execute("DELETE FROM rosters WHERE tid=?", (tid,))
        self.db.commit()

        with open(roster_file, 'rb') as f:
            rosters = csv.DictReader(f)
            for row in rosters:
                player_name = row['player_name'].strip()
                # strpint non-unicode characters, can't actually do this when I get real names with accents and what not, will need to fix
                # player_name = ''.join([x for x in player_name if ord(x) < 128])
                name_parts = player_name.split(" ")
                last_name = name_parts[-1]
                first_name = " ".join(name_parts[:-1])
                player_name = "%s, %s" % (last_name, first_name)
                # import pdb; pdb.set_trace()
                cur = self.db.execute("SELECT player_id FROM players WHERE display_name=?", (player_name,))
                player = cur.fetchone()
                player_id = None
                if not player:
                    while player_id is None:
                        player_id = self.__genID()
                        self.db.execute("SELECT player_id FROM players WHERE player_id=?", (player_id,))
                        exists = cur.fetchone()
                        if exists:
                            player_id = None

                    self.db.execute("INSERT INTO players (player_id, display_name) VALUES (?,?)", (player_id, player_name))
                    self.db.commit()

                else:
                    player_id = player['player_id']

                cap_number = None
                if re.match(r"\d+", row['cap_number']):
                    cap_number = row['cap_number']

                try:
                    cur = self.db.execute("INSERT INTO rosters (tid, player_id, team_id, cap_number) VALUES (?,?,?,?)", (tid, player_id, row['team_id'], cap_number))
                    self.db.commit()
                except sqlite3.IntegrityError as e:
                    print "Error inserting player %s due to duplicate, team: %s, cap_number: %s" % (player_name, row['team_id'], cap_number)
                    sys.exit(1)

    def __genID(self):
        return b64encode(urandom(6), "Aa")

if __name__ == "__main__":
    """ Main function, uses sys.argv to pull in a directory, defaults to clear contents and full import
    """
    src_folder = None
    try:
        src_folder = sys.argv[1].strip("/")
    except IndexError:
        print "Must give me a directory to import"
        sys.exit(1)

    if os.path.isdir(src_folder):
        print "Importing from directory %s" % src_folder
    else:
        print "Directory doesn't exist %s" % src_folder
        sys.exit(1)

    db_file = os.path.join('app/scores.db')

    importer = Import(db_file)
    importer.setSource(src_folder)
    importer.importAll(clear=True)
    sys.exit(0)
