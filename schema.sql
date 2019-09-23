CREATE TABLE games(
	tid INTEGER NOT NULL,
	gid INTEGER NOT NULL,
	day text,
	start_time time,
	pool text,
	black text,
	white text,
	type text,
	division text,
	pod text,
	description text,
	PRIMARY KEY (tid, gid)
);
CREATE INDEX time_index ON games (start_time);

CREATE TABLE scores(
	tid INTEGER NOT NULL,
	gid INTEGER NOT NULL,
	black_tid INTEGER,
	white_tid INTEGER,
	score_b INTEGER,
	score_w INTEGER,
	pod text,
	forfeit TEXT,
	PRIMARY KEY (tid,gid)
);

CREATE TABLE tournaments(
	tid INTEGER PRIMARY KEY,
	name TEXT,
	short_name TEXT,
	start_date datetime,
	end_date datetime,
	location TEXT,
	active INTEGER
);
CREATE UNIQUE INDEX unique_name on tournaments(short_name);

CREATE TABLE teams(
	tid INTEGER,
	team_id INTEGER,
	name Text,
	short_name Text,
	division text,
	flag_file text,
	PRIMARY KEY(tid, team_id)
);

CREATE TABLE pods(
	tid INTEGER,
	team_id INTEGER,
	pod Text,
	pod_id INTEGER
);

CREATE TABLE rankings(
		tid INTEGER NOT NULL,
		place text NOT NULL,
		game text,
		division text
);


CREATE TABLE params(
	tid INTEGER NOT NULL,
	field text NOT NULL,
	val NOT NULL
);

CREATE TABLE groups(
	tid INTEGER NOT NULL,
	group_id text NOT NULL,
	name text NOT NULL,
	group_color text,
	pod_round integer,
	PRIMARY KEY(tid, group_id)
);

CREATE TABLE users (
	user_id TEXT PRIMARY KEY,
	short_name TEXT NOT NULL,
	email TEXT NOT NULL UNIQUE,
	password TEXT NOT NULL,
	date_created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
	last_login timestamp NULL DEFAULT NULL,
	failed_logins INTEGER NOT NULL DEFAULT 0,
	active INTEGER NOT NULL DEFAULT 0,
	site_admin INTEGER NOT NULL DEFAULT 0,
	admin INTEGER NOT NULL DEFAULT 0,
	passwd_reset INTEGER NOT NULL DEFAULT 0,
    reset_token TEXT
);

CREATE TABLE tokens (
	token TEXT PRIMARY KEY,
	user_id TEXT NOT NULL,
	valid_til timestampt NOT NULL
);

CREATE TABLE players (
	player_id TEXT PRIMARY KEY,
	surname TEXT,
	first_name TEXT,
	display_name TEXT,
	date_created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rosters (
	tid INTEGER NOT NULL,
	player_id TEXT NOT NULL,
	team_id INTEGER NOT NULL,
	cap_number INTEGER,
	is_coach INTEGER DEFAULT 0,
	coach_title TEXT,
	PRIMARY KEY(tid, player_id)
);
