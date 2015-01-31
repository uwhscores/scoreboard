drop table if exists games;
drop table if exists scores;
drop table if exists teams;
drop table if exists tournaments;


CREATE TABLE games(
	tid INTEGER NOT NULL, gid INTEGER NOT NULL, day text, start_time datetime, pool text, black text, white text, type text, division text, pod text, PRIMARY KEY (tid, gid)
);

CREATE TABLE scores(
	tid INTEGER NOT NULL, gid INTEGER NOT NULL, black_tid INTEGER, white_tid INTEGER, score_b INTEGER, score_w INTEGER, 
	pod text, forfeit TEXT, PRIMARY KEY (tid,gid)
);

CREATE TABLE teams(
	tid INTEGER, team_id INTEGER, name Text, division text, PRIMARY KEY(tid, team_id)
);

CREATE TABLE tournaments(
	tid INTEGER PRIMARY KEY, name TEXT, short_name TEXT
);

CREATE TABLE pods(
	tid INTEGER, team_id INTEGER, pod Text, pod_id INTEGER
);

CREATE TABLE rankings(
	tid INTEGER NOT NULL, place text NOT NULL, game text, division text, PRIMARY KEY(tid, place)
);
