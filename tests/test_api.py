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
