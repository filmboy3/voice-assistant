import re
from typing import Any, Dict, List


_CLICHE_PATTERNS = [
    {"pattern": r"\bfollow\s+(your|my|their)\s+heart\b", "severity": "high"},
    {"pattern": r"\bheart\s+of\s+gold\b", "severity": "medium"},
    {"pattern": r"\btears?\s+.*\s+like\s+rain\b", "severity": "high"},
    {"pattern": r"\bon\s+my\s+mind\b", "severity": "low"},
    {"pattern": r"\bforever\s+and\s+always\b", "severity": "medium"},
]


def _simple_syllables(text: str) -> int:
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    total = 0
    for w in words:
        w = re.sub(r"[^a-z]", "", w)
        if not w:
            continue
        w = re.sub(r"e$", "", w)
        groups = re.findall(r"[aeiouy]+", w)
        total += max(1, len(groups))
    return total


def critique_lyrics(lyrics: str, focus_areas: List[str] | None = None) -> Dict[str, Any]:
    focus_areas = focus_areas or ["rhyme", "meter", "imagery", "cliche", "repetition"]

    lines = [l.strip() for l in (lyrics or "").splitlines()]
    content_lines = [l for l in lines if l and not l.startswith("[")]

    issues: List[Dict[str, Any]] = []

    if "cliche" in focus_areas:
        for idx, line in enumerate(content_lines):
            for pat in _CLICHE_PATTERNS:
                if re.search(pat["pattern"], line, flags=re.IGNORECASE):
                    issues.append(
                        {
                            "type": "cliche",
                            "severity": pat["severity"],
                            "location": f"line {idx+1}",
                            "text": line,
                        }
                    )

    if "repetition" in focus_areas:
        normalized = [re.sub(r"\W+", " ", l.lower()).strip() for l in content_lines]
        seen = {}
        for idx, n in enumerate(normalized):
            if not n:
                continue
            if n in seen:
                issues.append(
                    {
                        "type": "repetition",
                        "severity": "medium",
                        "location": f"line {idx+1}",
                        "text": content_lines[idx],
                        "note": f"Repeated line (also line {seen[n]+1})",
                    }
                )
            else:
                seen[n] = idx

    meter_scores: List[int] = []
    if "meter" in focus_areas:
        for l in content_lines:
            meter_scores.append(_simple_syllables(l))

        if meter_scores:
            avg = sum(meter_scores) / len(meter_scores)
            variance = sum((x - avg) ** 2 for x in meter_scores) / len(meter_scores)
            if variance > 16:
                issues.append(
                    {
                        "type": "meter",
                        "severity": "medium",
                        "location": "overall",
                        "note": f"High syllable variance across lines (avg {avg:.1f})",
                    }
                )

    cliche_penalty = len([i for i in issues if i["type"] == "cliche"]) * 0.4
    repetition_penalty = len([i for i in issues if i["type"] == "repetition"]) * 0.2
    meter_penalty = len([i for i in issues if i["type"] == "meter"]) * 0.2

    overall = max(0.0, 8.5 - (cliche_penalty + repetition_penalty + meter_penalty))

    return {
        "success": True,
        "scores": {
            "overall": round(overall, 2),
            "originality": round(max(0.0, 8.0 - cliche_penalty), 2),
            "meter_consistency": round(max(0.0, 8.0 - meter_penalty), 2),
            "repetition_control": round(max(0.0, 8.0 - repetition_penalty), 2),
        },
        "issues": issues,
        "strengths": [],
        "metadata": {
            "lines": len(content_lines),
            "syllables": meter_scores,
        },
    }
