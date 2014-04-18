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

@app.template_filter('expand')
def expand_game(g):
	match = re.search( '^S(\d+)$' )
	if match:
		g = "Seed " . match.group(1)

	return g


@app.route('/')
def render_main():
	db = get_db()
	cur = db.execute('SELECT gid, day, start_time, black, white FROM games WHERE tid=? ORDER BY gid',app.config['TID'])
	games = cur.fetchall()

	cur = db.execute('select name from teams WHERE tid=?', app.config['TID'])
	teams = cur.fetchall()

	return render_template('show_main.html', teams=teams, games=games)


if __name__ == '__main__':
	app.run(host='0.0.0.0')
