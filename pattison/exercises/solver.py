from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..core.phonetic_engine import PhoneticEngine
from ..core.rhyme_classifier import RhymeClassifier
from ..structure.analyzer import analyze_section
from .definitions import EXERCISES


def _build_patbook_style_table(
    *,
    analysis: Dict[str, Any],
    engine: PhoneticEngine,
) -> List[Dict[str, Any]]:
    rows = analysis.get("lines") if isinstance(analysis, dict) else None
    if not isinstance(rows, list):
        return []

    raw = str(analysis.get("raw_rhyme_scheme") or "")
    scheme = str(analysis.get("rhyme_scheme") or "")

    out: List[Dict[str, Any]] = []
    for i, lr in enumerate(rows, start=1):
        if not isinstance(lr, dict):
            continue
        text = (lr.get("text") or "").strip()
        end_word = (lr.get("end_word") or "").strip()
        stresses = lr.get("primary_stress_count")

        wp = engine.get_word_phonetics(end_word) if end_word else None
        end_phonetics = None
        if wp is not None:
            end_phonetics = {
                "stressed_vowel": wp.stressed_vowel,
                "onset_consonants": list(wp.onset_consonants),
                "post_vowel_consonants": list(wp.post_vowel_consonants),
                "syllable_count": int(wp.syllable_count),
            }

        out.append(
            {
                "line": i,
                "rhyme_raw": raw[i - 1] if i - 1 < len(raw) else "",
                "rhyme_structural": scheme[i - 1] if i - 1 < len(scheme) else "",
                "stresses": stresses,
                "end_word": end_word,
                "end_word_phonetics": end_phonetics,
                "text": text,
            }
        )

    return out


def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "t", "1", "yes", "y", "on"}:
            return True
        if s in {"false", "f", "0", "no", "n", "off", ""}:
            return False
    return False


def _normalize_scheme(raw_labels: List[str]) -> str:
    remap: Dict[str, str] = {}
    next_letter_ord = ord("A")
    out: List[str] = []
    for ch in raw_labels:
        if ch == "X":
            out.append("X")
            continue
        if ch not in remap:
            remap[ch] = chr(next_letter_ord)
            next_letter_ord += 1
        out.append(remap[ch])
    return "".join(out)


def _structural_scheme(raw_labels: List[str]) -> str:
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


def _scheme_with_allowed_types(
    *,
    endings: List[str],
    classifier: RhymeClassifier,
    allowed_types: set[str],
) -> Dict[str, Any]:
    labels: List[str] = []
    next_label_ord = ord("A")

    for i, w in enumerate(endings):
        if not w:
            labels.append("X")
            continue

        matched_label: Optional[str] = None
        for j in range(i - 1, -1, -1):
            w_prev = endings[j]
            if not w_prev:
                continue
            res = classifier.classify(w, w_prev)
            if res.pattison_type.value in allowed_types:
                matched_label = labels[j]
                break

        if matched_label and matched_label != "X":
            labels.append(matched_label)
            continue

        labels.append(chr(next_label_ord))
        next_label_ord += 1
        if next_label_ord > ord("Z"):
            next_label_ord = ord("A")

    raw = _normalize_scheme(labels)
    structural = _structural_scheme(list(raw))
    return {"raw": raw, "structural": structural}


def _parse_target_scheme(s: Any) -> Optional[str]:
    if s is None:
        return None
    if not isinstance(s, str):
        return None
    raw = re.sub(r"\s+", "", s.strip().upper())
    if not raw:
        return None
    if not all((ch == "X" or ("A" <= ch <= "Z")) for ch in raw):
        return None
    return _normalize_scheme(list(raw))


def _parse_target_stresses(s: Any) -> Optional[List[int]]:
    if s is None:
        return None
    if not isinstance(s, str):
        return None
    raw = re.sub(r"\s+", "", s.strip())
    if not raw:
        return None

    parts = [p for p in raw.split("-") if p != ""]
    if not parts:
        return None
    out: List[int] = []
    for p in parts:
        if not re.fullmatch(r"\d+", p):
            return None
        try:
            out.append(int(p))
        except Exception:
            return None
    return out


def describe_exercise(exercise_id: str) -> Dict[str, Any]:
    ex = EXERCISES.get(exercise_id)
    if not isinstance(ex, dict):
        return {"success": False, "error": "Unknown exercise_id"}
    return {
        "success": True,
        "exercise_id": exercise_id,
        "chapter": ex.get("chapter"),
        "title": ex.get("title"),
        "inputs": ex.get("inputs") or [],
    }


def _common_meter(lengths: List[int]) -> bool:
    if len(lengths) != 4:
        return False
    if lengths[0] > lengths[1] and lengths[2] > lengths[3] and lengths[0] == lengths[2] and lengths[1] == lengths[3]:
        return True
    return False


def solve_exercise(
    exercise_id: str,
    *,
    payload: Dict[str, Any],
    cmu_path: Optional[str] = None,
    jonathan_db_path: Optional[str] = None,
) -> Dict[str, Any]:
    if exercise_id == "ch4_rhyme_classify":
        word1 = payload.get("word1")
        word2 = payload.get("word2")
        if not isinstance(word1, str) or not word1.strip():
            return {"success": False, "error": "Missing required field: word1"}
        if not isinstance(word2, str) or not word2.strip():
            return {"success": False, "error": "Missing required field: word2"}

        engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
        cls = RhymeClassifier(engine)
        res = cls.classify(word1, word2)
        return {
            "success": True,
            "exercise_id": exercise_id,
            "result": {
                "word1": word1,
                "word2": word2,
                "pattison_type": res.pattison_type.value,
                "pattison_stability": res.pattison_stability,
                "explanation": res.explanation,
            },
        }

    if exercise_id == "ch14_stress_count":
        line = payload.get("line")
        if not isinstance(line, str) or not line.strip():
            return {"success": False, "error": "Missing required field: line"}

        engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
        return {
            "success": True,
            "exercise_id": exercise_id,
            "result": {"line": line, "primary_stress_count": engine.count_line_primary_stresses(line)},
        }

    if exercise_id == "ch14_common_meter_check":
        lines = payload.get("lines")
        if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
            return {"success": False, "error": "Missing or invalid field: lines (must be array of strings)"}
        cleaned = [l.strip() for l in lines if l and l.strip()]
        if len(cleaned) != 4:
            return {"success": False, "error": "Common meter check requires exactly 4 non-empty lines"}

        engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
        lengths = [engine.count_line_primary_stresses(l) for l in cleaned]
        return {
            "success": True,
            "exercise_id": exercise_id,
            "result": {"line_stress_counts": lengths, "is_common_meter": _common_meter(lengths)},
        }

    if exercise_id == "ch19_pattern_drill":
        lines = payload.get("lines")
        if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
            return {"success": False, "error": "Missing or invalid field: lines (must be array of strings)"}

        return {
            "success": True,
            "exercise_id": exercise_id,
            "result": analyze_section(
                [l for l in lines if isinstance(l, str)],
                cmu_path=cmu_path,
                jonathan_db_path=jonathan_db_path,
            ),
        }

    if exercise_id == "ch19_comprehensive_section_readout":
        lines = payload.get("lines")
        if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
            return {"success": False, "error": "Missing or invalid field: lines (must be array of strings)"}

        cleaned = [l.strip() for l in lines if isinstance(l, str) and l.strip()]
        if not cleaned:
            return {"success": False, "error": "Provide at least 1 non-empty line"}

        include_consonance = _coerce_bool(payload.get("include_consonance_in_scheme"))

        # Use section-based analyzer for proper stanza-by-stanza rhyme schemes
        from pattison.structure.section_analyzer import analyze_song_by_sections
        
        section_analysis = analyze_song_by_sections(
            cleaned,
            cmu_path=cmu_path,
            jonathan_db_path=jonathan_db_path,
            include_consonance_in_scheme=include_consonance,
        )
        
        # For backward compatibility, also generate old-style single-section analysis
        analysis = analyze_section(
            cleaned,
            cmu_path=cmu_path,
            jonathan_db_path=jonathan_db_path,
            include_consonance_in_scheme=include_consonance,
        )

        engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
        classifier = RhymeClassifier(engine)
        table = _build_patbook_style_table(analysis=analysis, engine=engine)

        endings: List[str] = []
        for row in table:
            if not isinstance(row, dict):
                continue
            ew = (row.get("end_word") or "").strip()
            endings.append(ew)

        pairwise_end_rhymes: List[Dict[str, Any]] = []
        for i in range(len(endings)):
            for j in range(i + 1, len(endings)):
                w1 = endings[i]
                w2 = endings[j]
                if not w1 or not w2:
                    continue
                res = classifier.classify(w1, w2)
                pairwise_end_rhymes.append(
                    {
                        "line1": i + 1,
                        "line2": j + 1,
                        "word1": w1,
                        "word2": w2,
                        "pattison_type": res.pattison_type.value,
                        "pattison_stability": res.pattison_stability,
                        "explanation": res.explanation,
                        "details": {
                            "vowel1": res.vowel1,
                            "vowel2": res.vowel2,
                            "post1": res.post1,
                            "post2": res.post2,
                        },
                    }
                )

        schemes = {
            "default": {
                "raw": str(analysis.get("raw_rhyme_scheme") or ""),
                "structural": str(analysis.get("rhyme_scheme") or ""),
            },
            "perfect_only": _scheme_with_allowed_types(
                endings=endings,
                classifier=classifier,
                allowed_types={"perfect"},
            ),
            "perfect_or_family": _scheme_with_allowed_types(
                endings=endings,
                classifier=classifier,
                allowed_types={"perfect", "family"},
            ),
        }

        report_markdown = ""
        try:
            from pattison.reports.analysis_report import generate_analysis_report

            report = generate_analysis_report(
                lines=cleaned,
                cmu_path=cmu_path,
                jonathan_db_path=jonathan_db_path,
                include_consonance_in_scheme=include_consonance,
            )
            if isinstance(report, dict) and report.get("success") is True:
                report_markdown = str(report.get("report_markdown") or "")
        except Exception:
            report_markdown = ""

        # Add per-line render spans for UI highlighting
        per_line_render: List[Dict[str, Any]] = []
        for idx, line_text in enumerate(cleaned):
            stress_spans = engine.line_stress_spans(line_text)
            # Determine end-word span (last word token)
            end_word_span = None
            for span in reversed(stress_spans):
                if span["is_word"]:
                    end_word_span = {"start": span["start"], "end": span["end"], "text": span["text"]}
                    break
            per_line_render.append({
                "line_number": idx + 1,
                "text": line_text,
                "stress_spans": stress_spans,
                "end_word_span": end_word_span,
            })

        return {
            "success": True,
            "exercise_id": exercise_id,
            "result": {
                "include_consonance_in_scheme": include_consonance,
                "schemes": schemes,
                "patbook_style_table": table,
                "pairwise_end_rhymes": pairwise_end_rhymes,
                "analysis": analysis,
                "section_analysis": section_analysis,  # NEW: stanza-by-stanza analysis
                "report_markdown": report_markdown,
                "per_line_render": per_line_render,
            },
        }

    if exercise_id == "ch19_section_constraints_validator":
        lines = payload.get("lines")
        if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
            return {"success": False, "error": "Missing or invalid field: lines (must be array of strings)"}

        cleaned = [l.strip() for l in lines if isinstance(l, str) and l.strip()]
        if not cleaned:
            return {"success": False, "error": "Provide at least 1 non-empty line"}

        target_scheme = _parse_target_scheme(payload.get("target_scheme"))
        target_stresses = _parse_target_stresses(payload.get("target_stresses"))
        if target_scheme is None and target_stresses is None:
            return {
                "success": False,
                "error": "Provide at least one constraint: target_scheme and/or target_stresses",
            }

        scheme_mode_raw = payload.get("scheme_mode")
        scheme_mode = (scheme_mode_raw or "default") if isinstance(scheme_mode_raw, str) else "default"
        scheme_mode = scheme_mode.strip().lower() or "default"
        if scheme_mode not in {"default", "perfect_only", "perfect_or_family"}:
            return {"success": False, "error": "Invalid field: scheme_mode (default, perfect_only, perfect_or_family)"}

        include_consonance = _coerce_bool(payload.get("include_consonance_in_scheme"))

        analysis = analyze_section(
            cleaned,
            cmu_path=cmu_path,
            jonathan_db_path=jonathan_db_path,
            include_consonance_in_scheme=include_consonance,
        )

        engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
        classifier = RhymeClassifier(engine)
        table = _build_patbook_style_table(analysis=analysis, engine=engine)

        end_words: List[str] = []
        stress_counts: List[Optional[int]] = []
        for row in table:
            if not isinstance(row, dict):
                continue
            end_words.append(str(row.get("end_word") or "").strip())
            sc = row.get("stresses")
            stress_counts.append(int(sc) if isinstance(sc, int) else None)

        if scheme_mode == "default":
            actual_scheme = {
                "raw": str(analysis.get("raw_rhyme_scheme") or ""),
                "structural": str(analysis.get("rhyme_scheme") or ""),
            }
        elif scheme_mode == "perfect_only":
            actual_scheme = _scheme_with_allowed_types(
                endings=end_words,
                classifier=classifier,
                allowed_types={"perfect"},
            )
        else:
            actual_scheme = _scheme_with_allowed_types(
                endings=end_words,
                classifier=classifier,
                allowed_types={"perfect", "family"},
            )

        actual_structural = str(actual_scheme.get("structural") or "")

        scheme_ok = True
        scheme_errors: List[str] = []
        expected_structural = target_scheme
        if expected_structural is not None:
            if len(expected_structural) != len(cleaned):
                scheme_ok = False
                scheme_errors.append(
                    f"target_scheme length {len(expected_structural)} does not match number of lines {len(cleaned)}"
                )
            elif len(actual_structural) != len(cleaned):
                scheme_ok = False
                scheme_errors.append(
                    f"computed scheme length {len(actual_structural)} does not match number of lines {len(cleaned)}"
                )
            elif expected_structural != actual_structural:
                scheme_ok = False
                scheme_errors.append(f"scheme mismatch: expected {expected_structural} got {actual_structural}")

        stresses_ok = True
        stress_errors: List[str] = []
        if target_stresses is not None:
            if len(target_stresses) != len(cleaned):
                stresses_ok = False
                stress_errors.append(
                    f"target_stresses length {len(target_stresses)} does not match number of lines {len(cleaned)}"
                )
            else:
                for i, expected in enumerate(target_stresses):
                    got = stress_counts[i] if i < len(stress_counts) else None
                    if got is None or got != expected:
                        stresses_ok = False
                        stress_errors.append(f"stress mismatch on line {i + 1}: expected {expected} got {got}")

        passed = True
        if expected_structural is not None:
            passed = passed and scheme_ok
        if target_stresses is not None:
            passed = passed and stresses_ok

        per_line: List[Dict[str, Any]] = []
        for i, text in enumerate(cleaned, start=1):
            exp_scheme = expected_structural[i - 1] if (expected_structural and i - 1 < len(expected_structural)) else None
            act_scheme = actual_structural[i - 1] if i - 1 < len(actual_structural) else None
            exp_stress = target_stresses[i - 1] if (target_stresses and i - 1 < len(target_stresses)) else None
            act_stress = stress_counts[i - 1] if i - 1 < len(stress_counts) else None
            per_line.append(
                {
                    "line": i,
                    "text": text,
                    "end_word": end_words[i - 1] if i - 1 < len(end_words) else "",
                    "scheme": {
                        "expected": exp_scheme,
                        "actual": act_scheme,
                        "ok": (exp_scheme is None) or (exp_scheme == act_scheme),
                    },
                    "stresses": {
                        "expected": exp_stress,
                        "actual": act_stress,
                        "ok": (exp_stress is None) or (exp_stress == act_stress),
                    },
                }
            )

        return {
            "success": True,
            "exercise_id": exercise_id,
            "result": {
                "passed": passed,
                "constraints": {
                    "target_scheme": expected_structural,
                    "target_stresses": target_stresses,
                    "scheme_mode": scheme_mode,
                    "include_consonance_in_scheme": include_consonance,
                },
                "computed": {
                    "scheme": actual_scheme,
                    "stress_counts": stress_counts,
                },
                "diagnostics": {
                    "scheme_ok": scheme_ok,
                    "scheme_errors": scheme_errors,
                    "stresses_ok": stresses_ok,
                    "stress_errors": stress_errors,
                    "per_line": per_line,
                },
            },
        }

    return {"success": False, "error": "Unknown exercise_id"}


def validate_exercise(
    exercise_id: str,
    *,
    payload: Dict[str, Any],
    cmu_path: Optional[str] = None,
    jonathan_db_path: Optional[str] = None,
) -> Dict[str, Any]:
    # For V1, validation is equivalent to solving deterministically.
    out = solve_exercise(exercise_id, payload=payload, cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
    if not out.get("success"):
        return out
    return {"success": True, "exercise_id": exercise_id, "validated": True, "result": out.get("result")}
