from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class PattisonRhymeType(str, Enum):
    PERFECT = "perfect"
    FAMILY = "family"
    ADDITIVE = "additive"
    SUBTRACTIVE = "subtractive"
    ASSONANCE = "assonance"
    CONSONANCE = "consonance"
    NONE = "none"


@dataclass(frozen=True)
class Phoneme:
    arpabet: str
    is_vowel: bool
    stress_level: int  # 0,1,2 for vowels; -1 for consonants

    @property
    def base(self) -> str:
        return self.arpabet.rstrip("012") if self.is_vowel else self.arpabet


@dataclass(frozen=True)
class WordPhonetics:
    text: str
    phonemes: List[Phoneme]
    syllable_count: int
    stressed_vowel: str
    onset_consonants: List[str]
    post_vowel_consonants: List[str]


@dataclass(frozen=True)
class RhymeClassification:
    word1: str
    word2: str
    pattison_type: PattisonRhymeType
    pattison_stability: float
    explanation: str
    vowel1: str = ""
    vowel2: str = ""
    post1: Optional[List[str]] = None
    post2: Optional[List[str]] = None
