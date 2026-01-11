from typing import Optional


PATTISON_PHONETIC_FAMILIES = {
    "plosives": {
        "voiced": {"B", "D", "G"},
        "unvoiced": {"P", "T", "K"},
    },
    "fricatives": {
        "voiced": {"V", "DH", "Z", "ZH", "JH"},
        "unvoiced": {"F", "TH", "S", "SH", "CH"},
    },
    "nasals": {
        "all": {"M", "N", "NG"},
    },
}


def get_family(consonant: str) -> Optional[str]:
    c = (consonant or "").strip().upper()
    if not c:
        return None

    if c in PATTISON_PHONETIC_FAMILIES["plosives"]["voiced"] or c in PATTISON_PHONETIC_FAMILIES["plosives"]["unvoiced"]:
        return "plosives"

    if c in PATTISON_PHONETIC_FAMILIES["fricatives"]["voiced"] or c in PATTISON_PHONETIC_FAMILIES["fricatives"]["unvoiced"]:
        return "fricatives"

    if c in PATTISON_PHONETIC_FAMILIES["nasals"]["all"]:
        return "nasals"

    return None


def same_family(c1: str, c2: str) -> bool:
    f1 = get_family(c1)
    f2 = get_family(c2)
    return bool(f1 and f2 and f1 == f2)
