import time
import uuid
from threading import Lock
from typing import Any
import pandas as pd
try:
    from backend.config import settings
except ImportError:
    from config import settings


class SessionManager:
    def __init__(self, ttl_minutes: int = 60):
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self.ttl = ttl_minutes * 60

    def create(self, df: pd.DataFrame, profile: dict[str, Any]) -> str:
        sid = str(uuid.uuid4())
        with self._lock:
            self._store[sid] = {
                "df": df,
                "profile": profile,
                "history": [],
                "created": time.time(),
                "last_active": time.time(),
            }
        return sid

    def get(self, sid: str) -> dict[str, Any]:
        self._evict_expired()
        with self._lock:
            if sid not in self._store:
                raise KeyError("Session not found or expired")
            self._store[sid]["last_active"] = time.time()
            return self._store[sid]

    def append_turn(self, sid: str, role: str, content: str) -> None:
        with self._lock:
            if sid in self._store:
                self._store[sid]["history"].append({"role": role, "content": content})
                self._store[sid]["last_active"] = time.time()

    def delete(self, sid: str) -> bool:
        with self._lock:
            if sid in self._store:
                del self._store[sid]
                return True
            return False

    def _evict_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired_keys = [
                s for s, v in self._store.items()
                if now - v.get("last_active", v.get("created", 0)) > self.ttl
            ]
            for sid in expired_keys:
                del self._store[sid]


session_manager = SessionManager(ttl_minutes=settings.session_ttl_minutes)
