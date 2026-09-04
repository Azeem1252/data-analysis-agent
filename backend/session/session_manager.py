import os
import pickle
import tempfile
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

    def create(self, df: pd.DataFrame, profile: dict[str, Any], profile_str: str = "") -> str:
        sid = str(uuid.uuid4())
        
        # Pre-serialize DataFrame once per session to avoid disk/serialization overhead on each turn
        tmp = tempfile.NamedTemporaryFile(suffix=".pkl", delete=False)
        pickle_path = tmp.name
        tmp.close()
        with open(pickle_path, "wb") as f:
            pickle.dump(df, f)

        with self._lock:
            self._store[sid] = {
                "df": df,
                "profile": profile,
                "profile_str": profile_str,
                "pickle_path": pickle_path,
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
                self._cleanup_session(self._store[sid])
                del self._store[sid]
                return True
            return False

    def _cleanup_session(self, session_data: dict[str, Any]) -> None:
        pickle_path = session_data.get("pickle_path")
        if pickle_path and os.path.exists(pickle_path):
            try:
                os.remove(pickle_path)
            except OSError:
                pass

    def _evict_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired_keys = [
                s for s, v in self._store.items()
                if now - v.get("last_active", v.get("created", 0)) > self.ttl
            ]
            for sid in expired_keys:
                self._cleanup_session(self._store[sid])
                del self._store[sid]


session_manager = SessionManager(ttl_minutes=settings.session_ttl_minutes)
