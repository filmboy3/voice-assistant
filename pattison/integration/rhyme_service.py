from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.phonetic_engine import PhoneticEngine
from ..core.rhyme_classifier import RhymeClassifier
from ..core.types import PattisonRhymeType
from .jonathan_rhyme_db import JonathanRhymeDB
from .pat_rhyme_db import PatRhymeDB


_PREFERENCE_ORDER = {
    "assonance": 0,
    "family": 1,
    "additive": 2,
    "subtractive": 2,
    "consonance": 3,
    "perfect": 4,
    "none": 5,
}


_MATCH_QUALITY = {
    "perfect": 3,
    "surprising": 2,
    "imperfect": 2,
    "near": 1,
    "phrase": 0,
    "": 0,
}


_BANNED_RHYME_PAIRS = {
    ("fire", "desire"),
    ("pain", "rain"),
    ("love", "above"),
    ("tears", "fears"),
    ("heart", "apart"),
    ("night", "light"),
    ("day", "away"),
    ("alone", "phone"),
    ("time", "rhyme"),
    ("true", "you"),
}


def _is_banned_pair(a: str, b: str) -> bool:
    x = (a or "").strip().lower()
    y = (b or "").strip().lower()
    if not x or not y:
        return False
    return (x, y) in _BANNED_RHYME_PAIRS or (y, x) in _BANNED_RHYME_PAIRS


def _normalize_score(x: Any) -> float:
    if isinstance(x, (int, float)):
        if x > 1.0:
            return max(0.0, min(1.0, float(x) / 100.0))
        return max(0.0, min(1.0, float(x)))
    return 0.0


def get_rhymes(
    word: str,
    *,
    rhyme_type: str = "any",
    limit: int = 10,
    include_phrases: bool = True,
    min_sophistication_score: float = 0.7,
    exclude_banned_pairs: bool = True,
    include_pat: bool = True,
    jonathan_db_path: Optional[str] = None,
    pat_db_path: Optional[str] = None,
    cmu_path: Optional[str] = None,
) -> Dict[str, Any]:
    w = (word or "").strip().lower()
    if not w:
        return {"success": False, "error": "Missing word"}

    engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
    classifier = RhymeClassifier(engine)
    db = JonathanRhymeDB(path=jonathan_db_path)

    pat_db = PatRhymeDB(path=pat_db_path) if include_pat else None

    raw = db.get_rhyme_entries(w)
    raw_pat = pat_db.get_rhyme_entries(w) if pat_db is not None else []

    out: List[Dict[str, Any]] = []
    by_word: Dict[str, Dict[str, Any]] = {}

    for entry in list(raw) + list(raw_pat):
        rw = (entry.get("word") or "").strip().lower()
        if not rw or rw == w:
            continue
        if not include_phrases and bool(entry.get("is_phrase")):
            continue

        if exclude_banned_pairs and _is_banned_pair(w, rw):
            continue

        cls = classifier.classify(w, rw)
        ptype = cls.pattison_type.value

        base_score = _normalize_score(entry.get("score") or entry.get("sophistication_score") or 0)
        if base_score < float(min_sophistication_score):
            continue
        combined = 0.5 * base_score + 0.5 * float(cls.pattison_stability)

        match_type = (entry.get("match_type") or entry.get("type") or "").strip().lower()
        match_quality = int(_MATCH_QUALITY.get(match_type, 0))
        source = (entry.get("source") or "").strip()
        tags = entry.get("tags") if isinstance(entry.get("tags"), list) else None

        candidate = {
            "word": rw,
            "match_type": match_type,
            "match_quality": match_quality,
            "is_phrase": bool(entry.get("is_phrase")),
            "score": base_score,
            "pattison_type": ptype,
            "pattison_stability": float(cls.pattison_stability),
            "explanation": cls.explanation,
            "combined_score": combined,
            **({"source": source} if source else {}),
            **({"tags": tags} if tags else {}),
        }

        prev = by_word.get(rw)
        if prev is None:
            by_word[rw] = candidate
            continue

        prev_q = int(prev.get("match_quality") or 0)
        prev_comb = float(prev.get("combined_score") or 0.0)
        cand_comb = float(candidate.get("combined_score") or 0.0)

        if match_quality > prev_q or (match_quality == prev_q and cand_comb > prev_comb):
            by_word[rw] = candidate

    out = list(by_word.values())

    if rhyme_type and rhyme_type != "any":
        out = [r for r in out if r.get("pattison_type") == rhyme_type]

    out.sort(
        key=lambda r: (
            _PREFERENCE_ORDER.get(r.get("pattison_type") or "none", 99),
            -int(r.get("match_quality") or 0),
            -float(r.get("combined_score") or 0.0),
        )
    )

    for r in out:
        r.pop("match_quality", None)

    if limit:
        out = out[: max(0, int(limit))]

    return {"success": True, "word": w, "results": out, "count": len(out)}
