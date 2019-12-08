import requests
import json
import base64

from scoreboard import functions
from common_functions import connect_db, add_tournament, load_schedule


def test_api_connect(test_client):
    db = connect_db(test_client.application.config['DATABASE'])

    response = test_client.get("/api/v1")
    assert response.status_code == 200
    assert response.is_json
    assert "documentation" in response.json
    assert response.json["documentation"] == "http://docs.uwhscores.apiary.io/"

    add_tournament(db, 1)

    response = test_client.get("/api/v1/tournaments")
    assert response.status_code == 200
    assert response.is_json
    assert "tournaments" in response.json
    assert len(response.json["tournaments"]) > 0
    test_t = response.json["tournaments"][0]
    assert test_t["tid"] == 1
    assert test_t["name"] == "Test Tournament"

    load_schedule("simple", 1, db)

    response = test_client.get("/api/v1/tournaments/1")
    assert response.status_code == 200
    assert response.is_json
    assert "tournament" in response.json

    assert response.json["tournament"]["tid"] == 1


def test_api_auth(test_client):
    db = connect_db(test_client.application.config['DATABASE'])

    new_user = {'email': "test_user@pytest.com", "short_name": "pytest", "site-admin": False, "admin": True}
    res = functions.addUser(new_user, db=db)

    assert res["success"] is True
    user_id = res["user_id"]
    token = res["token"]
    assert user_id is not None
    assert token is not None

    response = test_client.get("login/reset?token=%s" % token)
    assert response.status_code == 200
    assert b"Invalid or missing token" not in response.data

    test_passwd = "temp123!@#"
    response = test_client.post("login/reset", data={"token": token, "password1": test_passwd, "password2": test_passwd}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Something went wrong" not in response.data

    # assert bad token fails
    response = test_client.post("login/reset", data={"token": "kjasdflkj", "password1": test_passwd, "password2": test_passwd}, follow_redirects=True)
    assert response.status_code == 200
    assert b"You go away now" in response.data

    # assert re-using a good token fails
    response = test_client.post("login/reset", data={"token": token, "password1": test_passwd, "password2": test_passwd}, follow_redirects=True)
    assert response.status_code == 200
    assert b"You go away now" in response.data

    valid_credentials = base64.b64encode(b'test_user@pytest.com:temp123!@#').decode('utf-8')

    response = test_client.get("/api/v1/login", headers={'Authorization': 'Basic ' + valid_credentials})
    assert response.status_code == 200
    assert response.is_json
    assert "token" in response.json
    token = response.json["token"]

    valid_credentials = base64.b64encode(b'%b:' % token.encode('utf-8')).decode('utf-8')
    response = test_client.get("/api/v1/login/test", headers={'Authorization': 'Basic ' + valid_credentials})
    assert response.status_code == 200
    assert response.is_json
    assert "message" in response.json
    assert response.json["message"] == "success"

    valid_credentials = base64.b64encode(b'%b:' % token.encode('utf-8')).decode('utf-8')
    response = test_client.get("/api/v1/logout", headers={'Authorization': 'Basic ' + valid_credentials})
    assert response.status_code == 200
    assert response.is_json
    assert "message" in response.json
    assert response.json["message"] == "goodbye"

    valid_credentials = base64.b64encode(b'%b:' % token.encode('utf-8')).decode('utf-8')
    response = test_client.get("/api/v1/login/test", headers={'Authorization': 'Basic ' + valid_credentials})
    assert response.status_code == 401

def test_update_score(test_client):
    db = connect_db(test_client.application.config['DATABASE'])

    response = test_client.get("/api/v1/tournaments/1")
    assert response.status_code == 200
    assert response.is_json
    assert "tournament" in response.json

    assert response.json["tournament"]["tid"] == 1

    response = test_client.get("/api/v1/tournaments/1/games")
    assert response.status_code == 200
    assert response.is_json
    assert "games" in response.json
    games = response.json["games"]
    for game in games:
        assert "gid" in game

    first_game = games[0]
    assert first_game['score_w'] is None
    assert first_game['score_b'] is None

    valid_credentials = base64.b64encode(b'test_user@pytest.com:temp123!@#').decode('utf-8')
    response = test_client.get("/api/v1/login", headers={'Authorization': 'Basic ' + valid_credentials})
    assert response.status_code == 200
    assert response.is_json
    assert "token" in response.json
    token = response.json["token"]
    valid_credentials = base64.b64encode(b'%b:' % token.encode('utf-8')).decode('utf-8')

    # set score of first game
    first_game_score = { "game_score":
                        {
                            "tid": 1,
                            "gid": 1,
                            "score_w": 2,
                            "score_b": 1,
                            "black_id": first_game['black_id'],
                            "white_id": first_game['white_id']
                        }
                    }

    response = test_client.post("/api/v1/tournaments/1/games/1", headers={'Authorization': 'Basic ' + valid_credentials}, json=first_game_score)
    assert response.status_code == 200
    assert response.is_json
    # assert "game" in response.json
    assert response.json['score_w'] == 2
    assert response.json['score_b'] == 1

    # verify score is set by getting it again
    response = test_client.get("/api/v1/tournaments/1/games/1")
    assert response.status_code == 200
    assert response.is_json
    assert "game" in response.json
    game = response.json["game"]
    print(game)
    assert game["score_w"] == 2
    assert game["score_b"] == 1

    # update score again, should be allowed for corrections
    first_game_score = { "game_score":
                        {
                            "tid": 1,
                            "gid": 1,
                            "score_w": 1,
                            "score_b": 3,
                            "black_id": first_game['black_id'],
                            "white_id": first_game['white_id']
                        }
                    }

    response = test_client.post("/api/v1/tournaments/1/games/1", headers={'Authorization': 'Basic ' + valid_credentials}, json=first_game_score)
    assert response.status_code == 200
    assert response.is_json
    # assert "game" in response.json

    response = test_client.get("/api/v1/tournaments/1/games/1")
    assert response.status_code == 200
    assert response.is_json
    assert "game" in response.json
    game = response.json["game"]
    print(game)
    assert game["score_w"] == 1
    assert game["score_b"] == 3

    second_game = games[1]
    assert second_game['score_w'] is None
    assert second_game['score_b'] is None

    second_game_score = { "game_score":
                         {
                                "tid": 1,
                                "gid": 2,
                                "forfeit_w": True,
                                "score_w": 0,
                                "score_b": 0,
                                "black_id": second_game['black_id'],
                                "white_id": second_game['white_id']
                            }
                        }

    response = test_client.post("/api/v1/tournaments/1/games/2", headers={'Authorization': 'Basic ' + valid_credentials}, json=second_game_score)
    print(response.data)
    assert response.status_code == 200
    assert response.is_json
    # assert "game" in response.json

    response = test_client.get("/api/v1/tournaments/1/games/2")
    assert response.status_code == 200
    assert response.is_json
    assert "game" in response.json
    game = response.json["game"]
    print(game)
    assert game["score_w"] == 0
    assert game["score_b"] == 0
    assert game["forfeit"] == "w"
