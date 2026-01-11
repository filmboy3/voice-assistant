import re
from typing import List


_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


_QUOTE_CHARS = {
    '"',
    "“",
    "”",
    "„",
    "‟",
    "«",
    "»",
    "‹",
    "›",
    "〝",
    "〞",
    "〟",
    "＂",
    "`",
    "´",
}


_APOSTROPHE_CHARS = {
    "'",
    "’",
    "‘",
    "‛",
    "ʼ",
    "＇",
}


def normalize_lyric_line(text: str) -> str:
    s = text or ""
    if not s:
        return ""
    out: List[str] = []
    for i, ch in enumerate(s):
        if ch in _QUOTE_CHARS:
            continue
        if ch in _APOSTROPHE_CHARS:
            prev = s[i - 1] if i > 0 else ""
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if prev.isalpha() and nxt.isalpha():
                out.append("'")
            continue
        out.append(ch)
    return "".join(out)


def tokenize_words(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]
