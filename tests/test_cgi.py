from common_functions import connect_db
from scoreboard.models import Player


def test_search_player(test_client):
    db = connect_db(test_client.application.config['DATABASE'])
    print("DB path: %s" % test_client.application.config['DATABASE'])

    # one player, detailed test
    player_1 = Player(db, "Bob Dole")
    player_1.commit()
    response = test_client.get("/cgi/search?entity=players&like=bob")
    assert response.status_code == 200
    assert response.is_json
    assert "results" in response.json
    results = response.json["results"]
    assert len(results) > 0
    assert len(results) == 1
    first_result = results[0]
    assert isinstance(first_result, dict)
    assert "display_name" in first_result
    assert "player_id" in first_result
    assert first_result["display_name"] == "Bob Dole"
    assert first_result["player_id"] == player_1.player_id

    # add a second player and make sure they both return
    player_2 = Player(db, "Bob Ross")
    player_2.commit()
    response = test_client.get("/cgi/search?entity=players&like=bob")
    results = response.json["results"]
    assert len(results) == 2
    assert results[0]["display_name"] == "Bob Dole"
    assert results[1]["display_name"] == "Bob Ross"

    # search name that should have no results
    response = test_client.get("/cgi/search?entity=players&like=jill")
    results = response.json["results"]
    assert len(results) == 0


def test_search_errors(test_client):
    # test search called with no entity
    response = test_client.get("/cgi/search")
    assert response.status_code == 400
    assert response.is_json
    assert "message" in response.json
    assert response.json["message"] == "Missing required field"

    response = test_client.get("/cgi/search?entity=teams&like=minnesota")
    assert response.status_code == 501
    assert response.is_json
    assert "message" in response.json
    assert response.json["message"] == "Not implemented"

    response = test_client.get("/cgi/search?entity=people&like=jim")
    assert response.status_code == 400
    assert response.is_json
    assert "message" in response.json
    assert response.json["message"] == "Unknown entity"
