import random
import re
from typing import Any, Dict, List, Optional, Set

import gzip
import hashlib
import json
import os
import requests


def _split_structure(structure: str) -> List[str]:
    raw = (structure or "").strip().lower()
    if not raw:
        return ["verse_1", "chorus", "verse_2", "chorus_2", "bridge", "chorus_3"]

    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    counts: Dict[str, int] = {}
    out: List[str] = []

    for p in parts:
        counts[p] = counts.get(p, 0) + 1
        suffix = counts[p]
        if p in {"verse", "chorus"}:
            out.append(f"{p}_{suffix}")
        else:
            out.append(p if suffix == 1 else f"{p}_{suffix}")

    return out


def _pick_seed_word(theme: str) -> str:
    tokens = re.findall(r"[a-zA-Z']+", (theme or "").lower())
    if not tokens:
        return "time"
    return tokens[-1]


def _simple_syllable_estimate(word: str) -> int:
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    if not w:
        return 0
    w = re.sub(r"e$", "", w)
    groups = re.findall(r"[aeiouy]+", w)
    return max(1, len(groups))


_R2_CDN_BASE = os.environ.get("R2_CDN_BASE") or "https://pub-53b5eb7528ba49eaaf533b48541508ae.r2.dev"
_rhyme_shard_cache: Dict[str, Dict[str, Any]] = {}
_rhyme_candidates_cache: Dict[str, List[str]] = {}


def _shard_id_for_word(word: str) -> str:
    w = (word or "").strip().lower()
    if not w:
        return "00"
    digest = hashlib.sha256(w.encode("utf-8")).digest()
    return f"{digest[0]:02x}"


def _load_rhyme_shard(shard_id: str) -> Dict[str, Any]:
    sid = (shard_id or "").strip().lower()
    if len(sid) != 2:
        return {}
    if sid in _rhyme_shard_cache:
        return _rhyme_shard_cache[sid]

    url = f"{_R2_CDN_BASE.rstrip('/')}/rhyme/v3i_shards_256/{sid}.json.gz"
    try:
        resp = requests.get(url, timeout=20)
        if not resp.ok:
            _rhyme_shard_cache[sid] = {}
            return _rhyme_shard_cache[sid]
        raw = gzip.decompress(resp.content)
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        _rhyme_shard_cache[sid] = obj if isinstance(obj, dict) else {}
        return _rhyme_shard_cache[sid]
    except Exception:
        _rhyme_shard_cache[sid] = {}
        return _rhyme_shard_cache[sid]


def _rhyme_candidates_from_shards(seed: str) -> List[str]:
    s = (seed or "").strip().lower()
    if not s:
        return []
    if s in _rhyme_candidates_cache:
        return list(_rhyme_candidates_cache[s])

    shard = _load_rhyme_shard(_shard_id_for_word(s))
    entry = shard.get(s)
    if not isinstance(entry, dict):
        _rhyme_candidates_cache[s] = []
        return []

    rhymes = entry.get("rhymes")
    if not isinstance(rhymes, list) or not rhymes:
        _rhyme_candidates_cache[s] = []
        return []

    perfect: List[Dict[str, Any]] = []
    near: List[Dict[str, Any]] = []
    for r in rhymes:
        if not isinstance(r, dict):
            continue
        w = r.get("word")
        if not isinstance(w, str) or not w.strip():
            continue
        mt = str(r.get("match_type") or "").lower()
        if mt == "perfect":
            perfect.append(r)
        else:
            near.append(r)

    def _score(x: Dict[str, Any]) -> int:
        v = x.get("score")
        return int(v) if isinstance(v, (int, float)) else 0

    perfect_sorted = sorted(perfect, key=_score, reverse=True)
    near_sorted = sorted(near, key=_score, reverse=True)

    ordered: List[str] = []
    seen: Set[str] = set()
    for bucket in (perfect_sorted, near_sorted):
        for item in bucket:
            w = str(item.get("word") or "").strip().lower()
            if not w or w == s or w in seen:
                continue
            seen.add(w)
            ordered.append(w)
            if len(ordered) >= 80:
                break
        if len(ordered) >= 80:
            break

    if ordered:
        random.shuffle(ordered)
    _rhyme_candidates_cache[s] = ordered
    return list(ordered)


def _fallback_rhyme_candidates(seed: str) -> List[str]:
    seed = (seed or "").strip().lower()
    if len(seed) < 3:
        return [seed] if seed else ["time", "line", "night", "light"]

    suffix = seed[-3:]
    candidates = [
        seed,
        f"{suffix}",
        f"{seed[:-1]}y",
        "time",
        "line",
        "night",
        "light",
        "fire",
        "wire",
        "road",
        "cold",
    ]
    seen = set()
    out = []
    for c in candidates:
        c = (c or "").strip().lower()
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _rhyme_candidates(seed: str) -> List[str]:
    try:
        words = _rhyme_candidates_from_shards(seed)
        if words:
            return words[:30]
    except Exception:
        pass

    try:
        from rhyme_phrase_search import get_rhyming_words

        words = get_rhyming_words(seed)
        words = [w for w in words if w and isinstance(w, str)]
        if words:
            random.shuffle(words)
            return words[:30]
    except Exception:
        pass

    return _fallback_rhyme_candidates(seed)


def _pick_endings_for_scheme(rhyme_scheme: str, seed_word: str, used_endings: Optional[Set[str]] = None) -> Dict[str, str]:
    scheme = (rhyme_scheme or "").strip().upper()
    if not scheme:
        scheme = "ABAB"

    candidates = _rhyme_candidates(seed_word)
    if not candidates:
        candidates = [seed_word]

    letter_to_ending: Dict[str, str] = {}
    chosen: List[str] = []
    avoid = set(used_endings or set())

    for ch in scheme:
        if not ch.isalpha():
            continue
        if ch in letter_to_ending:
            continue
        pick = None
        for c in candidates:
            if c not in chosen and c not in avoid:
                pick = c
                break
        if not pick:
            for c in candidates:
                if c not in chosen:
                    pick = c
                    break
        if not pick:
            pick = candidates[0]
        letter_to_ending[ch] = pick
        chosen.append(pick)

    return letter_to_ending


def generate_song_outline(
    theme: str,
    tone: str = "",
    structure: str = "verse-chorus-verse-chorus-bridge-chorus",
    rhyme_scheme: Optional[Dict[str, str]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    constraints = constraints or {}
    max_lines = int(constraints.get("max_lines_per_section") or 4)
    motifs = constraints.get("required_motifs") or []
    avoid = constraints.get("avoid_words") or []

    seed_word = _pick_seed_word(theme)

    sections = _split_structure(structure)
    outline: Dict[str, Any] = {}

    used_endings_global: Set[str] = set()

    for section in sections:
        base = section.split("_")[0]
        section_scheme = "ABAB" if base == "verse" else "AABB" if base == "chorus" else "ABAB"
        if rhyme_scheme and isinstance(rhyme_scheme, dict):
            section_scheme = (rhyme_scheme.get(base) or rhyme_scheme.get(section) or section_scheme)

        letter_endings = _pick_endings_for_scheme(section_scheme, seed_word, used_endings=used_endings_global)
        used_endings_global.update(letter_endings.values())
        rhyme_plan: Dict[str, str] = {}
        for idx, ch in enumerate([c for c in section_scheme if c.isalpha()]):
            rhyme_plan[f"line_{idx+1}_ending"] = letter_endings.get(ch, seed_word)

        tone_words = [w for w in [tone.strip(), "fading", "distant", "amber", "raw", "bright"] if w]
        tone_words = list(dict.fromkeys(tone_words))[:6]

        outline[section] = {
            "goal": "",
            "rhyme_scheme": section_scheme,
            "rhyme_plan": rhyme_plan,
            "tone_words": tone_words,
            "constraints": {
                "max_lines": max_lines,
                "required_motifs": motifs,
                "avoid_words": avoid,
            },
        }

    return {
        "success": True,
        "outline": outline,
        "metadata": {
            "theme": theme,
            "tone": tone,
            "seed_word": seed_word,
            "structure": structure,
            "estimated_syllables_seed": _simple_syllable_estimate(seed_word),
        },
    }


def _ensure_ending(line: str, ending: str) -> str:
    ending = (ending or "").strip().lower()
    if not ending:
        return line

    cleaned = re.sub(r"[\s\t]+", " ", (line or "").strip())
    if not cleaned:
        cleaned = ending

    last = re.findall(r"[a-zA-Z']+", cleaned.lower())
    if last and last[-1] == ending:
        return cleaned

    cleaned = re.sub(r"[\W_]+$", "", cleaned)
    return f"{cleaned} {ending}".strip()


def _resolve_ending_with_phrase_coverage(
    ending: str,
    *,
    search_phrases_by_ending,
    max_phrase_check: int = 12,
    max_alt_candidates: int = 40,
) -> Dict[str, Any]:
    e = (ending or "").strip().lower()
    if not e or not search_phrases_by_ending:
        return {"ending": e, "phrases": []}

    try:
        phrases = search_phrases_by_ending(e, limit=max_phrase_check) or []
        if phrases:
            return {"ending": e, "phrases": phrases}
    except Exception:
        phrases = []

    for alt in _rhyme_candidates(e)[:max_alt_candidates]:
        a = (alt or "").strip().lower()
        if not a or a == e:
            continue
        try:
            phrases_alt = search_phrases_by_ending(a, limit=max_phrase_check) or []
            if phrases_alt:
                return {"ending": a, "phrases": phrases_alt}
        except Exception:
            continue

    return {"ending": e, "phrases": []}


def draft_from_outline(outline: Dict[str, Any], theme: str = "", tone: str = "") -> Dict[str, Any]:
    if not isinstance(outline, dict) or not outline:
        return {"success": False, "error": "Missing or invalid outline"}

    lines_out: List[str] = []

    try:
        from rhyme_phrase_search import search_phrases_by_ending
    except Exception:
        search_phrases_by_ending = None

    for section_name, section in outline.items():
        if not isinstance(section, dict):
            continue

        rhyme_plan = section.get("rhyme_plan") or {}
        section_lines: List[str] = []

        resolved: Dict[str, Dict[str, Any]] = {}
        for v in rhyme_plan.values():
            e = (v or "").strip().lower()
            if not e or e in resolved:
                continue
            resolved[e] = _resolve_ending_with_phrase_coverage(e, search_phrases_by_ending=search_phrases_by_ending)

        for key in sorted(rhyme_plan.keys()):
            ending_raw = (rhyme_plan.get(key) or "").strip().lower()
            resolved_entry = resolved.get(ending_raw) or {"ending": ending_raw, "phrases": []}
            ending = (resolved_entry.get("ending") or "").strip().lower()
            phrases_for_ending = resolved_entry.get("phrases") or []

            phrase = ""
            if phrases_for_ending and ending:
                phrase = random.choice(phrases_for_ending).get("text", "")

            if not phrase:
                phrase = f"thinking about {theme}".strip() if theme else "holding the moment"

            tone_word = ""
            tw = section.get("tone_words") or []
            if isinstance(tw, list) and tw:
                tone_word = random.choice([t for t in tw if t])

            raw_line = f"{tone_word} {phrase}".strip()
            section_lines.append(_ensure_ending(raw_line, ending))

        lines_out.append(f"[{section_name}]")
        lines_out.extend(section_lines)
        lines_out.append("")

    lyrics = "\n".join(lines_out).strip() + "\n"

    return {
        "success": True,
        "lyrics": lyrics,
        "metadata": {
            "theme": theme,
            "tone": tone,
            "sections": len(outline.keys()),
            "lines": len([l for l in lines_out if l and not l.startswith("[")]),
        },
    }
