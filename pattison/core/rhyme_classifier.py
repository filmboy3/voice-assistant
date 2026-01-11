from __future__ import annotations

from typing import List, Tuple, Optional

from .phonetic_engine import PhoneticEngine
from .phonetic_families import same_family
from .types import PattisonRhymeType, RhymeClassification, WordPhonetics


_PATTISON_STABILITY = {
    PattisonRhymeType.PERFECT: 1.0,
    PattisonRhymeType.FAMILY: 0.85,
    PattisonRhymeType.ADDITIVE: 0.7,
    PattisonRhymeType.SUBTRACTIVE: 0.7,
    PattisonRhymeType.ASSONANCE: 0.5,
    PattisonRhymeType.CONSONANCE: 0.3,
    PattisonRhymeType.NONE: 0.0,
}


class RhymeClassifier:
    def __init__(self, engine: PhoneticEngine):
        self.engine = engine

    def classify(self, word1: str, word2: str, wp1: Optional[WordPhonetics] = None, wp2: Optional[WordPhonetics] = None) -> RhymeClassification:
        wps1 = [wp1] if wp1 else self.engine.get_word_phonetics_variants(word1)
        wps2 = [wp2] if wp2 else self.engine.get_word_phonetics_variants(word2)
        
        if not wps1 or not wps2:
            return self._result(word1, word2, PattisonRhymeType.NONE, "Could not analyze one or both words")

        best: Tuple[float, int, RhymeClassification] | None = None

        for wp1 in wps1:
            for wp2 in wps2:
                rhyme_type, explanation = self._determine(
                    wp1.stressed_vowel,
                    wp2.stressed_vowel,
                    wp1.onset_consonants,
                    wp2.onset_consonants,
                    wp1.post_vowel_consonants,
                    wp2.post_vowel_consonants,
                )

                stability = _PATTISON_STABILITY[rhyme_type]
                # Prefer higher Pattison stability; for ties prefer a "tighter" rhyme (more post consonants matched)
                tie_strength = min(len(wp1.post_vowel_consonants), len(wp2.post_vowel_consonants))

                rc = RhymeClassification(
                    word1=word1,
                    word2=word2,
                    pattison_type=rhyme_type,
                    pattison_stability=stability,
                    explanation=explanation,
                    vowel1=wp1.stressed_vowel,
                    vowel2=wp2.stressed_vowel,
                    post1=list(wp1.post_vowel_consonants),
                    post2=list(wp2.post_vowel_consonants),
                )

                key = (float(stability), tie_strength, rc)
                if best is None or key[:2] > best[:2]:
                    best = key

        if best is None:
            return self._result(word1, word2, PattisonRhymeType.NONE, "Could not analyze one or both words")
        return best[2]

    def _determine(
        self,
        vowel1: str,
        vowel2: str,
        onset1: List[str],
        onset2: List[str],
        post1: List[str],
        post2: List[str],
    ) -> Tuple[PattisonRhymeType, str]:
        if vowel1 == vowel2:
            if post1 == post2 and onset1 != onset2:
                return (PattisonRhymeType.PERFECT, f"Same vowel ({vowel1}), same post-consonants, different onsets")

            if post1 == post2 and onset1 == onset2:
                return (PattisonRhymeType.PERFECT, f"Same vowel ({vowel1}), same post-consonants")

            if post1 and post2 and len(post1) == len(post2) and self._lists_same_family(post1, post2):
                return (PattisonRhymeType.FAMILY, f"Same vowel ({vowel1}), post-consonants in same family")

            if self._is_additive(post1, post2):
                return (PattisonRhymeType.ADDITIVE, f"Same vowel ({vowel1}), one word adds post-consonants")

            if self._is_additive(post2, post1):
                return (PattisonRhymeType.SUBTRACTIVE, f"Same vowel ({vowel1}), one word removes post-consonants")

            return (PattisonRhymeType.ASSONANCE, f"Same vowel ({vowel1}), unrelated post-consonants")

        if post1 == post2 and post1:
            return (PattisonRhymeType.CONSONANCE, f"Different vowels ({vowel1}/{vowel2}), same post-consonants")

        if post1 and post2 and len(post1) == len(post2) and self._lists_same_family(post1, post2):
            return (PattisonRhymeType.CONSONANCE, f"Different vowels, post-consonants in same family")

        return (PattisonRhymeType.NONE, f"Different vowels ({vowel1}/{vowel2}), unrelated post-consonants")

    def _lists_same_family(self, xs: List[str], ys: List[str]) -> bool:
        if len(xs) != len(ys):
            return False
        return all(same_family(a, b) for a, b in zip(xs, ys))

    def _is_additive(self, shorter: List[str], longer: List[str]) -> bool:
        if len(shorter) >= len(longer):
            return False
        if not shorter:
            return True
        return longer[: len(shorter)] == shorter

    def _result(self, word1: str, word2: str, t: PattisonRhymeType, explanation: str) -> RhymeClassification:
        return RhymeClassification(
            word1=word1,
            word2=word2,
            pattison_type=t,
            pattison_stability=_PATTISON_STABILITY[t],
            explanation=explanation,
        )
