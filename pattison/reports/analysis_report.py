from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..structure.analyzer import analyze_section


def split_sections_from_lyrics(lyrics: str) -> List[Tuple[str, List[str]]]:
    lines = [l.rstrip() for l in (lyrics or "").splitlines()]

    sections: List[Tuple[str, List[str]]] = []
    current_name = "Section 1"
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_lines, current_name
        cleaned = [l.strip() for l in current_lines if l and l.strip()]
        if cleaned:
            sections.append((current_name, cleaned))
        current_lines = []

    for raw in lines:
        s = (raw or "").strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]") and len(s) > 2:
            flush()
            current_name = s.strip("[]").strip() or current_name
            continue
        current_lines.append(s)

    flush()

    if not sections:
        return [("Section 1", [l.strip() for l in lines if l and l.strip()])]
    return sections


def split_sections_from_lines(lines: List[str]) -> List[Tuple[str, List[str]]]:
    # Accept the same bracket-header convention as lyric strings.
    buf = "\n".join([str(l) for l in (lines or []) if l is not None])
    return split_sections_from_lyrics(buf)


def _count_types(rhyme_pairs: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in rhyme_pairs or []:
        if not isinstance(p, dict):
            continue
        t = (p.get("pattison_type") or "").strip().lower()
        if not t:
            continue
        counts[t] = counts.get(t, 0) + 1
    return counts


def generate_analysis_report(
    *,
    lyrics: Optional[str] = None,
    lines: Optional[List[str]] = None,
    cmu_path: Optional[str] = None,
    jonathan_db_path: Optional[str] = None,
    include_consonance_in_scheme: bool = False,
) -> Dict[str, Any]:
    if lines is None and lyrics is None:
        return {"success": False, "error": "Provide either 'lines' (array) or 'lyrics' (string)"}

    if lines is not None and not isinstance(lines, list):
        return {"success": False, "error": "Invalid field: lines (must be array)"}
    if lyrics is not None and not isinstance(lyrics, str):
        return {"success": False, "error": "Invalid field: lyrics (must be string)"}

    sections: List[Tuple[str, List[str]]] = []

    if lines is not None:
        sections = split_sections_from_lines([l for l in lines if isinstance(l, str)])
    else:
        sections = split_sections_from_lyrics(lyrics or "")

    report_lines: List[str] = []
    report_lines.append("# Lyric Structure Analysis")
    report_lines.append("")

    section_outputs: List[Dict[str, Any]] = []
    stabilities: List[float] = []

    for name, sec_lines in sections:
        analysis = analyze_section(
            sec_lines,
            cmu_path=cmu_path,
            jonathan_db_path=jonathan_db_path,
            include_consonance_in_scheme=include_consonance_in_scheme,
        )

        section_outputs.append({"name": name, "analysis": analysis})

        stability = float(analysis.get("stability") or 0.0) if isinstance(analysis, dict) else 0.0
        stabilities.append(stability)

        report_lines.append(f"## {name}")
        report_lines.append("")

        report_lines.append("### Line Analysis")
        report_lines.append("")
        report_lines.append("| Line | Text | Stresses | End Word |")
        report_lines.append("|------|------|----------|----------|")

        line_rows = analysis.get("lines") if isinstance(analysis, dict) else None
        if isinstance(line_rows, list):
            for i, lr in enumerate(line_rows, start=1):
                if not isinstance(lr, dict):
                    continue
                txt = (lr.get("text") or "").strip().replace("|", "\\|")
                end = (lr.get("end_word") or "").strip().replace("|", "\\|")
                stresses = lr.get("primary_stress_count")
                report_lines.append(f"| {i} | {txt} | {stresses} | {end} |")

        report_lines.append("")

        report_lines.append("### Structure Pattern")
        report_lines.append("")
        pat = analysis.get("pattern") if isinstance(analysis, dict) else None
        if isinstance(pat, dict):
            report_lines.append(f"- **Pattern Detected**: {pat.get('name')}")
            report_lines.append(f"- **Confidence**: {float(analysis.get('pattern_confidence') or 0.0):.0%}")
            report_lines.append(f"- **Rhyme Scheme**: {analysis.get('rhyme_scheme')}")
            report_lines.append(f"- **Raw Rhyme Scheme**: {analysis.get('raw_rhyme_scheme')}")
            report_lines.append(f"- **Stability Score**: {float(analysis.get('stability') or 0.0):.2f}/1.0")
            report_lines.append(f"- **Motion Description**: {pat.get('description')}")
            report_lines.append(f"- **Emotional Implication**: {pat.get('emotion')}")
        else:
            report_lines.append(f"- **Rhyme Scheme**: {analysis.get('rhyme_scheme') if isinstance(analysis, dict) else ''}")

        report_lines.append("")

        report_lines.append("### Rhyme Analysis")
        report_lines.append("")
        rhyme_pairs = analysis.get("rhyme_pairs") if isinstance(analysis, dict) else None
        if isinstance(rhyme_pairs, list) and rhyme_pairs:
            counts = _count_types(rhyme_pairs)
            if counts:
                report_lines.append("Rhyme type counts:")
                for t in sorted(counts.keys()):
                    report_lines.append(f"- **{t}**: {counts[t]}")
                report_lines.append("")

            for rp in rhyme_pairs:
                if not isinstance(rp, dict):
                    continue
                l1 = rp.get("line1")
                l2 = rp.get("line2")
                t = rp.get("pattison_type")
                st = rp.get("pattison_stability")
                report_lines.append(f"- Lines {l1} & {l2}: **{t}** (stability: {float(st or 0.0):.2f})")
        else:
            report_lines.append("- No rhyme pairs detected.")

        report_lines.append("")

        juncture = analysis.get("juncture") if isinstance(analysis, dict) else None
        if isinstance(juncture, dict) and int(juncture.get("total") or 0) > 0:
            report_lines.append("### Juncture")
            report_lines.append("")
            report_lines.append(f"- **Legato**: {int(juncture.get('legato') or 0)}")
            report_lines.append(f"- **Staccato**: {int(juncture.get('staccato') or 0)}")
            report_lines.append(f"- **Staccato Ratio**: {float(juncture.get('staccato_ratio') or 0.0):.2f}")
            report_lines.append("")

        report_lines.append("---")
        report_lines.append("")

    report_lines.append("## Overall Assessment")
    report_lines.append("")

    avg = sum(stabilities) / len(stabilities) if stabilities else 0.0
    report_lines.append(f"- **Average Stability**: {avg:.2f}/1.0")
    if avg > 0.7:
        report_lines.append("- **Character**: Stable, resolved, certain")
    elif avg < 0.4:
        report_lines.append("- **Character**: Unstable, tense, forward-moving")
    else:
        report_lines.append("- **Character**: Balanced, dynamic, varied")

    return {
        "success": True,
        "report_markdown": "\n".join(report_lines),
        "sections": section_outputs,
        "overall": {"average_stability": avg},
    }
