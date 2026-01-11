from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class BookExercise:
    id: str
    exercise_label: str
    chapter_label: str
    number: Optional[int]
    start_line: int
    end_line: int
    prompt_text: str
    starter_word: Optional[str]


_CACHE: Dict[str, List[BookExercise]] = {}


def _parse_chapter_label(line: str) -> Optional[str]:
    m = re.match(r"^\s*CHAPTER\s+(.+?)\s*$", (line or "").strip(), flags=re.IGNORECASE)
    if m:
        return f"CHAPTER {m.group(1).strip()}"
    return None


def _extract_starter_suggestions(text: str, *, starter_word: Optional[str]) -> List[str]:
    if not text:
        return [starter_word] if starter_word else []

    out: List[str] = []
    seen = set()

    def push(s: str) -> None:
        s2 = (s or "").strip()
        s2 = re.sub(r"\s+", " ", s2).strip()
        s2 = re.sub(r"^[\s\-–—:;,.!?]+", "", s2).strip()
        s2 = re.sub(r"[\s\-–—:;,.!?]+$", "", s2).strip()
        if not s2:
            return
        if len(s2) > 40:
            return
        if "\n" in s2 or "\r" in s2:
            return

        words = [w for w in re.split(r"\s+", s2) if w]
        if len(words) > 3:
            return
        if not any(re.search(r"[A-Za-z]", w) for w in words):
            return

        key = s2.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(s2)

    if starter_word:
        push(starter_word)

    for m in re.finditer(r"[\"“](.+?)[\"”]", text, flags=re.DOTALL):
        push(m.group(1) or "")

    return out


def _parse_exercise_number(line: str) -> Optional[int]:
    m = re.match(r"^\s*EXERCISE\s+(\d+)\s*$", (line or "").strip(), flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _extract_starter_word(text: str) -> Optional[str]:
    if not text:
        return None

    m = re.search(r"Use the word\s+[\"“](.+?)[\"”]\s+as", text, flags=re.IGNORECASE)
    if m:
        w = (m.group(1) or "").strip()
        return w or None

    # Handle:
    # - Ready? “Pepper.” Go!
    # - Ready? “Pepper”. Go!
    # - Ready? "Pepper." Go!
    m = re.search(r"Ready\?\s*[\"“](.+?)[\"”]\s*Go", text, flags=re.IGNORECASE)
    if m:
        w = (m.group(1) or "").strip()
        w = re.sub(r"[\.!\?]+\s*$", "", w).strip()
        return w or None

    m = re.search(r"Ready\?\s*[\"“](.+?)[\"”]\s*\.\s*Go", text, flags=re.IGNORECASE)
    if m:
        w = (m.group(1) or "").strip()
        w = re.sub(r"[\.!\?]+\s*$", "", w).strip()
        return w or None

    return None


def load_book_exercises(*, book_path: str) -> List[BookExercise]:
    p = Path(book_path)
    cache_key = str(p.resolve())
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if not p.exists():
        _CACHE[cache_key] = []
        return []

    raw_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()

    current_chapter = ""
    ex_starts: List[Dict[str, Any]] = []

    for idx, line in enumerate(raw_lines, start=1):
        chap = _parse_chapter_label(line)
        if chap:
            current_chapter = chap

        ex_num = _parse_exercise_number(line)
        if ex_num is not None:
            ex_starts.append({
                "line": idx,
                "chapter": current_chapter,
                "number": ex_num,
            })

    exercises: List[BookExercise] = []
    for i, s in enumerate(ex_starts):
        start_line = int(s["line"])
        end_line = int(ex_starts[i + 1]["line"]) - 1 if i + 1 < len(ex_starts) else len(raw_lines)
        chunk = "\n".join(raw_lines[start_line - 1 : end_line]).strip()
        number = s.get("number")
        label = f"EXERCISE {number}" if isinstance(number, int) else "EXERCISE"
        ex_id = f"book_ex_{i + 1}"
        starter = _extract_starter_word(chunk)
        exercises.append(
            BookExercise(
                id=ex_id,
                exercise_label=label,
                chapter_label=(s.get("chapter") or ""),
                number=number if isinstance(number, int) else None,
                start_line=start_line,
                end_line=end_line,
                prompt_text=chunk,
                starter_word=starter,
            )
        )

    _CACHE[cache_key] = exercises
    return exercises


def list_book_exercises(*, book_path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ex in load_book_exercises(book_path=book_path):
        preview = ex.prompt_text.splitlines()
        preview_txt = "\n".join(preview[:8]).strip()
        starter_suggestions = _extract_starter_suggestions(ex.prompt_text, starter_word=ex.starter_word)
        out.append(
            {
                "id": ex.id,
                "exercise_label": ex.exercise_label,
                "chapter": ex.chapter_label,
                "number": ex.number,
                "starter_word": ex.starter_word,
                "starter_suggestions": starter_suggestions,
                "preview": preview_txt,
                "start_line": ex.start_line,
                "end_line": ex.end_line,
            }
        )
    return out


def get_book_exercise(*, book_path: str, exercise_id: str) -> Optional[Dict[str, Any]]:
    for ex in load_book_exercises(book_path=book_path):
        if ex.id == exercise_id:
            starter_suggestions = _extract_starter_suggestions(ex.prompt_text, starter_word=ex.starter_word)
            return {
                "id": ex.id,
                "exercise_label": ex.exercise_label,
                "chapter": ex.chapter_label,
                "number": ex.number,
                "starter_word": ex.starter_word,
                "starter_suggestions": starter_suggestions,
                "prompt_text": ex.prompt_text,
                "start_line": ex.start_line,
                "end_line": ex.end_line,
            }
    return None
