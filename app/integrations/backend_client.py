import os
import requests
from typing import Optional


class BackendClient:
    """Client to fetch scoring configuration from the Java backend.

    Environment variables supported:
      BACKEND_URL (e.g. http://localhost:8080/api)
      BACKEND_API_KEY (optional) - if provided is sent as Authorization: Bearer <key>
      BACKEND_USER / BACKEND_PASS (optional) - used to obtain JWT from /auth/login
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("BACKEND_URL", "http://localhost:8080/api")
        self.api_key = os.getenv("BACKEND_API_KEY")
        self.user = os.getenv("BACKEND_USER")
        self.password = os.getenv("BACKEND_PASS")
        self._token = None
        self._cache = {}
        if self.api_key:
            self._token = self.api_key
        elif self.user and self.password:
            try:
                self.authenticate(self.user, self.password)
            except Exception:
                self._token = None

    def clear_cache(self):
        self._cache.clear()

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def authenticate(self, user: str, password: str) -> bool:
        url = f"{self.base_url.rstrip('/')}/auth/login"
        payload = {"username": user, "password": password}
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()
        body = r.json()
        token = body.get("token") or body.get("accessToken") or body.get("access_token")
        if token:
            self._token = token
            return True
        return False

    def get_active_model(self):
        if "active_model" in self._cache:
            return self._cache["active_model"]
        url = f"{self.base_url.rstrip('/')}/scoring/config/models/active"
        r = requests.get(url, headers=self._headers(), timeout=5)
        if r.status_code != 200:
            return None
        j = r.json()
        self._cache["active_model"] = j
        return j

    def get_variables(self, version: str):
        key = f"vars:{version}"
        if key in self._cache:
            return self._cache[key]
        url = f"{self.base_url.rstrip('/')}/scoring/config/models/{version}/variables"
        r = requests.get(url, headers=self._headers(), timeout=5)
        if r.status_code != 200:
            return None
        j = r.json()
        self._cache[key] = j
        return j

    def get_variable_ranges(self, version: str, variable_key: str):
        key = f"ranges:{version}:{variable_key}"
        if key in self._cache:
            return self._cache[key]
        url = f"{self.base_url.rstrip('/')}/scoring/config/models/{version}/variables/{variable_key}/ranges"
        r = requests.get(url, headers=self._headers(), timeout=5)
        if r.status_code != 200:
            return None
        j = r.json()
        self._cache[key] = j
        return j

    def send_score_audit(self, audit: dict) -> bool:
        """Send audit record to backend; best-effort, returns True if HTTP 200/201."""
        try:
            endpoint = os.getenv("BACKEND_AUDIT_ENDPOINT", "/scoring/audit")
            url = f"{self.base_url.rstrip('/')}{endpoint}"
            r = requests.post(url, json=audit, headers=self._headers(), timeout=5)
            return r.status_code in (200, 201)
        except Exception:
            return False
