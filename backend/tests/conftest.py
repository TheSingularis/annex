import pytest

from app import create_app


@pytest.fixture
def app():
    """Flask app context — enough for code that reads current_app.config.

    Nothing here touches the database, so no real DB/Redis is needed.
    """
    flask_app = create_app()
    with flask_app.app_context():
        yield flask_app


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
