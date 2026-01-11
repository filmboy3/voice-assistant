"""
Section-based rhyme scheme analyzer using Pat Pattison's building blocks.

This module analyzes lyrics by stanzas/sections, generating rhyme schemes
that use Pat Pattison's canonical patterns (ABAB, XAXA, AABB, etc.) rather
than one continuous unintelligible string.
"""

from typing import List, Dict, Any, Tuple, Optional, Union
from dataclasses import dataclass
from pattison.core.phonetic_engine import PhoneticEngine
from pattison.core.rhyme_classifier import RhymeClassifier
from pattison.structure.analyzer import (
    detect_rhyme_scheme,
    split_into_stanzas,
    match_pattern,
    estimate_stability,
    _ending_word,
    _structural_scheme,
    _analyze_juncture,
    LineResult
)
from pattison.core.tokenize import normalize_lyric_line

@dataclass
class StanzaAnalysis:
    """Analysis of a single stanza/section."""
    stanza_number: int
    lines: List[str]
    line_count: int
    raw_rhyme_scheme: str
    structural_scheme: str
    pattern_name: Optional[str]
    pattern_confidence: float
    stability: float
    stress_counts: List[int]
    end_words: List[str]
    rhyme_pairs: List[Dict[str, Any]]
    likely_section_type: Optional[str]  # verse, chorus, bridge, etc.

@dataclass
class SectionDetection:
    """Detected section type based on repetition and structure."""
    section_type: str  # verse, chorus, bridge, pre-chorus, outro, etc.
    confidence: float
    reasoning: str

def detect_section_type(
    stanza: StanzaAnalysis,
    all_stanzas: List[StanzaAnalysis],
    stanza_index: int
) -> SectionDetection:
    """
    Detect likely section type (verse/chorus/bridge) based on:
    1. Repetition of rhyme scheme across stanzas
    2. Repetition of actual lines (chorus indicator)
    3. Position in song structure
    4. Rhyme scheme pattern stability
    """
    
    # Check for repeated lines (strong chorus indicator)
    repeated_count = 0
    for other_idx, other_stanza in enumerate(all_stanzas):
        if other_idx == stanza_index:
            continue
        
        # Count matching lines
        matching_lines = sum(
            1 for line in stanza.lines
            if line in other_stanza.lines
        )
        
        if matching_lines >= len(stanza.lines) * 0.7:  # 70% match
            repeated_count += 1
    
    # Strong repetition = likely chorus
    if repeated_count >= 2:
        return SectionDetection(
            section_type="chorus",
            confidence=0.9,
            reasoning=f"Lines repeated in {repeated_count} other stanzas"
        )
    
    # Check rhyme scheme repetition
    scheme_matches = sum(
        1 for other in all_stanzas
        if other.structural_scheme == stanza.structural_scheme
        and other.stanza_number != stanza.stanza_number
    )
    
    # Repeated scheme with high stability = likely chorus
    if scheme_matches >= 2 and stanza.stability > 0.8:
        return SectionDetection(
            section_type="chorus",
            confidence=0.75,
            reasoning=f"Stable rhyme scheme ({stanza.structural_scheme}) repeated {scheme_matches} times"
        )
    
    # Unique or less stable scheme = likely verse
    if scheme_matches == 0 or stanza.stability < 0.7:
        return SectionDetection(
            section_type="verse",
            confidence=0.7,
            reasoning=f"Unique or unstable rhyme scheme ({stanza.structural_scheme})"
        )
    
    # Check position - first/last stanzas
    if stanza_index == 0:
        return SectionDetection(
            section_type="verse",
            confidence=0.6,
            reasoning="First stanza, typically verse"
        )
    
    if stanza_index == len(all_stanzas) - 1:
        return SectionDetection(
            section_type="outro",
            confidence=0.5,
            reasoning="Final stanza"
        )
    
    # Check for bridge indicators (different pattern, appears once)
    if scheme_matches == 0 and stanza_index > len(all_stanzas) // 2:
        return SectionDetection(
            section_type="bridge",
            confidence=0.6,
            reasoning="Unique pattern in latter half of song"
        )
    
    # Default to verse
    return SectionDetection(
        section_type="verse",
        confidence=0.5,
        reasoning="Default classification"
    )

def analyze_stanza(
    lines: List[str],
    stanza_number: int,
    *,
    classifier: RhymeClassifier,
    engine: PhoneticEngine,
    include_consonance: bool = False
) -> StanzaAnalysis:
    """
    Analyze a single stanza using Pat Pattison's building blocks.
    
    Returns rhyme scheme limited to the stanza (not continuous across song).
    """
    
    # Normalize and analyze lines
    cleaned = [l.strip() for l in lines if l.strip()]
    normalized_cleaned = [normalize_lyric_line(l) for l in cleaned]
    line_results: List[LineResult] = []
    
    for l, normalized in zip(cleaned, normalized_cleaned):
        end = _ending_word(normalized)
        stresses = engine.count_line_primary_stresses(normalized)
        line_results.append(LineResult(text=l, end_word=end, primary_stress_count=stresses))
    
    endings = [lr.end_word for lr in line_results]
    lengths = [lr.primary_stress_count for lr in line_results]
    
    # Detect rhyme scheme for THIS stanza only
    raw_scheme, pairs = detect_rhyme_scheme(
        endings,
        classifier=classifier,
        include_consonance=include_consonance
    )
    
    scheme = _structural_scheme(list(raw_scheme))
    pattern, confidence = match_pattern(
        raw_scheme=raw_scheme,
        structural_scheme=scheme,
        lengths=lengths
    )
    
    stability = pattern.stability if pattern else estimate_stability(
        scheme=scheme,
        lengths=lengths
    )
    
    # Format rhyme pairs
    rhyme_pairs_out: List[Dict[str, Any]] = []
    for (i, j), payload in sorted(pairs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        entry = {"line1": int(i) + 1, "line2": int(j) + 1}
        entry.update(payload)
        rhyme_pairs_out.append(entry)
    
    return StanzaAnalysis(
        stanza_number=stanza_number,
        lines=cleaned,
        line_count=len(cleaned),
        raw_rhyme_scheme=raw_scheme,
        structural_scheme=scheme,
        pattern_name=pattern.name if pattern else None,
        pattern_confidence=confidence,
        stability=stability,
        stress_counts=lengths,
        end_words=endings,
        rhyme_pairs=rhyme_pairs_out,
        likely_section_type=None  # Will be filled in after all stanzas analyzed
    )

def analyze_song_by_sections(
    lines: Union[str, List[str]],
    *,
    cmu_path: Optional[str] = None,
    jonathan_db_path: Optional[str] = None,
    include_consonance_in_scheme: bool = False,
) -> Dict[str, Any]:
    """
    Analyze a song by sections/stanzas using Pat Pattison's building blocks.
    
    Returns:
    - List of stanza analyses (each with its own rhyme scheme)
    - Section type detection (verse/chorus/bridge)
    - Overall song structure summary
    """
    
    engine = PhoneticEngine(cmu_path=cmu_path, jonathan_db_path=jonathan_db_path)
    classifier = RhymeClassifier(engine)
    
    # Split into stanzas
    # NOTE: callers often pass full lyrics as a single string. If we iterate a string,
    # we'll accidentally treat each character as a "line" (catastrophic output).
    if isinstance(lines, str):
        source_lines: List[str] = lines.splitlines()
    else:
        source_lines = list(lines or [])

    raw_input_lines = [l.rstrip() for l in source_lines if isinstance(l, str)]
    stanzas = split_into_stanzas(raw_input_lines)
    
    # Analyze each stanza separately
    stanza_analyses: List[StanzaAnalysis] = []
    
    for i, stanza_lines in enumerate(stanzas, 1):
        analysis = analyze_stanza(
            stanza_lines,
            stanza_number=i,
            classifier=classifier,
            engine=engine,
            include_consonance=include_consonance_in_scheme
        )
        stanza_analyses.append(analysis)
    
    # Detect section types based on repetition and structure
    for i, stanza in enumerate(stanza_analyses):
        detection = detect_section_type(stanza, stanza_analyses, i)
        stanza.likely_section_type = detection.section_type
    
    # Generate overall song structure summary
    structure_summary = []
    for stanza in stanza_analyses:
        structure_summary.append({
            'stanza_number': stanza.stanza_number,
            'section_type': stanza.likely_section_type,
            'rhyme_scheme': stanza.structural_scheme,
            'pattern': stanza.pattern_name,
            'line_count': stanza.line_count,
            'stability': stanza.stability
        })
    
    # Juncture analysis on full song
    all_normalized = []
    for stanza_lines in stanzas:
        for line in stanza_lines:
            if line.strip():
                all_normalized.append(normalize_lyric_line(line.strip()))
    
    juncture = _analyze_juncture(all_normalized, engine=engine)
    
    return {
        "success": True,
        "stanzas": [
            {
                "stanza_number": s.stanza_number,
                "lines": s.lines,
                "line_count": s.line_count,
                "rhyme_scheme": s.structural_scheme,
                "raw_rhyme_scheme": s.raw_rhyme_scheme,
                "pattern": s.pattern_name,
                "pattern_confidence": s.pattern_confidence,
                "stability": s.stability,
                "stress_counts": s.stress_counts,
                "end_words": s.end_words,
                "rhyme_pairs": s.rhyme_pairs,
                "section_type": s.likely_section_type
            }
            for s in stanza_analyses
        ],
        "structure_summary": structure_summary,
        "juncture": juncture,
        "total_stanzas": len(stanza_analyses),
        "total_lines": sum(s.line_count for s in stanza_analyses)
    }
