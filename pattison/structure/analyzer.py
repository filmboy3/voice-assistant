from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..core.phonetic_engine import PhoneticEngine
from ..core.rhyme_classifier import RhymeClassifier
from ..core.tokenize import normalize_lyric_line, tokenize_words
from ..core.types import PattisonRhymeType
from .patterns import PatternDef, patterns_for_line_count


@dataclass(frozen=True)
class LineResult:
    text: str
    end_word: str
    primary_stress_count: int


def _ending_word(line: str) -> str:
    words = tokenize_words(line)
    return words[-1] if words else ""


def _is_vowel_letter(ch: str) -> bool:
    c = (ch or "").strip().lower()
    return bool(c and c in {"a", "e", "i", "o", "u", "y"})


def _edge_kind(engine: PhoneticEngine, word: str, *, which: str) -> Optional[str]:
    w = (word or "").strip()
    if not w:
        return None
    phonemes = engine.get_phonemes(w)
    if phonemes:
        p = phonemes[0] if which == "first" else phonemes[-1]
        return "vowel" if p.is_vowel else "consonant"

    letters = "".join([c for c in w.lower() if c.isalpha()])
    if not letters:
        return None
    ch = letters[0] if which == "first" else letters[-1]
    return "vowel" if _is_vowel_letter(ch) else "consonant"


def _analyze_juncture(lines: List[str], *, engine: PhoneticEngine) -> Dict[str, Any]:
    pairs: List[Dict[str, Any]] = []
    legato = 0
    staccato = 0
    total = 0

    for line_idx, line in enumerate(lines or [], start=1):
        words = tokenize_words(line)
        if len(words) < 2:
            continue
        for j in range(len(words) - 1):
            left = words[j]
            right = words[j + 1]
            a = _edge_kind(engine, left, which="last")
            b = _edge_kind(engine, right, which="first")
            if not a or not b:
                continue
            total += 1
            kind = "staccato" if a == "consonant" and b == "consonant" else "legato"
            if kind == "staccato":
                staccato += 1
            else:
                legato += 1
            pairs.append({"line": line_idx, "left": left, "right": right, "type": kind})

    ratio = float(staccato) / float(total) if total else 0.0
    return {
        "total": total,
        "legato": legato,
        "staccato": staccato,
        "staccato_ratio": ratio,
        "pairs": pairs,
    }


def _normalize_scheme(raw_labels: List[str]) -> str:
    remap: Dict[str, str] = {}
    next_letter = ord("A")
    out: List[str] = []
    for ch in raw_labels:
        if ch == "X":
            out.append("X")
            continue
        if ch not in remap:
            remap[ch] = chr(next_letter)
            next_letter += 1
        out.append(remap[ch])
    return "".join(out)


def _structural_scheme(raw_labels: List[str]) -> str:
    """Collapse singleton rhyme classes to X (Pattison-style unrhymed placeholders) and normalize."""
    counts: Dict[str, int] = {}
    for ch in raw_labels:
        counts[ch] = counts.get(ch, 0) + 1
    collapsed: List[str] = []
    for ch in raw_labels:
        if ch == "X":
            collapsed.append("X")
        elif counts.get(ch, 0) <= 1:
            collapsed.append("X")
        else:
            collapsed.append(ch)
    return _normalize_scheme(collapsed)


def _counts_as_rhyme(t: PattisonRhymeType, *, include_consonance: bool = False) -> bool:
    if t in {
        PattisonRhymeType.PERFECT,
        PattisonRhymeType.FAMILY,
        PattisonRhymeType.ADDITIVE,
        PattisonRhymeType.SUBTRACTIVE,
        PattisonRhymeType.ASSONANCE,
    }:
        return True
    if include_consonance and t == PattisonRhymeType.CONSONANCE:
        return True
    return False


def detect_rhyme_scheme(
    endings: List[str],
    *,
    classifier: RhymeClassifier,
    include_consonance: bool = False,
) -> Tuple[str, Dict[Tuple[int, int], Dict[str, Any]]]:
    # First pass: assign provisional labels based on first earlier rhyme.
    labels: List[str] = []
    pair_details: Dict[Tuple[int, int], Dict[str, Any]] = {}
    next_label_ord = ord("A")

    for i, w in enumerate(endings):
        if not w:
            labels.append("X")
            continue

        matched_label: Optional[str] = None
        best_match: Optional[Tuple[int, float]] = None  # (index, stability)
        for j in range(i - 1, -1, -1):
            w_prev = endings[j]
            if not w_prev:
                continue
            res = classifier.classify(w, w_prev)
            if _counts_as_rhyme(res.pattison_type, include_consonance=include_consonance):
                # Prefer the most stable match; tie-break by recency (largest j)
                if best_match is None or res.pattison_stability > best_match[1] or (res.pattison_stability == best_match[1] and j > best_match[0]):
                    best_match = (j, res.pattison_stability)
                    matched_label = labels[j]
                    pair_details[(j, i)] = {
                        "word1": w_prev,
                        "word2": w,
                        "pattison_type": res.pattison_type.value,
                        "pattison_stability": res.pattison_stability,
                        "explanation": res.explanation,
                    }
        # Only assign if we found a valid match (not X)
        if matched_label and matched_label != "X":
            labels.append(matched_label)
            continue

        labels.append(chr(next_label_ord))
        next_label_ord += 1
        if next_label_ord > ord("Z"):
            next_label_ord = ord("A")

    scheme = _normalize_scheme(labels)
    return scheme, pair_details


def _common_meter(lengths: List[int]) -> bool:
    if len(lengths) != 4:
        return False
    if lengths[0] > lengths[1] and lengths[2] > lengths[3] and lengths[0] == lengths[2] and lengths[1] == lengths[3]:
        return True
    if lengths[0] > lengths[1] and lengths[2] > lengths[3] and lengths[0] >= lengths[2] - 1 and lengths[0] <= lengths[2] + 1:
        return True
    return False


def _pattern_match_score(candidate: str, target: str) -> float:
    if len(candidate) != len(target) or not target:
        return 0.0
    matches = 0.0
    for c, t in zip(candidate, target):
        if c == t:
            matches += 1.0
    return matches / len(target)


def match_pattern(*, raw_scheme: str, structural_scheme: str, lengths: List[int]) -> Tuple[Optional[PatternDef], float]:
    candidates = patterns_for_line_count(len(lengths))
    best: Optional[PatternDef] = None
    best_key: Tuple[float, int, float] = (0.0, -1, -1.0)

    for p in candidates:
        cand = structural_scheme if "X" in p.rhyme_scheme else raw_scheme
        score = _pattern_match_score(cand, p.rhyme_scheme)
        if p.length_pattern == "common_meter":
            if _common_meter(lengths):
                score = min(1.0, score + 0.15)
            else:
                score = max(0.0, score - 0.15)
        elif p.length_pattern in {"matched", "unmatched"}:
            is_matched = len(set(lengths)) == 1
            wants_matched = p.length_pattern == "matched"
            if is_matched == wants_matched:
                score = min(1.0, score + 0.15)
            else:
                score = max(0.0, score - 0.15)
        specificity = sum(1 for ch in p.rhyme_scheme if ch != "X")
        key = (score, specificity, float(p.stability))
        if key > best_key:
            best = p
            best_key = key

    return best, best_key[0]


def estimate_stability(*, scheme: str, lengths: List[int]) -> float:
    # Heuristic stability: even lines stabilize; more rhymes stabilize; matched lengths stabilize.
    if not lengths:
        return 0.0
    score = 0.5

    if len(lengths) % 2 == 0:
        score += 0.15
    else:
        score -= 0.1

    # length stability
    if len(set(lengths)) == 1:
        score += 0.15
    elif len(lengths) >= 2:
        # penalize long->short transitions more
        for a, b in zip(lengths, lengths[1:]):
            if a > b:
                score -= 0.05
            elif a < b:
                score += 0.02

    rhyme_positions = len(scheme) - scheme.count("X")
    if scheme:
        score += 0.2 * (rhyme_positions / len(scheme))

    return max(0.0, min(1.0, score))


def split_into_stanzas(lines: List[str]) -> List[List[str]]:
    """
    Split a list of lyric lines into stanzas.
    - Explicit blank lines create stanza breaks (ALWAYS respected).
    - If no blank lines and line_count > 16, propose auto-segmentation (4/6/8-line groups).
    - Otherwise preserve natural structure (don't force chunking).
    Returns a list of stanzas, each a list of lines.
    """
    stanzas: List[List[str]] = []
    current: List[str] = []
    has_explicit_breaks = False
    
    for line in lines:
        stripped = line.rstrip()
        if stripped == "":
            if current:
                stanzas.append(current)
                current = []
                has_explicit_breaks = True
        else:
            current.append(stripped)
    if current:
        stanzas.append(current)

    # NEVER auto-segment if there were explicit blank lines
    # Only auto-segment very long sections (>16 lines) with no breaks
    if not has_explicit_breaks and len(stanzas) == 1 and len(stanzas[0]) > 16:
        base = stanzas[0]
        # Prefer 4, 6, or 8 lines per stanza; choose the most even division
        candidates = [4, 6, 8]
        best_chunk = None
        best_remainder = None
        best_score = None
        for chunk in candidates:
            if chunk >= len(base):
                continue
            num_full = len(base) // chunk
            remainder = len(base) % chunk
            # Prefer fewer, larger chunks and smaller remainder
            score = (num_full, -remainder, -chunk)
            if best_score is None or score > best_score:
                best_score = score
                best_chunk = chunk
                best_remainder = remainder
        if best_chunk:
            auto_stanzas: List[List[str]] = []
            i = 0
            while i + best_chunk <= len(base):
                auto_stanzas.append(base[i:i+best_chunk])
                i += best_chunk
            if best_remainder:
                auto_stanzas.append(base[i:])
            stanzas = auto_stanzas
    return stanzas


def analyze_section(
    lines: List[str],
    *,
    cmu_path: Optional[str] = None,
    jonathan_db_path: Optional[str] = None,
    include_consonance_in_scheme: bool = False,
) -> Dict[str, Any]:
    engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
    classifier = RhymeClassifier(engine)

    raw_input_lines = [l.rstrip() for l in (lines or []) if isinstance(l, str)]
    cleaned = [l.strip() for l in raw_input_lines if l.strip()]
    normalized_cleaned = [normalize_lyric_line(l) for l in cleaned]
    line_results: List[LineResult] = []

    for l, normalized in zip(cleaned, normalized_cleaned):
        end = _ending_word(normalized)
        stresses = engine.count_line_primary_stresses(normalized)
        line_results.append(LineResult(text=l, end_word=end, primary_stress_count=stresses))

    endings = [lr.end_word for lr in line_results]
    lengths = [lr.primary_stress_count for lr in line_results]

    raw_scheme, pairs = detect_rhyme_scheme(endings, classifier=classifier, include_consonance=include_consonance_in_scheme)
    scheme = _structural_scheme(list(raw_scheme))
    pattern, confidence = match_pattern(raw_scheme=raw_scheme, structural_scheme=scheme, lengths=lengths)

    stability = pattern.stability if pattern else estimate_stability(scheme=scheme, lengths=lengths)

    rhyme_pairs_out: List[Dict[str, Any]] = []
    for (i, j), payload in sorted(pairs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        entry = {"line1": int(i) + 1, "line2": int(j) + 1}
        entry.update(payload)
        rhyme_pairs_out.append(entry)

    juncture = _analyze_juncture(normalized_cleaned, engine=engine)

    # Stanza splitting
    stanzas = split_into_stanzas(raw_input_lines)

    return {
        "success": True,
        "lines": [asdict(lr) for lr in line_results],
        "end_words": endings,
        "stresses": lengths,
        "raw_rhyme_scheme": raw_scheme,
        "rhyme_scheme": scheme,
        "rhyme_pairs": rhyme_pairs_out,
        "pattern": pattern.__dict__ if pattern else None,
        "pattern_confidence": confidence,
        "confidence": confidence,
        "stability": stability,
        "juncture": juncture,
        "stanzas": stanzas,
    }
