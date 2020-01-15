from scoreboard import create_app
import pytest
from common_functions import create_db


@pytest.fixture(scope="session")
def app(request):
    print("[Setup]\tCreating app context")
    app = create_app(db_path="file::memory:", debug=True, testing=True)
    yield app
    print("[Setup]\tDone with app")


@pytest.fixture(autouse=True, scope='module')
def app_context(app):
    """Creates a flask app context"""
    with app.app_context():
        yield app


@pytest.fixture
def request_context(app_context):
    """Creates a flask request context"""
    with app_context.test_request_context():
        yield


@pytest.fixture(scope='module')
def test_client(app, app_context, tmpdir_factory):
    db_path = tmpdir_factory.mktemp("db").join("test.db")
    print("[Setup]\tCreating test_client: db path: %s" % db_path)
    create_db(db_path.strpath)

    app.config['DATABASE'] = db_path.strpath
    app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = False

    yield app.test_client()
