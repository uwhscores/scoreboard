import os
import sqlite3
import re
from flask import Flask, request, session, g, redirect, url_for, abort, \
	render_template, flash

app = Flask(__name__)
app.config.from_object(__name__)

app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'scores.db'),
	DEBUG=True,
	SECRET_KEY='testkey',
	USERNAME='admin',
	PASSWORD='default',
	TID='1'
))

app.config.from_envvar('SCOREBOARD_SETTINGS', silent=True)

def connect_db():
	rv = sqlite3.connect(app.config['DATABASE'])
	rv.row_factory = sqlite3.Row
	return rv

def get_db():
	if not hasattr(g, 'sqlite_db'):
		g.sqlite_db = connect_db()
	return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
	if hasattr(g, 'sqlite_db'):
		g.sqlite_db.close()

def get_team(team_id):
	db = get_db()
	cur = db.execute('SELECT name FROM teams WHERE team_id=? AND tid=?', (team_id, app.config['TID']))
	team = cur.fetchone()

	return team['name']

def parse_game(g):
	game = g

	match = re.search( '^T(\d+)$', g)
	if match:
		game = get_team(match.group(1))

	match = re.search( '^S(\d+)$', g )
	if match:
		game = "Seed " + match.group(1)
	
	match = re.search( '^W(\d+)$', g)
	if match:
		game = "Winner of " + match.group(1)

	match = re.search( '^L(\d+)$', g)
	if match:
		game = "Looser of " + match.group(1)

	return game

def expand_games(games):
	expanded = []
	db = get_db()
	
	for info in games:
		game = {}
		game["gid"] = info['gid']
		game["day"] = info['day']
		game["start_time"] = info['start_time']
		game["black"] = parse_game(info['black'])
		game["white"] = parse_game(info['white'])

		cur = db.execute('SELECT score_b, score_w FROM scores WHERE gid=? AND tid=?', (game['gid'],app.config['TID']))
		score = cur.fetchone()

		if score:
			game['score_b'] = score['score_b']		
			game['score_w'] = score['score_w']
		else:
			game['score_b'] = "--"
			game['score_w'] = "--"
		
		expanded.append(game)

	return expanded 
		


@app.route('/')
def render_main():
	db = get_db()
	cur = db.execute('SELECT gid, day, start_time, black, white FROM games WHERE tid=? ORDER BY gid',app.config['TID'])
	games = expand_games(cur.fetchall())

	cur = db.execute('select name from teams WHERE tid=?', app.config['TID'])
	teams = cur.fetchall()

	return render_template('show_main.html', teams=teams, games=games)


if __name__ == '__main__':
	app.run(host='0.0.0.0')
