import requests
from flask import current_app


class QBittorrentClient:
    def __init__(self):
        host = current_app.config["QBIT_HOST"]
        port = current_app.config["QBIT_PORT"]
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self._authenticated = False

    def _authenticate(self):
        resp = self.session.post(
            f"{self.base_url}/api/v2/auth/login",
            data={
                "username": current_app.config["QBIT_USERNAME"],
                "password": current_app.config["QBIT_PASSWORD"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        self._authenticated = True

    def get_completed_torrents(self, categories=("audiobook", "ebook")):
        if not self._authenticated:
            self._authenticate()

        results = []
        for category in categories:
            resp = self.session.get(
                f"{self.base_url}/api/v2/torrents/info",
                params={"filter": "completed", "category": category},
                timeout=10,
            )
            resp.raise_for_status()
            results.extend(resp.json())

        return results
