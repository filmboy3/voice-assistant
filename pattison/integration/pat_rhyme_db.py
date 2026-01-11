from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _tags_list(x: Any) -> List[str]:
    if not isinstance(x, list):
        return []
    out: List[str] = []
    for t in x:
        if isinstance(t, str):
            s = t.strip()
            if s:
                out.append(s)
    return out


def _find_tag_value(tags: List[str], prefix: str) -> Optional[str]:
    p = prefix.strip().lower()
    if not p:
        return None
    for t in tags:
        tl = t.strip().lower()
        if tl.startswith(p):
            return t[len(prefix) :].strip() if len(t) >= len(prefix) else ""
    return None


def _infer_match_type(tags: List[str], fallback: str) -> str:
    tv = _find_tag_value(tags, "type:")
    if tv:
        v = tv.strip().lower()
        if v in {"perfect", "surprising", "imperfect"}:
            return "surprising" if v == "imperfect" else v
    fb = (fallback or "").strip().lower()
    if fb in {"perfect", "surprising", "imperfect", "near", "phrase"}:
        return "surprising" if fb == "imperfect" else fb
    return ""


def _infer_source(tags: List[str], fallback: str) -> str:
    sv = _find_tag_value(tags, "source:")
    if sv:
        return sv.strip()
    return (fallback or "").strip()


def _log_relative_score(score: float, max_score: float) -> float:
    if score <= 0 or max_score <= 0:
        return 0.0
    if score >= max_score:
        return 1.0
    denom = math.log10(max_score + 1.0)
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, math.log10(score + 1.0) / denom))


class PatRhymeDB:
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
            if p.suffix.lower() == ".gz":
                with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
                    obj = json.load(f)
            else:
                obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            self._db = obj if isinstance(obj, dict) else {}
        except Exception:
            self._db = {}
        return self._db

    def _get_bucket(self) -> Dict[str, Any]:
        db = self._load()
        rh = db.get("rhymes")
        return rh if isinstance(rh, dict) else {}

    def get_rhyme_entries(self, word: str) -> List[Dict[str, Any]]:
        w = (word or "").strip().lower()
        if not w:
            return []

        bucket = self._get_bucket()
        raw = bucket.get(w)
        if not isinstance(raw, list):
            return []

        cleaned: List[Tuple[Dict[str, Any], float]] = []
        max_score = 0.0
        for item in raw:
            if not isinstance(item, dict):
                continue
            s = item.get("score")
            score = float(s) if isinstance(s, (int, float)) else 0.0
            max_score = max(max_score, score)
            cleaned.append((item, score))

        out: List[Dict[str, Any]] = []
        for item, score in cleaned:
            rw = (item.get("word") or "").strip().lower()
            if not rw or rw == w:
                continue

            tags = _tags_list(item.get("tags"))
            match_type = _infer_match_type(tags, str(item.get("match_type") or item.get("type") or ""))
            source = _infer_source(tags, str(item.get("source") or ""))
            num_syllables = item.get("num_syllables")

            is_phrase = False
            if isinstance(item.get("is_phrase"), bool):
                is_phrase = bool(item.get("is_phrase"))
            elif " " in rw:
                is_phrase = True

            out.append(
                {
                    "word": rw,
                    "match_type": match_type,
                    "score": _log_relative_score(score, max_score),
                    "raw_score": score,
                    "num_syllables": num_syllables,
                    "tags": tags,
                    "source": source,
                    "is_phrase": is_phrase,
                }
            )

        return out
