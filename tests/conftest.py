from scoreboard import create_app
import pytest

from common_functions import create_db


@pytest.fixture
def app():
    app = create_app()
    return app


@pytest.fixture(scope='module')
def test_client(tmpdir_factory):
    print("Creating test_client")
    db_path = tmpdir_factory.mktemp("db").join("test.db")
    create_db(db_path.strpath)

    flask_app = create_app(db_path=db_path.strpath, debug=True)

    # Flask provides a way to test your application by exposing the Werkzeug test Client
    # and handling the context locals for you.
    testing_client = flask_app.test_client()

    # Establish an application context before running the tests.
    ctx = flask_app.app_context()
    ctx.push()

    yield testing_client  # this is where the testing happens!

    ctx.pop()
