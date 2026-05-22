import requests
from flask import current_app


class ABSClient:
    def __init__(self):
        from app.models import AppSettings
        cfg = AppSettings.get_abs_config()
        self.base_url = cfg["abs_host"].rstrip("/")
        self.api_key = cfg["abs_api_key"]
        self.audiobook_library_id = cfg["abs_audiobook_library_id"]
        self.ebook_library_id = cfg["abs_ebook_library_id"]
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def check_connection(self) -> dict:
        """Returns { reachable, authenticated, error }"""
        if not self.base_url:
            return {"reachable": False, "authenticated": False, "error": "ABS_HOST not configured"}

        # Step 1 — host reachable?
        try:
            resp = requests.get(f"{self.base_url}/ping", timeout=5)
            resp.raise_for_status()
        except Exception as e:
            return {"reachable": False, "authenticated": False, "error": str(e)}

        # Step 2 — API key valid?
        if not self.api_key:
            return {"reachable": True, "authenticated": False, "error": "ABS_API_KEY not configured"}

        try:
            resp = requests.get(
                f"{self.base_url}/api/libraries",
                headers=self.headers,
                timeout=5,
            )
            if resp.status_code == 401:
                return {"reachable": True, "authenticated": False, "error": "Invalid API key"}
            resp.raise_for_status()
        except Exception as e:
            return {"reachable": True, "authenticated": False, "error": str(e)}

        return {"reachable": True, "authenticated": True, "error": None}

    def scan_library(self, category: str):
        library_id = self.audiobook_library_id if category == "audiobook" else self.ebook_library_id

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
