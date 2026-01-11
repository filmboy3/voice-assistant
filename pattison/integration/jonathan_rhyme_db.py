import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class JonathanRhymeDB:
    def __init__(self, *, path: Optional[str] = None):
        self.path = (path or "").strip() or None
        self._db: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._db is not None:
            return self._db
        if not self.path:
            self._db = {}
            return self._db
        p = Path(self.path)
        if not p.exists():
            self._db = {}
            return self._db
        try:
            obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            self._db = obj if isinstance(obj, dict) else {}
        except Exception:
            self._db = {}
        return self._db

    def get_rhyme_entries(self, word: str) -> List[Dict[str, Any]]:
        w = (word or "").strip().lower()
        if not w:
            return []
        db = self._load()
        entry = db.get(w)
        if isinstance(entry, dict):
            rh = entry.get("rhymes")
            if isinstance(rh, list):
                return [r for r in rh if isinstance(r, dict)]
        if isinstance(entry, list):
            # Allow simple list-of-words fixtures
            out: List[Dict[str, Any]] = []
            for item in entry:
                if isinstance(item, str) and item.strip():
                    out.append({"word": item.strip(), "match_type": "near", "score": 0})
            return out
        return []
