import re

from common_functions import connect_db, add_tournament, load_schedule
from scoreboard import functions


def test_admin_connect(test_client):
    db = connect_db(test_client.application.config['DATABASE'])

    # connect without login, should be redirected
    response = test_client.get("/admin")
    assert response.status_code == 302
    assert "/login" in response.location

    test_client.application.config['TESTING'] = True

    new_user = {'email': "test_user@pytest.com", "short_name": "pytest", "site_admin": False, "admin": True}
    res = functions.addUser(new_user, db=db)

    assert res["success"] is True
    user_id = res["user_id"]
    token = res["token"]
    assert user_id is not None
    assert token is not None

    test_user = functions.getUserByID(user_id)
    test_user.setPassword("pytest123")

    response = test_client.post("/login",  data={'email': "test_user@pytest.com", 'password': "pytest123"})
    print(response.location)
    assert response.status_code == 302
    assert "/admin" in response.location

    response = test_client.get("/admin")
    assert response.status_code == 200


def test_admin_users(test_client):

    #
    # Creation tests
    #
    new_user1 = {
                "email": "test01@test.com",
                "short_name": "test01",
                "admin": False
                }

    # test that create fails for non-logged in user
    response = test_client.post("/admin/users", json={'user': new_user1})
    assert response.status_code == 403

    # re-use admin user from previous test
    test_user_id = functions.getUserID("test_user@pytest.com")
    test_user = functions.getUserByID(test_user_id)
    assert test_user_id is not None

    # login user
    response = test_client.post("/login",  data={'email': "test_user@pytest.com", 'password': "pytest123"})
    assert response.status_code == 302

    # try creating again, still fail cause user is not site-admin
    response = test_client.post("/admin/users", json={'user': new_user1})
    assert response.status_code == 403

    test_user.setSiteAdmin(True)
    response = test_client.post("/admin/users", json={'user': new_user1})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['user']['token'] is not None

    new_user1_id = functions.getUserID("test01@test.com")
    assert new_user1_id is not None
    new_user1_obj = functions.getUserByID(new_user1_id)
    assert new_user1_obj is not None
    # user shouldn't have any elevated privilages
    assert new_user1_obj.admin is False
    assert new_user1_obj.site_admin is False

    # test missing elements rejected
    bad_user = {
        "email": "new_email@test.com",
    }
    response = test_client.post("/admin/users", json={'user': bad_user})
    assert response.is_json
    assert response.status_code == 400
    assert "message" in response.json
    # error response should tell us what field we're missing
    assert "short_name" in response.json['message']

    # test bad email
    bad_user = {
        "email": "notanemail@1",
        "short_name": "bademail"
    }
    response = test_client.post("/admin/users", json={'user': bad_user})
    assert response.is_json
    assert response.status_code == 400
    assert "message" in response.json
    assert response.json['message'] == "Email address does not pass validation"

    # test duplicate email rejected
    bad_user = {
        "email": "test01@test.com",
        "short_name": "new"
    }
    response = test_client.post("/admin/users", json={'user': bad_user})
    assert response.is_json
    assert response.status_code == 400
    assert "Email already exists" in response.json['message']

    # test create  user who is admin directly
    new_user2 = {
                "email": "test02@test.com",
                "short_name": "test02",
                "admin": True
                }
    response = test_client.post("/admin/users", json={'user': new_user2})
    assert response.status_code == 200
    assert response.json['success'] is True

    new_user2_id = functions.getUserID("test02@test.com")
    assert new_user2_id is not None
    new_user2_obj = functions.getUserByID(new_user2_id)
    assert new_user2_obj is not None
    assert new_user2_obj.admin is True
    assert new_user2_obj.site_admin is False

    #
    # Update tests
    #

    # test promote user1 to admin
    new_user1 = {
                "user_id": new_user1_id,
                "admin": True
                }
    assert new_user1_obj.admin is False
    response = test_client.put(f"/admin/users/{new_user1_id}", json={'user': new_user1})
    assert response.status_code == 200
    assert response.json['success'] is True
    new_user1_obj = functions.getUserByID(new_user1_id)
    assert new_user1_obj.admin is True

    # bad update
    new_user1 = {
                "user_id": new_user1_id,
                "admin": "True"
                }
    response = test_client.put(f"/admin/users/{new_user1_id}", json={'user': new_user1})
    assert response.status_code == 400
    assert "type boolean" in response.json['message']

    # test deactive user1
    new_user1 = {
                "user_id": new_user1_id,
                "active": False
                }
    assert new_user1_obj.active is True
    response = test_client.put(f"/admin/users/{new_user1_id}", json={'user': new_user1})
    assert response.status_code == 200
    assert response.json['success'] is True
    new_user1_obj = functions.getUserByID(new_user1_id)
    assert new_user1_obj.active is False

    # test password reset
    new_user1 = {
                "user_id": new_user1_id,
                "reset_password": True
                }
    response = test_client.put(f"/admin/users/{new_user1_id}", json={'user': new_user1})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert "token" in response.json
    print(response.json)
    reset_token = response.json['token']
    assert reset_token is not None

    reset_id = functions.validateResetToken(reset_token)
    assert reset_id is not None
    assert reset_id == new_user1_id

    # kidnof a random test case but make sure that a None token doesn't resolve to any user ID
    reset_id = functions.validateResetToken(None)
    assert reset_id is None

def test_score_update(test_client):
    # need a tournament with some games to update
    short_name = "pytest"
    db = connect_db(test_client.application.config['DATABASE'])
    test_t = add_tournament(db, 1, short_name=short_name)
    load_schedule("simple", 1, db)

    # re-use admin user from previous test
    test_user_id = functions.getUserID("test_user@pytest.com")
    assert test_user_id is not None

    # first game to update
    gid = 1
    score = {'score_w': 1, 'score_b': 2, 'forfeit_w': False, 'forfeit_b': False}

    # normal update, should succeed
    response = test_client.put(f"/admin/t/{short_name}/games/{gid}", json={'score': score})
    assert response.status_code == 200
    assert 'url' in response.json
    assert re.match(f".*/admin/t/{short_name}/games$", response.json['url'])
    game = test_t.getGame(1)
    assert game is not None
    assert game.score_w == 1
    assert game.score_b == 2
    assert game.forfeit is None

    score = {'score_w': 3, 'score_b': 2, 'forfeit_w': False, 'forfeit_b': False}

    # test updating an existing game
    response = test_client.put(f"/admin/t/{short_name}/games/{gid}", json={'score': score})
    assert response.status_code == 200
    assert re.match(f".*/admin/t/{short_name}/games$", response.json['url'])
    game = test_t.getGame(1)
    assert game is not None
    assert game.score_w == 3
    assert game.score_b == 2
    assert game.forfeit is None

    # test some bad input
    score_bad = {'not': 1, 'score_b': 2, 'forfeit_w': False, 'forfeit_b': False}
    response = test_client.put(f"/admin/t/{short_name}/games/{gid}", json={'score': score_bad})
    assert response.status_code == 400

    score_bad = {'score_w': 0, 'score_b': 0, 'forfeit_w': True, 'forfeit_b': True}
    response = test_client.put(f"/admin/t/{short_name}/games/{gid}", json={'score': score_bad})
    assert response.status_code == 200  # there is a todo to fix this, so at some point this will be 400
    assert 'success' in response.json
    assert response.json['success'] is False

    response = test_client.put(f"/admin/t/{short_name}/games/{gid}", json={})
    assert response.status_code == 400

    response = test_client.put(f"/admin/t/{short_name}/games/100", json={'score': score_bad})
    assert response.status_code == 404


def test_tournament_config(test_client):

    test_t = functions.getTournamentByID(1)
    assert test_t is not None

    response = test_client.get(f"/t/{test_t.short_name}")
    assert response.status_code == 200

    # re-use admin user from previous test
    test_user_id = functions.getUserID("test_user@pytest.com")
    assert test_user_id is not None

    # normal tournament banner enable
    banner = {"config_name": "banner", "banner": {"enabled": True, "message": "averyuniquestringicansearchfor"}}

    response = test_client.put(f"/admin/t/{test_t.short_name}", json=banner)
    assert response.status_code == 200
    print(response.json)
    assert response.json['success'] is True
    site_message = test_t.getSiteMessage()
    assert site_message == "averyuniquestringicansearchfor"
    response = test_client.get(f"/t/{test_t.short_name}")
    assert response.status_code == 200
    assert b"averyuniquestringicansearchfor" in response.data

    # normal tournament banner disable
    banner = {"config_name": "banner", "banner": {"enabled": False, "message": "averyuniquestringicansearchfor"}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=banner)
    assert response.status_code == 200
    assert response.json['success'] is True
    site_message = test_t.getSiteMessage()
    assert site_message is None
    response = test_client.get(f"/t/{test_t.short_name}")
    assert response.status_code == 200
    assert b"averyuniquestringicansearchfor" not in response.data

    # bad tournament banner, missing message
    banner = {"config_name": "banner", "banner": {"enabled": True, "message": None}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=banner)
    assert response.status_code == 400
    assert response.json['success'] is False
    assert "message" in response.json
    # bad tournament banner, empty string
    banner = {"config_name": "banner", "banner": {"enabled": True, "message": ""}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=banner)
    assert response.status_code == 400
    assert response.json['success'] is False
    assert "message" in response.json

    # normal tournameent blackout
    blackout_message = "adifferentuniquestringthaticansearchfor"
    blackout = {"config_name": "blackout", "blackout": {"enabled": True, "message": blackout_message}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=blackout)
    assert response.status_code == 200
    assert response.json['success'] is True
    blackout_status = test_t.getBlackoutMessage()
    assert blackout_status == blackout_message
    response = test_client.get(f"/t/{test_t.short_name}")
    assert response.status_code == 200
    assert b"" in response.data

    # normal tournament blackout clear
    blackout = {"config_name": "blackout", "blackout": {"enabled": False, "message": None}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=blackout)
    assert response.status_code == 200
    assert response.json['success'] is True

    blackout_status = test_t.getBlackoutMessage()
    assert blackout_status is None
    response = test_client.get(f"/t/{test_t.short_name}")
    assert response.status_code == 200
    assert blackout_message.encode() not in response.data

    # normal tie break add
    tie_break_config = {"config_name": "tie_break", "tie_break": {"teams": [1, 2], "winner": 2}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=tie_break_config)
    assert response.status_code == 200
    tie_break = test_t.getTieBreak(1, 2)
    assert tie_break is not None
    assert tie_break == 2

    # duplicate should fail
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=tie_break_config)
    assert response.status_code == 400
    assert response.json['success'] is False

    # test finalize w/o all scores being entered, expect failure
    finalize_config = {"config_name": "finalize", "finalize": {"finalize": True}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=finalize_config)
    assert response.status_code == 400
    assert response.json['success'] is False

    # test making a user a tournament admin and removing
    # need a user to test with
    helper_user = {
                "email": "helper@example.com",
                "short_name": "helper",
                "admin": False
                }

    response = test_client.post("/admin/users", json={'user': helper_user})
    assert response.status_code == 200
    assert response.json['success'] is True
    helper_user_id = response.json['user']['user_id']
    assert helper_user_id is not None

    authorized_ids = test_t.getAuthorizedUserIDs()
    assert helper_user_id not in authorized_ids

    make_admin = {'config_name': 'admin', 'admin': {'make_admin': True, 'user_id': helper_user_id}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=make_admin)
    assert response.status_code == 200
    assert response.json['success'] is True

    authorized_ids = test_t.getAuthorizedUserIDs()
    assert helper_user_id in authorized_ids

    unmake_admin = {'config_name': 'admin', 'admin': {'make_admin': False, 'user_id': helper_user_id}}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=unmake_admin)
    assert response.status_code == 200
    assert response.json['success'] is True

    authorized_ids = test_t.getAuthorizedUserIDs()
    assert helper_user_id not in authorized_ids

    # various failure test cases
    bad_config = {}
    response = test_client.put(f"/admin/t/{test_t.short_name}", json=bad_config)
    assert response.status_code == 400
    assert response.json['success'] is False
    response = test_client.put(f"/admin/t/{test_t.short_name}")
    assert response.status_code == 400
    assert response.json['success'] is False
    response = test_client.put(f"/admin/t/{test_t.short_name}", data="text")
    assert response.status_code == 400
    assert response.json['success'] is False
    response = test_client.put(f"/admin/t/{test_t.short_name}", json={"config_name": "bob"})
    assert response.status_code == 400
    assert response.json['success'] is False
    response = test_client.put(f"/admin/t/notatournament", json={"config_name": "banner", "banner": {"enabled": True, "message": "testytest"}})
    assert response.status_code == 404
    assert response.json['success'] is False
