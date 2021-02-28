from datetime import datetime, timedelta
from freezegun import freeze_time
import pytest

from common_functions import connect_db
from scoreboard import functions
from scoreboard.models import User
from scoreboard.exceptions import UpdateError


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
