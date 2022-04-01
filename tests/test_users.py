from datetime import datetime, timedelta
from freezegun import freeze_time
import pytest

from common_functions import connect_db
from scoreboard import functions
from scoreboard.models import User
from scoreboard.exceptions import UpdateError, UserAuthError


def test_user_creates(test_client):
    db = connect_db(test_client.application.config['DATABASE'])

    new_user = {'email': "test_user@pytest.com", "short_name": "pytest", "site_admin": False, "admin": True}
    user = User.create(new_user, db=db)

    assert user.user_id is not None
    assert user.email == "test_user@pytest.com"
    assert user.short_name == "pytest"
    assert user.active is True
    assert user.admin is True
    assert user.site_admin is False

    # creating a new user creates an initial password reset token that can be retrieved with getResetToken()
    first_token = user.getResetToken()
    assert first_token is not None
    assert isinstance(first_token, str)
    assert len(first_token) > 20

    found_user_id = functions.validateResetToken(first_token)
    assert found_user_id == user.user_id

    # assert duplicate user create fails
    with pytest.raises(UpdateError) as create_error:
        new_user = {'email': "test_user@pytest.com", "short_name": "new_shortname", "site_admin": False, "admin": True}
        user = User.create(new_user, db=db)

    assert create_error.type is UpdateError
    assert create_error.value.error == "emailexists"
    assert "Email already exists" in create_error.value.message

    with pytest.raises(UpdateError) as create_error:
        new_user = {'email': "new_email@pytest.com", "short_name": "pytest", "site_admin": False, "admin": True}
        user = User.create(new_user, db=db)

    assert create_error.type is UpdateError
    assert create_error.value.error == "namexists"
    assert "Short name" in create_error.value.message

    # test user lookup functions
    user_id = functions.getUserID("test_user@pytest.com")
    assert user_id is not None
    assert user_id == user.user_id

    new_obj = functions.getUserByID(user_id)
    assert new_obj.user_id == user.user_id


def test_user_authentication(test_client):
    db = connect_db(test_client.application.config['DATABASE'])

    test_email = "auth_test@pytest.com"
    new_user = {'email': test_email, "short_name": "authtest", "site_admin": False, "admin": False}
    user = User.create(new_user, db=db)

    test_password = "testingpassword"
    user.setPassword(test_password)

    authed_id = functions.authenticate_user(test_email, test_password)
    assert authed_id == user.user_id

    with pytest.raises(UserAuthError) as auth_error:
        authed_id = functions.authenticate_user(test_email, "badpassword")

    assert auth_error.value.error == "FAIL"
    assert auth_error.value.message == "Incorrect password"

    # test user lockout
    # first log the user in succesfully to reset counters
    authed_id = functions.authenticate_user(test_email, test_password)
    assert authed_id == user.user_id
    for x in range(0, 11):
        with pytest.raises(UserAuthError) as auth_error:
            authed_id = functions.authenticate_user(test_email, "badpassword")

        assert auth_error.value.error == "FAIL"
        assert auth_error.value.message == "Incorrect password"

    with pytest.raises(UserAuthError) as auth_error:
        authed_id = functions.authenticate_user(test_email, "badpassword")

    assert auth_error.value.error == "LOCKED"
    assert "Account locked" in auth_error.value.message

    # resetting the user password should reset the lock
    user.setPassword("mynewpassword")
    authed_id = functions.authenticate_user(test_email, "mynewpassword")
    assert authed_id == user.user_id


def test_password_resets(test_client):
    db = connect_db(test_client.application.config['DATABASE'])

    new_user = {'email': "test_pwreset@pytest.com", "short_name": "resetme", "site_admin": False, "admin": True}
    user = User.create(new_user, db=db)

    # do a pssword reset and validate that a new token
    reset_token = user.createResetToken()
    assert reset_token is not None
    assert user.getResetToken() == reset_token

    found_user_id = functions.validateResetToken(reset_token)
    assert found_user_id == user.user_id

    # validate token exipres after 24 hours
    later = datetime.utcnow() + timedelta(days=0, hours=23)
    with freeze_time(later):
        found_user_id = functions.validateResetToken(reset_token)
        assert found_user_id == user.user_id

    much_later = datetime.utcnow() + timedelta(days=1, seconds=1)
    with freeze_time(much_later):
        found_user_id = functions.validateResetToken(reset_token)
        assert found_user_id is None

    # validate that a none token doesn't resolve to user
    reset_id = functions.validateResetToken(None)
    assert reset_id is None

    # make sure we didn't totally screw up and that something else doesn't return as valid
    reset_id = functions.validateResetToken("thisisnotatoken")
    assert reset_id is None

    # setting a password should clear out the reset token
    user.setPassword("somenewstring")
    user.getResetToken() is None

    # test that you can't get a valid reset token on an inactive account
    user.setActive(False)
    assert user.active is False
    token = user.createResetToken()
    found_user_id = functions.validateResetToken(token)
    assert found_user_id is None

    # test that an admin reset enables the account
    user.setActive(False)
    assert user.active is False
    token = user.createResetToken(by_admin=True)
    found_user_id = functions.validateResetToken(token)
    assert found_user_id == user.user_id

    # teest bad passwords
    # test_pwreset@pytest.com
    with pytest.raises(UpdateError) as e:
        user.setPassword("test_pwreset@pytest.com")
    assert e.value.error == "badpassword"
    assert e.value.message == "Cannot use email address in password"

    with pytest.raises(UpdateError) as e:
        user.setPassword("Test_PWreset@pytest.com1!")
    assert e.value.error == "badpassword"
    assert e.value.message == "Cannot use email address in password"

    with pytest.raises(UpdateError) as e:
        user.setPassword("uwhscoresRocks!")
    assert e.value.error == "badpassword"
    assert e.value.message == "Cannot use uwhscores in password"
