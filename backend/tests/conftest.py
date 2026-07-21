import pytest

from app import create_app, db as _db
from config import Config


@pytest.fixture
def app():
    """Flask app context — enough for code that reads current_app.config.

    Nothing here touches the database, so no real DB/Redis is needed.
    """
    flask_app = create_app()
    with flask_app.app_context():
        yield flask_app


class _TestConfig(Config):
    # In-memory, not the real /app/data/annex.db -- set on the config class
    # (not app.config post-hoc) since Flask-SQLAlchemy reads the URI at
    # db.init_app(app) time, inside create_app().
    SQLALCHEMY_DATABASE_URI = "sqlite://"


@pytest.fixture
def db_app():
    """Like `app`, but backed by a real in-memory SQLite DB (db.create_all()
    run inside the app context). First DB-backed fixture in this suite --
    the plain `app` fixture above explicitly promises no DB touch, so tests
    that read/write Import/ShadowMatch rows (Phase 4a's migration, shadow
    task, and summary route) use this one instead.
    """
    flask_app = create_app(config_class=_TestConfig)
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


class _FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class HttpMock:
    """
    Stand-in for `requests.get`/`requests.post` used by app.metadata's search
    functions. Routes by substring match against the request URL; anything
    unregistered gets an empty-object response (so an unmocked source just
    yields zero candidates and the normal cascade/fallback logic runs) rather
    than raising, since the search functions' own try/except would silently
    swallow an injected exception and mask the real behavior under test.
    """

    def __init__(self, monkeypatch):
        self._get_routes = []
        self._post_routes = []
        self.calls = []
        monkeypatch.setattr("app.metadata.requests.get", self._get)
        monkeypatch.setattr("app.metadata.requests.post", self._post)

    def on_get(self, url_substring, json_data):
        self._get_routes.append((url_substring, json_data))

    def on_post(self, url_substring, json_data):
        self._post_routes.append((url_substring, json_data))

    def _get(self, url, **kwargs):
        self.calls.append(url)
        for substring, data in self._get_routes:
            if substring in url:
                return _FakeResponse(data)
        return _FakeResponse({})

    def _post(self, url, **kwargs):
        self.calls.append(url)
        for substring, data in self._post_routes:
            if substring in url:
                return _FakeResponse(data)
        return _FakeResponse({})

    def called(self, url_substring) -> bool:
        return any(url_substring in c for c in self.calls)


@pytest.fixture
def http_mock(monkeypatch):
    return HttpMock(monkeypatch)
