import requests
from flask import current_app


class ABSClient:
    def __init__(self):
        self.base_url = current_app.config["ABS_HOST"].rstrip("/")
        self.api_key = current_app.config["ABS_API_KEY"]
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def scan_library(self, category: str):
        if category == "audiobook":
            library_id = current_app.config["ABS_AUDIOBOOK_LIBRARY_ID"]
        else:
            library_id = current_app.config["ABS_EBOOK_LIBRARY_ID"]

        if not library_id:
            current_app.logger.warning(f"No ABS library ID configured for category: {category}")
            return

        resp = requests.post(
            f"{self.base_url}/api/libraries/{library_id}/scan",
            headers=self.headers,
            timeout=15,
        )
        resp.raise_for_status()
        current_app.logger.info(f"ABS scan triggered for library {library_id}")
