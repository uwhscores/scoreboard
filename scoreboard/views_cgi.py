from flask import current_app as app
from flask import request, jsonify
from scoreboard.functions import searchPlayers
from scoreboard.exceptions import InvalidUsage


@app.route('/cgi/search')
def cgiSearch():
    entity = None
    search_like = None

    entity = request.args.get('entity')
    search_like = request.args.get('like')

    if not (entity and search_like):
        raise InvalidUsage("Missing required field", status_code=400)

    if len(search_like) < 3:
        raise InvalidUsage("Search string too short", status_code=400)

    results = []
    if entity == "players":
        results = searchPlayers(search_like)
    elif entity == "teams" or entity == "tournaments":
        raise InvalidUsage("Not implemented", status_code=501)
    else:
        raise InvalidUsage("Unknown entity", status_code=400)

    return jsonify(results=results)
