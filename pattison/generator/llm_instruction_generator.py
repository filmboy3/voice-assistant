from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..integration.rhyme_service import get_rhymes
from .template_generator import generate_template


_BANNED_RHYME_PAIRS = [
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
]


def _format_prompt(package: Dict[str, Any]) -> str:
    tmpl = package.get("template") if isinstance(package.get("template"), dict) else {}
    concept = tmpl.get("concept") or ""
    emotional_arc = tmpl.get("emotional_arc") or ""
    structure = tmpl.get("structure") or ""
    stability_goal = tmpl.get("stability_goal") or ""

    sections = tmpl.get("sections") if isinstance(tmpl.get("sections"), list) else []

    lines: List[str] = []
    lines.append("You are writing a song lyric.")
    lines.append(f"Concept: {concept}")
    if emotional_arc:
        lines.append(f"Emotional arc: {emotional_arc}")
    if structure:
        lines.append(f"Structure: {structure}")
    if stability_goal:
        lines.append(f"Stability goal: {stability_goal}")

    rp = package.get("rhyme_preferences") if isinstance(package.get("rhyme_preferences"), dict) else {}
    if rp:
        lines.append("Rhyme preferences:")
        for k in sorted(rp.keys()):
            lines.append(f"- {k}: {rp[k]}")

    banned = package.get("banned_pairs") if isinstance(package.get("banned_pairs"), list) else []
    if banned:
        lines.append("Avoid these cliché rhyme pairs:")
        for a, b in banned:
            lines.append(f"- {a}/{b}")

    lines.append("Rhyme canon:")
    lines.append("- Match rhyme stability to emotional meaning (perfect=certainty; family/assonance=uncertainty; consonance=very unstable).")
    lines.append("- Use rhyme spotlights wisely: prefer concrete, image-rich end words; avoid functional end words.")
    lines.append("- Avoid rhyming transitive verbs when possible; prefer nouns or participles (e.g., surprise -> surprised).")

    lines.append("Section templates:")
    for s in sections:
        if not isinstance(s, dict):
            continue
        stype = s.get("section_type")
        sn = s.get("section_number")
        pname = s.get("pattern_name")
        scheme = s.get("rhyme_scheme")
        lines.append(f"[{stype} {sn}] pattern={pname} scheme={scheme}")
        for ln in s.get("lines") or []:
            if not isinstance(ln, dict):
                continue
            num = ln.get("line_number")
            stresses = ln.get("target_stresses")
            label = ln.get("rhyme_label")
            rh_with = ln.get("rhymes_with_line")
            opts = ln.get("end_word_options") or []
            opts_txt = ", ".join(opts[:6]) if isinstance(opts, list) and opts else ""
            if rh_with:
                lines.append(f"  - Line {num}: {stresses} stresses; rhyme={label} (with line {rh_with}); end words: {opts_txt}")
            else:
                lines.append(f"  - Line {num}: {stresses} stresses; rhyme={label}; end words: {opts_txt}")

    lines.append("Output requirements:")
    lines.append("- Write vivid, concrete imagery.")
    lines.append("- Respect the target stress counts per line.")
    lines.append("- Respect the rhyme labels and rhyme links exactly.")

    return "\n".join(lines)


def generate_instruction_package(
    *,
    concept: str,
    emotional_arc: str = "",
    structure: str = "verse-chorus-verse-chorus-bridge-chorus",
    stability_goal: str = "balanced",
    rhyme_seed: str = "",
    include_rhyme_suggestions: bool = True,
    jonathan_db_path: Optional[str] = None,
    pat_db_path: Optional[str] = None,
    cmu_path: Optional[str] = None,
    min_sophistication_score: float = 0.7,
) -> Dict[str, Any]:
    c = (concept or "").strip()
    if not c:
        return {"success": False, "error": "Missing required field: concept"}

    seed = (rhyme_seed or "").strip().lower()
    if include_rhyme_suggestions and not seed:
        seed = c.split()[-1].strip().lower() if c.split() else ""

    suggested_words: Dict[str, List[str]] = {}
    suggested_phrases: List[str] = []
    end_word_options_by_label: Optional[Dict[str, List[str]]] = None

    if include_rhyme_suggestions and seed:
        rh = get_rhymes(
            seed,
            rhyme_type="any",
            limit=50,
            include_phrases=True,
            min_sophistication_score=min_sophistication_score,
            exclude_banned_pairs=True,
            jonathan_db_path=jonathan_db_path,
            pat_db_path=pat_db_path,
            cmu_path=cmu_path,
        )
        results = rh.get("results") if isinstance(rh, dict) else None
        if isinstance(results, list):
            words_for_labels: List[str] = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                w = (r.get("word") or "").strip().lower()
                if not w:
                    continue
                if bool(r.get("is_phrase")):
                    suggested_phrases.append(w)
                    continue
                ptype = (r.get("pattison_type") or "none").strip().lower()
                suggested_words.setdefault(ptype, []).append(w)
                words_for_labels.append(w)
            # Provide a baseline list for all rhyme labels.
            end_word_options_by_label = {"A": words_for_labels[:10], "B": words_for_labels[:10], "C": words_for_labels[:10]}

    tmpl = generate_template(
        concept=c,
        emotional_arc=emotional_arc,
        structure=structure,
        stability_goal=stability_goal,
        end_word_options_by_label=end_word_options_by_label,
    )
    if not isinstance(tmpl, dict) or not tmpl.get("success"):
        return tmpl if isinstance(tmpl, dict) else {"success": False, "error": "Template generation failed"}

    rhyme_preferences = {
        "prefer_assonance": True,
        "prefer_family_rhyme": True,
        "avoid_perfect_rhyme": True,
        "max_perfect_rhymes": 1,
        "min_sophistication_score": float(min_sophistication_score),
    }

    pkg: Dict[str, Any] = {
        "success": True,
        "template": tmpl.get("template"),
        "suggested_vocabulary": suggested_words,
        "suggested_phrases": suggested_phrases[:20],
        "rhyme_preferences": rhyme_preferences,
        "banned_pairs": _BANNED_RHYME_PAIRS,
    }
    pkg["formatted_prompt"] = _format_prompt(pkg)

    return pkg
