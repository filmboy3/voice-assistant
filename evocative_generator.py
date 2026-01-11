"""
Evocative Generator - Uses the same Quick Hits vocabulary as quick_helper

Generates creative content on-the-fly using proven songwriting patterns.
Pulls from the comprehensive Quick Hits database with 1300+ curated items.
"""

import json
import random
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

APP_ROOT = Path(__file__).parent
QUICK_HITS_SOURCE_PATH = APP_ROOT / "LLM_Latest_Quick_Hits_Page"

_quick_hits_cache = None


def load_quick_hits() -> Dict:
    """Load the Quick Hits database (same source as quick_helper)."""
    global _quick_hits_cache
    if _quick_hits_cache is not None:
        return _quick_hits_cache
    
    if not QUICK_HITS_SOURCE_PATH.exists():
        _quick_hits_cache = {}
        return _quick_hits_cache
    
    text = QUICK_HITS_SOURCE_PATH.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"```json\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if not m:
        _quick_hits_cache = {}
        return _quick_hits_cache
    
    try:
        _quick_hits_cache = json.loads(m.group(1))
    except json.JSONDecodeError:
        _quick_hits_cache = {}
    
    return _quick_hits_cache


def extract_all_items(obj: Any, items: List[str] = None) -> List[str]:
    """Recursively extract all string items from the Quick Hits structure."""
    if items is None:
        items = []
    
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, str):
                items.append(item)
            elif isinstance(item, dict) and "text" in item:
                items.append(item["text"])
            else:
                extract_all_items(item, items)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("metadata", "description"):
                continue
            if key == "items" and isinstance(value, list):
                extract_all_items(value, items)
            else:
                extract_all_items(value, items)
    
    return items


def get_items_by_category(category: str) -> List[str]:
    """Get all items from a specific category."""
    db = load_quick_hits()
    if category not in db:
        return []
    return extract_all_items(db[category])


def get_items_by_path(path: List[str]) -> List[str]:
    """Get items by navigating a path like ['concrete_imagery', 'drinks', 'alcohol_spirits']."""
    db = load_quick_hits()
    current = db
    
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return []
    
    return extract_all_items(current)


KNOWN_PROPER_NOUNS = {
    "patagonia", "lexapro", "zoloft", "bushwick", "marfa", "joshua tree",
    "silver lake", "corvette", "mustang", "substack", "hinge", "raya",
    "peloton", "lululemon", "trader joe's", "whole foods", "erewhon",
    "sweetgreen", "brooklyn", "williamsburg", "greenpoint", "dumbo",
    "west village", "soho", "the les", "the hamptons", "montauk",
    "hudson valley", "catskills", "echo park", "los feliz", "venice beach",
    "abbot kinney", "west hollywood", "santa monica", "malibu", "palm springs",
    "napa", "sonoma", "big sur", "cadillac", "thunderbird", "continental",
    "silverado", "chevy", "ford", "jeep", "bronco", "rover", "defender",
    "harley", "nashville", "new york", "nyc", "la", "los angeles", "hollywood",
    "miami", "vegas", "las vegas", "chicago", "detroit", "atlanta",
    "new orleans", "austin", "dallas", "houston", "memphis", "seattle",
    "london", "paris", "tokyo", "rome", "berlin", "toronto",
    "california", "cali", "texas", "tennessee", "georgia", "florida",
    "carolina", "alabama", "mississippi", "louisiana", "kentucky", "virginia",
    "colorado", "nevada", "arizona", "montana", "ohio", "illinois", "michigan",
    "hawaii", "alaska", "budweiser", "miller", "coors", "corona", "heineken",
    "guinness", "pbr", "cabernet", "merlot", "pinot", "chardonnay", "prosecco",
    "dom perignon", "jack", "jim beam", "hennessy", "patron", "casamigos",
    "bacardi", "grey goose", "rolex", "ray-bans", "converse", "vans",
    "coca-cola", "coke", "diet coke", "pepsi", "npr", "pbs", "wordle",
    "oura ring", "apple watch", "airpods", "kindle"
}


def has_proper_noun(text: str) -> bool:
    """Check if text contains a proper noun."""
    text_lower = text.lower()
    
    for noun in KNOWN_PROPER_NOUNS:
        if noun in text_lower:
            return True
    
    words = text.split()
    if len(words) <= 1:
        return False
    for word in words[1:]:
        if word and word[0].isupper() and word.lower() not in {"i", "i'm", "i'll", "i've", "i'd"}:
            return True
    return False


def filter_proper_nouns(items: List[str], exclude_proper_nouns: bool) -> List[str]:
    """Filter out items with proper nouns if requested."""
    if not exclude_proper_nouns:
        return items
    return [item for item in items if not has_proper_noun(item)]


def capitalize_first(text: str) -> str:
    """Capitalize the first letter of the text."""
    if not text:
        return text
    return text[0].upper() + text[1:]


MOOD_ADJECTIVES = [
    # Core emotions
    "melancholic", "euphoric", "restless", "hollow", "radiant",
    "bitter", "tender", "anxious", "wistful", "reckless",
    "lonely", "hopeful", "desperate", "numb", "electric",
    "aching", "burning", "yearning", "longing", "craving",
    "haunted", "hunted", "wanted", "needed", "forgotten",
    "abandoned", "stranded", "lost", "found", "searching",
    # States of being
    "waiting", "watching", "wondering", "wandering", "drifting",
    "floating", "falling", "rising", "sinking", "spinning",
    "trembling", "shaking", "breaking", "bending", "folding",
    "unraveling", "dissolving", "fading", "glowing", "pulsing",
    # Intensity
    "fierce", "gentle", "wild", "calm", "stormy",
    "peaceful", "chaotic", "serene", "turbulent", "still",
    "quiet", "loud", "silent", "raw", "polished",
    # Weight and depth
    "heavy", "light", "deep", "shallow", "wide",
    "narrow", "open", "closed", "free", "trapped",
    # Character
    "brave", "afraid", "bold", "timid", "proud",
    "humble", "grateful", "patient", "certain", "uncertain",
    "trusting", "suspicious", "innocent", "guilty", "clean",
    # Texture
    "rough", "smooth", "sharp", "dull", "bright",
    "dim", "dark", "pure", "whole", "broken",
    # Temperature
    "freezing", "melting", "hardening", "softening", "healing",
    "hurting", "throbbing", "racing", "slowing", "stopping",
    # Additional evocative moods
    "sacred", "profane", "holy", "blessed", "cursed",
    "lucky", "unlucky", "fated", "doomed", "saved",
    "redeemed", "forsaken", "chosen", "damned", "forgiven",
    "vengeful", "forgiving", "resentful", "content", "restless",
    # Sensory-emotional
    "intoxicated", "sober", "dizzy", "grounded", "untethered",
    "anchored", "adrift", "rooted", "uprooted", "scattered",
    "gathered", "splintered", "unified", "fractured", "mended",
    # Time-based
    "ancient", "young", "aging", "timeless", "fleeting",
    "eternal", "momentary", "lasting", "fading", "emerging",
    # Relational
    "connected", "disconnected", "bonded", "severed", "tangled",
    "untangled", "knotted", "loosened", "tightened", "released"
]


def get_moods() -> List[str]:
    """Get mood/emotion adjectives - curated list for quality."""
    return MOOD_ADJECTIVES.copy()


def get_sensory_adjectives() -> List[str]:
    """Get sensory/descriptive adjectives."""
    db = load_quick_hits()
    adjectives = []
    
    if "object_characteristics" in db:
        adjectives.extend(extract_all_items(db["object_characteristics"]))
    
    fallback_adjectives = [
        "scorching", "flickering", "trembling", "rusted", "faded",
        "cracked", "dusty", "worn", "cold", "warm", "heavy", "light",
        "sharp", "soft", "bitter", "sweet", "hollow", "solid",
        "rough", "smooth", "wet", "dry", "sticky", "slippery",
        "gritty", "silky", "velvety", "coarse", "fine", "thick",
        "thin", "dense", "sparse", "tight", "loose", "taut",
        "crisp", "soggy", "stale", "fresh", "rotten", "ripe",
        "raw", "burnt", "frozen", "melted", "hardened", "softened",
        "crushed", "whole", "broken", "shattered", "splintered",
        "twisted", "bent", "straight", "curved", "flat", "round",
        "jagged", "bumpy", "sleek", "matte", "glossy", "shiny",
        "dull", "bright", "dim", "glowing", "fading", "pulsing",
        "buzzing", "humming", "ringing", "silent", "muffled", "clear"
    ]
    
    if not adjectives:
        adjectives = fallback_adjectives
    else:
        adjectives = list(set(adjectives + fallback_adjectives))
    
    return adjectives


def get_concrete_objects() -> List[str]:
    """Get concrete objects from the database."""
    db = load_quick_hits()
    objects = []
    
    for category in ["concrete_imagery", "objects", "domestic_objects", "objects_ephemera"]:
        if category in db:
            objects.extend(extract_all_items(db[category]))
    
    return list(set(objects)) if objects else ["something"]


def get_places() -> List[str]:
    """Get place names from the database."""
    db = load_quick_hits()
    places = []
    
    for category in ["places", "spaces", "places_spaces"]:
        if category in db:
            places.extend(extract_all_items(db[category]))
    
    if "concrete_imagery" in db:
        ci = db["concrete_imagery"]
        if isinstance(ci, dict):
            for key in ["roads_paths", "coastal_millennial"]:
                if key in ci:
                    places.extend(extract_all_items(ci[key]))
    
    return list(set(places)) if places else ["somewhere"]


def get_time_weather() -> List[str]:
    """Get time and weather references."""
    db = load_quick_hits()
    items = []
    
    for category in ["time", "weather"]:
        if category in db:
            items.extend(extract_all_items(db[category]))
    
    return list(set(items)) if items else ["midnight"]


def get_verbs() -> List[str]:
    """Get action verbs from the database."""
    db = load_quick_hits()
    verbs = []
    
    if "verbs" in db:
        verbs.extend(extract_all_items(db["verbs"]))
    
    return list(set(verbs)) if verbs else ["moving"]


def get_body_gestures() -> List[str]:
    """Get body language and gesture phrases."""
    db = load_quick_hits()
    gestures = []
    
    if "concrete_imagery" in db:
        ci = db["concrete_imagery"]
        if isinstance(ci, dict) and "body_sensory" in ci:
            gestures.extend(extract_all_items(ci["body_sensory"]))
    
    fallback = [
        "trembling hands", "clenched jaw", "heavy shoulders",
        "racing heart", "held breath", "closed eyes", "open palms",
        "turned back", "locked gaze", "bitten lip", "furrowed brow",
        "crossed arms", "tapping foot", "drumming fingers"
    ]
    
    return list(set(gestures + fallback)) if gestures else fallback


def generate_expanded_title(starter_word: str = "", exclude_proper_nouns: bool = False) -> str:
    """Generate an expanded title (hit song pattern)."""
    moods = filter_proper_nouns(get_moods(), exclude_proper_nouns)
    objects = filter_proper_nouns(get_concrete_objects(), exclude_proper_nouns)
    places = filter_proper_nouns(get_places(), exclude_proper_nouns)
    times = filter_proper_nouns(get_time_weather(), exclude_proper_nouns)
    verbs = filter_proper_nouns(get_verbs(), exclude_proper_nouns)
    
    # If anchor word provided, use it as the main object/subject
    anchor = starter_word if starter_word else None
    
    if anchor:
        # Patterns that incorporate the anchor word
        patterns = [
            lambda: f"{anchor} in {random.choice(places)}",
            lambda: f"{random.choice(moods)} {anchor}",
            lambda: f"{anchor} and {random.choice(moods)}",
            lambda: f"{anchor} at {random.choice(times)}",
            lambda: f"{random.choice(times)} {anchor}",
            lambda: f"{anchor} {random.choice(verbs) if verbs else 'waiting'}",
            lambda: f"the {anchor} of {random.choice(places)}",
            lambda: f"{random.choice(moods)} {anchor}",
            lambda: f"{anchor} on {random.choice(places)}",
            lambda: f"{random.choice(objects)} and {anchor}",
        ]
    else:
        # No anchor - use random objects
        patterns = [
            lambda: f"{random.choice(objects)} in {random.choice(places)}",
            lambda: f"{random.choice(moods)} {random.choice(objects)}",
            lambda: f"{random.choice(objects)} and {random.choice(moods)}",
            lambda: f"{random.choice(places)} at {random.choice(times)}",
            lambda: f"{random.choice(moods)} {random.choice(times)}",
            lambda: f"{random.choice(objects)} {random.choice(verbs) if verbs else 'waiting'}",
            lambda: f"the {random.choice(objects)} of {random.choice(places)}",
            lambda: f"{random.choice(times)} {random.choice(objects)}",
            lambda: f"{random.choice(moods)} in {random.choice(places)}",
            lambda: f"{random.choice(objects)} on {random.choice(places)}",
        ]
    
    result = random.choice(patterns)()
    return capitalize_first(result)


def generate_object_characteristic(starter_word: str = "", exclude_proper_nouns: bool = False) -> str:
    """Generate an object characteristic (sensory + concrete)."""
    adjectives = filter_proper_nouns(get_sensory_adjectives(), exclude_proper_nouns)
    objects = filter_proper_nouns(get_concrete_objects(), exclude_proper_nouns)
    
    adj = random.choice(adjectives) if adjectives else "worn"
    obj = starter_word if starter_word else (random.choice(objects) if objects else "thing")
    
    return capitalize_first(f"{adj} {obj}")


def generate_emotional_landscape(starter_word: str = "", exclude_proper_nouns: bool = False) -> str:
    """Generate an emotional landscape (mood + setting)."""
    moods = filter_proper_nouns(get_moods(), exclude_proper_nouns)
    places = filter_proper_nouns(get_places(), exclude_proper_nouns)
    objects = filter_proper_nouns(get_concrete_objects(), exclude_proper_nouns)
    
    mood = random.choice(moods) if moods else "quiet"
    
    patterns = [
        lambda: f"{mood} {random.choice(places) if places else 'somewhere'}",
        lambda: f"{mood} {random.choice(objects) if objects else 'something'}",
        lambda: f"{mood} like {random.choice(objects) if objects else 'something'}",
    ]
    
    place_or_obj = starter_word if starter_word else None
    if place_or_obj:
        result = f"{mood} {place_or_obj}"
    else:
        result = random.choice(patterns)()
    
    return capitalize_first(result)


def generate_metaphorical_bridge(starter_word: str = "", exclude_proper_nouns: bool = False) -> str:
    """Generate a metaphorical bridge (X is/becomes Y)."""
    all_items = filter_proper_nouns(
        get_concrete_objects() + get_moods()[:30] + get_places()[:30],
        exclude_proper_nouns
    )
    
    if len(all_items) < 2:
        all_items = ["love", "time", "hope", "fear", "joy", "pain", "light", "dark"]
    
    connectors = ["is", "becomes", "turns into"]
    
    item1 = starter_word if starter_word else random.choice(all_items)
    item2 = random.choice([i for i in all_items if i.lower() != item1.lower()])
    connector = random.choice(connectors)
    
    return capitalize_first(f"{item1} {connector} {item2}")


def generate(
    starter_word: str = "",
    count: int = 5,
    all_exercises: bool = True,
    exclude_proper_nouns: bool = False,
    **kwargs  # Accept but ignore legacy params like 'exercise'
) -> List[Dict[str, Any]]:
    """
    Generate creative content across all 4 exercise types.
    
    Args:
        starter_word: Optional anchor word to incorporate into generations
        count: Number of items to generate per exercise (default 5, total 20)
        all_exercises: Always True - generates for all 4 types
        exclude_proper_nouns: If True, filter out results with proper nouns (except the anchor word)
    
    Returns:
        List of generated items with metadata (5 per exercise = 20 total)
    """
    generators = {
        "expanded_titles": generate_expanded_title,
        "object_characteristics": generate_object_characteristic,
        "emotional_landscapes": generate_emotional_landscape,
        "metaphorical_bridges": generate_metaphorical_bridge
    }
    
    # Always generate for all exercises
    all_results = []
    for ex_name, generator in generators.items():
        ex_results = _generate_for_exercise(
            generator, ex_name, starter_word, count, 
            filter_by_word=False,  # Don't filter - just incorporate starter word
            exclude_proper_nouns=exclude_proper_nouns,
            allowed_proper_noun=starter_word  # Allow the anchor word even if it's a proper noun
        )
        all_results.extend(ex_results)
    return all_results


def _generate_for_exercise(
    generator,
    exercise_name: str,
    starter_word: str,
    count: int,
    filter_by_word: bool = False,
    exclude_proper_nouns: bool = False,
    allowed_proper_noun: str = ""
) -> List[Dict[str, Any]]:
    """Generate results for a single exercise."""
    results = []
    seen = set()
    attempts = 0
    max_attempts = count * 30
    
    while len(results) < count and attempts < max_attempts:
        attempts += 1
        text = generator(starter_word, exclude_proper_nouns)
        
        if not text or text.lower() in seen:
            continue
        
        if filter_by_word and starter_word:
            if starter_word.lower() not in text.lower():
                continue
        
        # Check for proper nouns, but allow the anchor word itself
        if exclude_proper_nouns:
            if has_proper_noun_except(text, allowed_proper_noun):
                continue
        
        seen.add(text.lower())
        results.append({
            "text": text,
            "exercise": exercise_name
        })
    
    return results


def has_proper_noun_except(text: str, allowed_word: str = "") -> bool:
    """Check if text contains a proper noun, excluding the allowed word."""
    if not allowed_word:
        return has_proper_noun(text)
    
    # Remove the allowed word from the text before checking
    text_without_allowed = text.lower().replace(allowed_word.lower(), "")
    
    # Check remaining text for proper nouns from our known list
    for noun in KNOWN_PROPER_NOUNS:
        if noun != allowed_word.lower() and noun in text_without_allowed:
            return True
    
    # Check for capitalized words (excluding the allowed word)
    words = text.split()
    if len(words) <= 1:
        return False
    for word in words[1:]:
        if word and word[0].isupper():
            # Skip if this word is the allowed word
            if word.lower() == allowed_word.lower():
                continue
            if word.lower() not in {"i", "i'm", "i'll", "i've", "i'd"}:
                return True
    return False


def get_available_exercises() -> List[Dict[str, str]]:
    """Get list of available exercises with descriptions."""
    return [
        {
            "id": "expanded_titles",
            "name": "Expanded Titles",
            "description": "Hit song title patterns",
            "example": "Soft launch in Brooklyn"
        },
        {
            "id": "object_characteristics",
            "name": "Object Characteristics",
            "description": "Sensory + concrete objects",
            "example": "Scorching motorcycle"
        },
        {
            "id": "emotional_landscapes",
            "name": "Emotional Landscapes",
            "description": "Mood + evocative setting",
            "example": "Melancholic slow burn"
        },
        {
            "id": "metaphorical_bridges",
            "name": "Metaphorical Bridges",
            "description": "X is Y connections",
            "example": "Lucky is gravy"
        }
    ]


def get_database_stats() -> Dict[str, Any]:
    """Get statistics about the loaded database."""
    db = load_quick_hits()
    
    stats = {
        "categories": list(db.keys()) if db else [],
        "total_items": len(extract_all_items(db)),
        "moods_count": len(get_moods()),
        "objects_count": len(get_concrete_objects()),
        "places_count": len(get_places()),
        "adjectives_count": len(get_sensory_adjectives()),
    }
    
    return stats
