from __future__ import annotations

import re
import json
import gzip
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tokenize import normalize_lyric_line, tokenize_words
from .types import Phoneme, WordPhonetics
from .builtin_cmu_expanded import BUILTIN_CMU as EXPANDED_BUILTIN_CMU


_CMU_VOWELS = {
    "AA",
    "AE",
    "AH",
    "AO",
    "AW",
    "AY",
    "EH",
    "ER",
    "EY",
    "IH",
    "IY",
    "OW",
    "OY",
    "UH",
    "UW",
}

# Function words excluded from stress counting per Pattison methodology.
# These words typically don't carry metrical stress in natural speech.
_FUNCTION_WORDS = {
    # Articles
    "a", "an", "the",
    # Pronouns
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their",
    # Prepositions
    "of", "to", "in", "on", "at", "as", "by", "for", "from", "with", "beneath", "below", "above",
    # Conjunctions
    "and", "or", "nor", "but", "so", "yet",
    # Auxiliary/linking verbs
    "is", "are", "was", "were", "be", "been", "am",
    "have", "has",
    "do", "does", "did",
    "can", "could", "will", "would", "shall", "should", "may", "might", "must",
    # Determiners/demonstratives
    "this", "that", "these", "those", "which", "who", "whom",
    # Adverbs that don't carry stress
    "then", "than",
}


_BUILTIN_CMU: Dict[str, List[str]] = {
    "CAT": ["K", "AE1", "T"],
    "HAT": ["HH", "AE1", "T"],
    "RUB": ["R", "AH1", "B"],
    "UP": ["AH1", "P"],
    "THUD": ["TH", "AH1", "D"],
    "LOVE": ["L", "AH1", "V"],
    "ABOVE": ["AH0", "B", "AH1", "V"],
    "LIVE": ["L", "IH1", "V"],
    "ENOUGH": ["IH0", "N", "AH1", "F"],
    "FREE": ["F", "R", "IY1"],
    "FREED": ["F", "R", "IY1", "D"],
    "FUN": ["F", "AH1", "N"],
    "ON": ["AA1", "N"],
    "MARY": ["M", "EH1", "R", "IY0"],
    "HAD": ["HH", "AE1", "D"],
    "LITTLE": ["L", "IH1", "T", "AH0", "L"],
    "LAMB": ["L", "AE1", "M"],
    "ITS": ["IH1", "T", "S"],
    "FLEECE": ["F", "L", "IY1", "S"],
    "WAS": ["W", "AA1", "Z"],
    "WHITE": ["W", "AY1", "T"],
    "SNOW": ["S", "N", "OW1"],
    "GO": ["G", "OW1"],
    "ROAD": ["R", "OW1", "D"],
    "RED": ["R", "EH1", "D"],
    "RUN": ["R", "AH1", "N"],
    "STRONG": ["S", "T", "R", "AO1", "NG"],
    "LONG": ["L", "AO1", "NG"],
    "CUT": ["K", "AH1", "T"],
    "LUCK": ["L", "AH1", "K"],
    "TIDE": ["T", "AY1", "D"],
    "MINE": ["M", "AY1", "N"],
    "FRIEND": ["F", "R", "EH1", "N", "D"],
    "WIND": ["W", "IH1", "N", "D"],
    "FIND": ["F", "AY1", "N", "D"],
    "SIGN": ["S", "AY1", "N"],
    "TRUCK": ["T", "R", "AH1", "K"],
    "DUCK": ["D", "AH1", "K"],
    "STUCK": ["S", "T", "AH1", "K"],
    "SHUT": ["SH", "AH1", "T"],
    "CUP": ["K", "AH1", "P"],
    "PUP": ["P", "AH1", "P"],
    "BUG": ["B", "AH1", "G"],
    "RUG": ["R", "AH1", "G"],
    # Common contractions without apostrophes (for user input normalization)
    "DIDNT": ["D", "IH1", "D", "AH0", "N", "T"],
    "DONT": ["D", "OW1", "N", "T"],
    "WONT": ["W", "OW1", "N", "T"],
    "CANT": ["K", "AE1", "N", "T"],
    "ISNT": ["IH1", "Z", "AH0", "N", "T"],
    "WASNT": ["W", "AA1", "Z", "AH0", "N", "T"],
    "WERENT": ["W", "ER1", "AH0", "N", "T"],
    "HAVENT": ["HH", "AE1", "V", "AH0", "N", "T"],
    "HASNT": ["HH", "AE1", "Z", "AH0", "N", "T"],
    "HADNT": ["HH", "AE1", "D", "AH0", "N", "T"],
    "WOULDNT": ["W", "UH1", "D", "AH0", "N", "T"],
    "COULDNT": ["K", "UH1", "D", "AH0", "N", "T"],
    "SHOULDNT": ["SH", "UH1", "D", "AH0", "N", "T"],
    "WEVE": ["W", "IY1", "V"],
    "YOUVE": ["Y", "UW1", "V"],
    "THEYVE": ["DH", "EY1", "V"],
    "IVE": ["AY1", "V"],
    "YOURE": ["Y", "UH1", "R"],
    "THEYRE": ["DH", "EH1", "R"],
    "WERE": ["W", "ER1"],  # contraction of "we are"
    "ILL": ["AY1", "L"],
    "YOULL": ["Y", "UW1", "L"],
    "THEYLL": ["DH", "EY1", "L"],
    "WELL": ["W", "IY1", "L"],  # contraction of "we will"
    "THATS": ["DH", "AE1", "T", "S"],
    "WHATS": ["W", "AH1", "T", "S"],
    "HERES": ["HH", "IH1", "R", "Z"],
    "THERES": ["DH", "EH1", "R", "Z"],
    # Informal spellings
    "STANDIN": ["S", "T", "AE1", "N", "D", "IH0", "N"],
    "RUNNIN": ["R", "AH1", "N", "IH0", "N"],
    "WALKIN": ["W", "AO1", "K", "IH0", "N"],
    "TALKIN": ["T", "AO1", "K", "IH0", "N"],
    "SINGIN": ["S", "IH1", "NG", "IH0", "N"],
    "DANCIN": ["D", "AE1", "N", "S", "IH0", "N"],
    "LOVIN": ["L", "AH1", "V", "IH0", "N"],
    "LIVIN": ["L", "IH1", "V", "IH0", "N"],
}


class PhoneticEngine:
    def __init__(self, cmu_path: Optional[str] = None, jonathan_db_path: Optional[str] = None, phonetic_index_url: Optional[str] = None):
        self._cmu: Dict[str, List[List[str]]] = {}
        # Merge original built-in + expanded built-in
        self._cmu.update({k: [v] for k, v in _BUILTIN_CMU.items()})
        self._cmu.update({k: [v] for k, v in EXPANDED_BUILTIN_CMU.items()})
        if cmu_path:
            self.load_cmu_dict(cmu_path)

        self._jonathan_db_path = (jonathan_db_path or "").strip() or None
        self._jonathan_db: Optional[Dict[str, Any]] = None
        
        # Phonetic index shard cache
        self._phonetic_index_url = phonetic_index_url or "https://pub-53b5eb7528ba49eaaf533b48541508ae.r2.dev/phonetics/v1_shards_256"
        self._phonetic_shards: Dict[str, Dict[str, Any]] = {}

    def _load_jonathan_db(self) -> Dict[str, Any]:
        if self._jonathan_db is not None:
            return self._jonathan_db
        if not self._jonathan_db_path:
            self._jonathan_db = {}
            return self._jonathan_db
        p = Path(self._jonathan_db_path)
        if not p.exists():
            self._jonathan_db = {}
            return self._jonathan_db
        try:
            obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            self._jonathan_db = obj if isinstance(obj, dict) else {}
        except Exception:
            self._jonathan_db = {}
        return self._jonathan_db

    def _get_jonathan_pronunciations(self, word: str) -> Optional[List[List[str]]]:
        w = (word or "").strip().lower()
        if not w:
            return None
        db = self._load_jonathan_db()
        entry = db.get(w)
        if not isinstance(entry, dict):
            return None

        prons = entry.get("pronunciations")
        if isinstance(prons, list) and prons and all(isinstance(p, list) for p in prons):
            out: List[List[str]] = []
            for p in prons:
                out.append([str(x).strip() for x in p if str(x).strip()])
            return out or None

        phones = entry.get("phonemes")
        if isinstance(phones, list) and phones:
            return [[str(x).strip() for x in phones if str(x).strip()]]

        return None

    def _shard_id_for_word(self, word: str) -> str:
        """Compute shard ID from SHA256 hash of lowercase word."""
        digest = hashlib.sha256(word.lower().encode("utf-8")).digest()
        return f"{digest[0]:02x}"
    
    def _load_phonetic_shard(self, shard_id: str) -> Dict[str, Any]:
        """Load phonetic index shard from R2 (with caching)."""
        if shard_id in self._phonetic_shards:
            return self._phonetic_shards[shard_id]
        
        try:
            import requests
            url = f"{self._phonetic_index_url}/{shard_id}.json.gz"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            raw = gzip.decompress(resp.content)
            shard = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(shard, dict):
                self._phonetic_shards[shard_id] = shard
                return shard
        except Exception:
            pass
        
        self._phonetic_shards[shard_id] = {}
        return {}
    
    def _get_phonetic_index_pronunciations(self, word: str) -> Optional[List[List[str]]]:
        """Get pronunciations from phonetic index shards."""
        w = (word or "").strip().lower()
        if not w:
            return None
        
        shard_id = self._shard_id_for_word(w)
        shard = self._load_phonetic_shard(shard_id)
        entry = shard.get(w)
        
        if not isinstance(entry, dict):
            return None
        
        phonemes = entry.get("phonemes")
        if isinstance(phonemes, list) and phonemes:
            return [[str(p).strip() for p in phonemes if str(p).strip()]]
        
        return None

    def _get_pronouncing_pronunciations(self, word: str) -> Optional[List[List[str]]]:
        try:
            import pronouncing  # type: ignore
        except Exception:
            return None

        w = (word or "").strip().lower()
        if not w:
            return None

        w = re.sub(r"[^a-zA-Z']+", "", w)
        if not w:
            return None

        try:
            phones = pronouncing.phones_for_word(w)
        except Exception:
            phones = []

        out: List[List[str]] = []
        for p in phones or []:
            if not isinstance(p, str):
                continue
            parts = [x.strip() for x in p.split() if x.strip()]
            if parts:
                out.append(parts)
        return out or None

    def load_cmu_dict(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        try:
            for line in p.read_text(encoding="latin-1", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith(";;;"):
                    continue
                parts = re.split(r"\s+", line)
                if len(parts) < 2:
                    continue
                word = re.sub(r"\(\d+\)$", "", parts[0].upper())
                phones = parts[1:]
                self._cmu.setdefault(word, []).append(phones)
        except Exception:
            return

    def get_phoneme_pronunciations(self, word: str) -> List[List[Phoneme]]:
        w = (word or "").strip()
        if not w:
            return []

        # Priority 1: Jonathan DB (custom overrides)
        j_prons = self._get_jonathan_pronunciations(w)
        if j_prons:
            return [self._parse_arpabet(p) for p in j_prons if p]

        # Priority 2: Built-in CMU (expanded + original)
        key = w.upper()
        prons = self._cmu.get(key) or []
        if prons:
            return [self._parse_arpabet(p) for p in prons if p]

        # Priority 3: Phonetic index shards (from R2)
        idx_prons = self._get_phonetic_index_pronunciations(w)
        if idx_prons:
            return [self._parse_arpabet(p) for p in idx_prons if p]

        # Priority 4: Pronouncing library (fallback)
        p_prons = self._get_pronouncing_pronunciations(w)
        if p_prons:
            return [self._parse_arpabet(p) for p in p_prons if p]

        return []

    def get_phonemes(self, word: str) -> Optional[List[Phoneme]]:
        prons = self.get_phoneme_pronunciations(word)
        return prons[0] if prons else None

    def _parse_arpabet(self, phones: List[str]) -> List[Phoneme]:
        out: List[Phoneme] = []
        for p in phones:
            base = p.rstrip("012")
            is_vowel = base in _CMU_VOWELS
            if is_vowel:
                stress = int(p[-1]) if p[-1].isdigit() else 0
            else:
                stress = -1
            out.append(Phoneme(arpabet=p, is_vowel=is_vowel, stress_level=stress))
        return out

    def get_word_phonetics_variants(self, word: str) -> List[WordPhonetics]:
        out: List[WordPhonetics] = []
        for phonemes in self.get_phoneme_pronunciations(word):
            wp = self._word_phonetics_from_phonemes(word, phonemes)
            if wp:
                out.append(wp)
        return out

    def get_word_phonetics(self, word: str) -> Optional[WordPhonetics]:
        variants = self.get_word_phonetics_variants(word)
        return variants[0] if variants else None

    def get_word_phonetics_from_tags(self, word: str, tags: List[str]) -> Optional[WordPhonetics]:
        """Extract pronunciation from Datamuse tags and convert to WordPhonetics."""
        if not tags: return None
        for tag in tags:
            if tag.startswith("pron:"):
                arpabet_str = tag[5:].strip()
                phones = arpabet_str.split()
                phonemes = self._parse_arpabet(phones)
                return self._word_phonetics_from_phonemes(word, phonemes)
        return None

    def _word_phonetics_from_phonemes(self, word: str, phonemes: List[Phoneme]) -> Optional[WordPhonetics]:
        if not phonemes:
            return None

        vowel_idxs = [i for i, p in enumerate(phonemes) if p.is_vowel]
        syllable_count = len(vowel_idxs)
        if not vowel_idxs:
            return WordPhonetics(
                text=word,
                phonemes=phonemes,
                syllable_count=0,
                stressed_vowel="",
                onset_consonants=[],
                post_vowel_consonants=[],
            )

        # Consider both primary (1) and secondary (2) stress for rhyme purposes.
        # Pattison often rhymes on secondary stress at the end of lines (e.g. "hypnotized", "petticoats").
        # We pick the LAST stressed syllable (1 or 2) as the rhyme anchor.
        stressed_indices = [i for i in vowel_idxs if phonemes[i].stress_level in {1, 2}]
        
        # Fallback to the last vowel if no stress found (shouldn't happen for valid words usually)
        stressed_idx = stressed_indices[-1] if stressed_indices else vowel_idxs[-1]
        stressed_vowel = phonemes[stressed_idx].base

        prev_vowel_idx = None
        for vi in vowel_idxs:
            if vi < stressed_idx:
                prev_vowel_idx = vi
            else:
                break

        onset_start = (prev_vowel_idx + 1) if prev_vowel_idx is not None else 0
        onset = [p.base for p in phonemes[onset_start:stressed_idx] if not p.is_vowel]

        post: List[str] = []
        for p in phonemes[stressed_idx + 1 :]:
            if p.is_vowel:
                break
            post.append(p.base)

        return WordPhonetics(
            text=word,
            phonemes=phonemes,
            syllable_count=syllable_count,
            stressed_vowel=stressed_vowel,
            onset_consonants=onset,
            post_vowel_consonants=post,
        )

    def estimate_stresses(self, word: str, is_line_end: bool = False) -> int:
        """Estimate stress count for a word without phonetic data."""
        w = (word or "").strip().lower()
        if not w:
            return 0
        if w in _FUNCTION_WORDS and not is_line_end:
            return 0
        return 1
    
    def _estimate_phonemes_for_unknown(self, word: str) -> Optional[List[Phoneme]]:
        """Try to estimate phonemes for unknown words by pattern matching.
        
        Strategies:
        1. Strip common suffixes and look up base form
        2. Match word ending patterns to known words
        3. Estimate syllable count from vowel letters
        """
        w = (word or "").strip().lower()
        if not w:
            return None
        
        # Strategy 1: Common suffix stripping
        suffix_map = {
            "in'": "ing",  # standin' -> standing
            "in": "ing",   # standin -> standing
            "n't": "not",  # didn't without apostrophe handled in builtin
            "nt": "not",   # didnt -> didn't
            "'s": "",      # possessive
            "s": "",       # plural (try without)
            "ed": "",      # past tense
            "ly": "",      # adverb
        }
        
        for suffix, replacement in suffix_map.items():
            if w.endswith(suffix) and len(w) > len(suffix) + 2:
                base = w[:-len(suffix)]
                if replacement:
                    base += replacement
                phonemes = self.get_phonemes(base)
                if phonemes:
                    return phonemes
        
        # Strategy 2: Try removing doubled final consonant (runnin -> run + ing)
        if len(w) > 4 and w[-1] == w[-2] and w[-1] not in 'aeiou':
            base = w[:-1]
            phonemes = self.get_phonemes(base)
            if phonemes:
                return phonemes
        
        # Strategy 3: Estimate from vowel count in spelling
        # This gives us syllable count, assume 1 primary stress
        vowel_count = sum(1 for c in w if c in 'aeiouy')
        if vowel_count == 0:
            vowel_count = 1  # Assume at least 1 syllable
        
        # Create synthetic phonemes with estimated stress
        # Primary stress on first syllable (common English pattern)
        synthetic = []
        for i in range(vowel_count):
            stress = 1 if i == 0 else 0
            synthetic.append(Phoneme(arpabet=f"AH{stress}", is_vowel=True, stress_level=stress))
        
        return synthetic if synthetic else None

    def count_line_primary_stresses(self, line: str) -> int:
        """Count primary stresses in a line.
        
        Rules:
        1. Function words are skipped UNLESS they are at line end (natural speech emphasis)
        2. For 3+ syllable words, count both primary and secondary stress
        3. For unknown words, try to estimate via similar word lookup
        """
        words = tokenize_words(line)
        if not words:
            return 0
        
        total = 0
        last_word = words[-1] if words else None
        
        for w in words:
            is_line_end = (w == last_word)
            
            # Function words skip UNLESS at line end where they can carry stress
            if w in _FUNCTION_WORDS and not is_line_end:
                continue
            
            phonemes = self.get_phonemes(w)
            if not phonemes:
                # Try unknown word fallback
                phonemes = self._estimate_phonemes_for_unknown(w)
            
            if phonemes:
                syllable_count = sum(1 for p in phonemes if p.is_vowel)
                
                # For 3+ syllable words, count both primary (1) and secondary (2) stress
                # For shorter words, count only primary stress
                if syllable_count >= 3:
                    total += sum(1 for p in phonemes if p.is_vowel and p.stress_level in {1, 2})
                else:
                    total += sum(1 for p in phonemes if p.is_vowel and p.stress_level == 1)
            else:
                # Final fallback: estimate 1 stress for content words
                if w not in _FUNCTION_WORDS:
                    total += 1
                elif is_line_end:
                    total += 1  # Line-end function word gets stress
        return total

    def line_stress_spans(self, line: str) -> List[Dict[str, Any]]:
        """
        Return token-level spans for a line, marking which words contain primary stresses.
        Each span includes:
        - start: character index in original line
        - end: character index (exclusive)
        - text: the substring from original line
        - is_word: True if this token matches a word (vs punctuation/space)
        - has_primary_stress: True if the word contains a primary stress vowel
        
        Note: Function words at line end CAN carry stress (natural speech emphasis).
        """
        import re
        spans: List[Dict[str, Any]] = []
        normalized = normalize_lyric_line(line)
        words = tokenize_words(normalized)
        last_word = words[-1] if words else None
        
        # Build a map from lowercase word to whether it has primary stress
        word_to_has_stress: Dict[str, bool] = {}
        for w in words:
            is_line_end = (w == last_word)
            
            # Function words don't carry stress UNLESS at line end
            if w in _FUNCTION_WORDS and not is_line_end:
                word_to_has_stress[w] = False
                continue
            
            phonemes = self.get_phonemes(w)
            if not phonemes:
                phonemes = self._estimate_phonemes_for_unknown(w)
            
            if phonemes:
                syllable_count = sum(1 for p in phonemes if p.is_vowel)
                if syllable_count >= 3:
                    has_stress = any(p.is_vowel and p.stress_level in {1, 2} for p in phonemes)
                else:
                    has_stress = any(p.is_vowel and p.stress_level == 1 for p in phonemes)
                word_to_has_stress[w] = has_stress
            else:
                # Fallback: content words get stress, function words at line end get stress
                word_to_has_stress[w] = (w not in _FUNCTION_WORDS) or is_line_end
        
        # Tokenize preserving original punctuation/casing
        word_re = r"[A-Za-z]+(?:['’‘‛ʼ＇][A-Za-z]+)?"
        token_re = re.compile(word_re + r"|\S")
        for m in token_re.finditer(line):
            token_text = m.group()
            is_word = bool(re.fullmatch(word_re, token_text))
            token_key = normalize_lyric_line(token_text).lower() if is_word else ""
            has_stress = is_word and word_to_has_stress.get(token_key, False)
            spans.append({
                "start": m.start(),
                "end": m.end(),
                "text": token_text,
                "is_word": is_word,
                "has_primary_stress": has_stress,
            })
        return spans
