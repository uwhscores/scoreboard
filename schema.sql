CREATE TABLE games(
	tid INTEGER NOT NULL, gid INTEGER NOT NULL, day text, start_time time, pool text, black text, white text, type text, division text, pod text, description text, PRIMARY KEY (tid, gid)
);
CREATE TABLE scores(
	tid INTEGER NOT NULL, gid INTEGER NOT NULL, black_tid INTEGER, white_tid INTEGER, score_b INTEGER, score_w INTEGER, pod text, forfeit TEXT, PRIMARY KEY (tid,gid)
);
CREATE TABLE tournaments(
	tid INTEGER PRIMARY KEY, name TEXT, short_name TEXT
, start_date datetime, end_date datetime, location TEXT);
CREATE TABLE teams(
tid INTEGER, team_id INTEGER, name Text, division text, PRIMARY KEY(tid, team_id)
);
CREATE TABLE pods(
tid INTEGER, team_id INTEGER, pod Text, pod_id INTEGER
);
CREATE TABLE rankings(
        tid INTEGER NOT NULL, place text NOT NULL, game text, division text, PRIMARY KEY(tid, place)
);
CREATE INDEX time_index ON games (start_time);
CREATE TABLE params(
tid INTEGER NOT NULL, field text NOT NULL, val NOT NULL
);
CREATE TABLE groups(
tid INTEGER NOT NULL, group_id text NOT NULL, name text NOT NULL, PRIMARY KEY(tid, group_id)
);
CREATE UNIQUE INDEX unique_name on tournaments(short_name);
