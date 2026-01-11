from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..structure.patterns import PATTERNS, PatternDef


@dataclass(frozen=True)
class LineTemplate:
    line_number: int
    target_stresses: int
    rhyme_label: str
    rhymes_with_line: Optional[int]
    end_word_options: List[str]


@dataclass(frozen=True)
class SectionTemplate:
    section_type: str
    section_number: int
    pattern_name: str
    rhyme_scheme: str
    num_lines: int
    target_stability: float
    emotional_goal: str
    lines: List[LineTemplate]


def _split_structure(structure: str) -> List[str]:
    raw = (structure or "").strip().lower()
    if not raw:
        return ["verse", "chorus", "verse", "chorus", "bridge", "chorus"]
    return [p.strip() for p in raw.split("-") if p.strip()]


def _stability_arc(sections: List[str], goal: str) -> List[float]:
    g = (goal or "balanced").strip().lower()
    n = max(1, len(sections))

    if g == "stable":
        return [0.85] * n
    if g == "unstable":
        return [0.35] * n
    if g == "build":
        if n == 1:
            return [0.6]
        return [0.35 + (0.5 * i / (n - 1)) for i in range(n)]

    # balanced
    out: List[float] = []
    for s in sections:
        if "chorus" in s:
            out.append(0.85)
        elif "bridge" in s:
            out.append(0.4)
        elif "pre" in s:
            out.append(0.35)
        else:
            out.append(0.6)
    return out


def _preferred_line_counts(section_type: str) -> List[int]:
    s = (section_type or "").strip().lower()
    if "verse" in s:
        return [4, 6]
    if "chorus" in s:
        return [4, 6]
    if "bridge" in s:
        return [3, 4]
    if "pre" in s:
        return [2, 3, 4]
    return [4]


def _preferred_patterns(section_type: str) -> List[str]:
    s = (section_type or "").strip().lower()
    if "verse" in s:
        return ["4_ABAB", "4_XAXA", "4_AXAX", "4_AABA"]
    if "chorus" in s:
        return ["4_AABB", "4_AAAA", "5_AAAAA"]
    if "bridge" in s:
        return ["3_ABA", "3_AAB", "4_ABBA", "3_XXA"]
    if "pre" in s:
        return ["3_AAB", "3_ABA", "4_AABA", "2_XX"]
    return ["4_ABAB"]


def _choose_pattern(section_type: str, target_stability: float) -> PatternDef:
    allowed_counts = set(_preferred_line_counts(section_type))
    preferred = set(_preferred_patterns(section_type))

    best: Optional[PatternDef] = None
    best_score = 1e9

    for name, p in PATTERNS.items():
        if p.line_count not in allowed_counts:
            continue
        # score is closeness to stability plus a small penalty if not preferred
        score = abs(p.stability - float(target_stability))
        if name not in preferred:
            score += 0.12
        if score < best_score:
            best_score = score
            best = p

    if best is None:
        best = PATTERNS["4_ABAB"]

    return best


def _stress_pattern(p: PatternDef) -> List[int]:
    if p.length_pattern == "common_meter":
        if p.line_count == 4:
            return [4, 3, 4, 3]
        if p.line_count == 6:
            return [4, 3, 4, 3, 4, 3]
    return [4] * p.line_count


def _line_templates(
    rhyme_scheme: str,
    stresses: List[int],
    *,
    end_word_options_by_label: Optional[Dict[str, List[str]]] = None,
) -> List[LineTemplate]:
    seen: Dict[str, int] = {}
    out: List[LineTemplate] = []
    for i, label in enumerate(list(rhyme_scheme)):
        rhymes_with: Optional[int] = None
        if label != "X":
            if label in seen:
                rhymes_with = seen[label] + 1
            else:
                seen[label] = i
        opts: List[str] = []
        if label != "X" and end_word_options_by_label and isinstance(end_word_options_by_label.get(label), list):
            opts = [str(x) for x in (end_word_options_by_label.get(label) or []) if x]
        out.append(
            LineTemplate(
                line_number=i + 1,
                target_stresses=stresses[i],
                rhyme_label=label,
                rhymes_with_line=rhymes_with,
                end_word_options=opts,
            )
        )
    return out


def generate_template(
    *,
    concept: str,
    emotional_arc: str = "",
    structure: str = "verse-chorus-verse-chorus-bridge-chorus",
    stability_goal: str = "balanced",
    end_word_options_by_label: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    if not (concept or "").strip():
        return {"success": False, "error": "Missing required field: concept"}

    sections = _split_structure(structure)
    arc = _stability_arc(sections, stability_goal)

    templates: List[SectionTemplate] = []
    for idx, (stype, target) in enumerate(zip(sections, arc)):
        pat = _choose_pattern(stype, target)
        stresses = _stress_pattern(pat)
        lines = _line_templates(pat.rhyme_scheme, stresses, end_word_options_by_label=end_word_options_by_label)
        templates.append(
            SectionTemplate(
                section_type=stype,
                section_number=idx + 1,
                pattern_name=pat.name,
                rhyme_scheme=pat.rhyme_scheme,
                num_lines=pat.line_count,
                target_stability=float(target),
                emotional_goal=pat.emotion,
                lines=lines,
            )
        )

    return {
        "success": True,
        "template": {
            "concept": concept,
            "emotional_arc": emotional_arc,
            "structure": structure,
            "stability_goal": stability_goal,
            "sections": [asdict(s) for s in templates],
        },
    }
