EXERCISES = {
    "ch4_rhyme_classify": {
        "chapter": 4,
        "title": "Rhyme classification",
        "inputs": ["word1", "word2"],
        "presets": [
            {
                "label": "Perfect rhyme: fun / sun",
                "inputs": {"word1": "fun", "word2": "sun"},
            },
            {
                "label": "Family rhyme (example): strum / drum",
                "inputs": {"word1": "strum", "word2": "drum"},
            },
            {
                "label": "Assonance (example): love / buzz",
                "inputs": {"word1": "love", "word2": "buzz"},
            },
        ],
        "writeup": (
            "Classify the rhyme relationship between two words using Pat Pattison's rhyme stability ladder. "
            "This is a technical drill: you supply two words and the engine returns the Pattison rhyme type "
            "(perfect, family, additive, subtractive, assonance, consonance) plus a short explanation of why.\n\n"
            "Use this when you're deciding whether a pair of line-ending words supports the emotional intent of the section "
            "(stable rhymes feel more resolved; unstable rhymes feel more restless)."
        ),
        "input_hints": {
            "word1": "First word to compare (single word; casing doesn't matter).",
            "word2": "Second word to compare (single word; casing doesn't matter).",
        },
        "input_placeholders": {
            "word1": "e.g. fun",
            "word2": "e.g. sun",
        },
    },
    "ch14_stress_count": {
        "chapter": 14,
        "title": "Stress counting (primary stresses)",
        "inputs": ["line"],
        "presets": [
            {
                "label": "Mary had a little lamb",
                "inputs": {"line": "Mary had a little lamb"},
            },
            {
                "label": "Its fleece was white as snow",
                "inputs": {"line": "Its fleece was white as snow"},
            },
            {
                "label": "I hitched to Tulsa worn and soaked",
                "inputs": {"line": "I hitched to Tulsa worn and soaked"},
            },
        ],
        "writeup": (
            "Count the number of primary stresses in a single lyric line using the phonetic engine. "
            "This is a practical meter drill: you can quickly compare line-to-line stress counts while revising.\n\n"
            "Note: this is not 'syllable count' — it is a rough stress count based on pronunciations in the CMU dictionary "
            "(plus any custom entries you have in the Jonathan rhyme DB)."
        ),
        "input_hints": {
            "line": "One lyric line. The result is the number of primary stresses detected.",
        },
        "input_placeholders": {
            "line": "e.g. Mary had a little lamb",
        },
    },
    "ch14_common_meter_check": {
        "chapter": 14,
        "title": "Common meter check (4-3-4-3)",
        "inputs": ["lines"],
        "presets": [
            {
                "label": "Mary had a little lamb (common meter)",
                "inputs": {
                    "lines": "Mary had a little lamb\nIts fleece was white as snow\nAnd everywhere that Mary went\nThe lamb was sure to go",
                },
            },
        ],
        "writeup": (
            "Check whether four lines fit common meter (a 4-3-4-3 stress pattern). "
            "This drill helps you build verses that are easy to set melodically and that naturally support repetition/variation.\n\n"
            "Enter exactly 4 non-empty lines. The engine counts primary stresses per line and verifies the 4-3-4-3 relationship."
        ),
        "input_hints": {
            "lines": "Exactly 4 non-empty lines (one per row).",
        },
        "input_placeholders": {
            "lines": "Mary had a little lamb\nIts fleece was white as snow\nAnd everywhere that Mary went\nThe lamb was sure to go",
        },
    },
    "ch19_pattern_drill": {
        "chapter": 19,
        "title": "Pattern drill (detect scheme + pattern)",
        "inputs": ["lines"],
        "presets": [
            {
                "label": "Tulsa (PatBook canon)",
                "inputs": {
                    "lines": "I hitched to Tulsa worn and soaked\nI stopped to get a bite\nThe waitress stared before she spoke\nThen asked me what I'd like",
                },
            },
        ],
        "writeup": (
            "Analyze a short set of lines as a 'mini section' and return the detected rhyme scheme and pattern. "
            "This is a diagnostic drill: paste in a verse/chorus fragment and the engine will identify rhyme relationships "
            "and structural motion cues (including juncture).\n\n"
            "Use this while revising to see if your intended pattern is actually happening on the page."
        ),
        "input_hints": {
            "lines": "A list of lines (one per row). More lines gives a clearer pattern signal.",
        },
        "input_placeholders": {
            "lines": "I hitched to Tulsa worn and soaked\nI stopped to get a bite\nThe waitress stared before she spoke\nThen asked me what I'd like",
        },
    },
    "ch19_comprehensive_section_readout": {
        "chapter": 19,
        "title": "Comprehensive section readout (PatBook-style table)",
        "inputs": ["lines", "include_consonance_in_scheme"],
        "presets": [
            {
                "label": "Tulsa (PatBook canon) — strict scheme",
                "inputs": {
                    "lines": "I hitched to Tulsa worn and soaked\nI stopped to get a bite\nThe waitress stared before she spoke\nThen asked me what I'd like",
                    "include_consonance_in_scheme": "false",
                },
            },
            {
                "label": "Tulsa (PatBook canon) — allow consonance in scheme",
                "inputs": {
                    "lines": "I hitched to Tulsa worn and soaked\nI stopped to get a bite\nThe waitress stared before she spoke\nThen asked me what I'd like",
                    "include_consonance_in_scheme": "true",
                },
            },
        ],
        "writeup": (
            "Analyze a set of lyric lines and return a Pat Pattison-style section readout: rhyme scheme(s), "
            "stress counts per line, end-word phonetic breakdown, and rhyme-type classifications between line-ending words. "
            "This is meant to function like the book’s “Rhyme | Stresses” tables and is designed as a foundation for future generation + judging workflows."
        ),
        "input_hints": {
            "lines": "A list of lines (one per row). Use at least 2 lines for rhyme analysis.",
            "include_consonance_in_scheme": "Optional. If true, consonance is allowed to count as a rhyme when building the scheme. Accepts true/false.",
        },
        "input_placeholders": {
            "lines": "I hitched to Tulsa worn and soaked\nI stopped to get a bite\nThe waitress stared before she spoke\nThen asked me what I'd like",
            "include_consonance_in_scheme": "false",
        },
    },
    "ch19_section_constraints_validator": {
        "chapter": 19,
        "title": "Section constraints validator (scheme + stresses)",
        "inputs": [
            "lines",
            "target_scheme",
            "target_stresses",
            "scheme_mode",
            "include_consonance_in_scheme",
        ],
        "presets": [
            {
                "label": "Tulsa (PatBook canon) — target ABAB",
                "inputs": {
                    "lines": "I hitched to Tulsa worn and soaked\nI stopped to get a bite\nThe waitress stared before she spoke\nThen asked me what I'd like",
                    "target_scheme": "ABAB",
                    "target_stresses": "",
                    "scheme_mode": "default",
                    "include_consonance_in_scheme": "false",
                },
            },
            {
                "label": "Mary (common meter-ish) — target XAXA + 4-3-4-3",
                "inputs": {
                    "lines": "Mary had a little lamb\nIts fleece was white as snow\nAnd everywhere that Mary went\nThe lamb was sure to go",
                    "target_scheme": "XAXA",
                    "target_stresses": "4-3-4-3",
                    "scheme_mode": "perfect_or_family",
                    "include_consonance_in_scheme": "false",
                },
            },
        ],
        "writeup": (
            "Validate a draft section against explicit constraints: an intended rhyme scheme (like ABAB or XAXA) "
            "and/or an intended stress pattern (like 4-3-4-3). The engine returns pass/fail plus per-line diagnostics.\n\n"
            "Use this to turn many PatBook structure prompts into a repeatable drill: write your lines, then validate whether "
            "the structure you intended is actually happening on the page."
        ),
        "input_hints": {
            "lines": "A list of lines (one per row).",
            "target_scheme": "Optional. Structural target scheme (same length as lines). Use X for unrhymed lines (e.g. XAXA).",
            "target_stresses": "Optional. Hyphen-separated target stress counts per line (e.g. 4-3-4-3).",
            "scheme_mode": "Optional. One of: default, perfect_only, perfect_or_family.",
            "include_consonance_in_scheme": "Optional. Only affects scheme_mode=default. Accepts true/false.",
        },
        "input_placeholders": {
            "lines": "I hitched to Tulsa worn and soaked\nI stopped to get a bite\nThe waitress stared before she spoke\nThen asked me what I'd like",
            "target_scheme": "ABAB",
            "target_stresses": "4-3-4-3",
            "scheme_mode": "default",
            "include_consonance_in_scheme": "false",
        },
    },
}
