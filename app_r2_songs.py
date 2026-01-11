#!/usr/bin/env python3
"""
R2 Songs Database API

Fetches songs from R2 master database at:
https://pub-53b5eb7528ba49eaaf533b48541508ae.r2.dev/songs/

No batch numbers - single master database with sharded storage.
"""

from flask import Blueprint, jsonify, request
import json
import gzip
import requests
from functools import lru_cache
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

bp = Blueprint('r2_songs', __name__)

_SONGS_INDEX_CACHE = None
_SONGS_INDEX_CACHE_TS = 0

# R2 base URL for songs dataset (V4 genome shards with full metadata)
R2_SONG_DATASET_BASE_URL = "https://pub-53b5eb7528ba49eaaf533b48541508ae.r2.dev/genome_shards_v4/"

# R2 base URL for shards within the dataset
R2_SONG_SHARDS_BASE_URL = R2_SONG_DATASET_BASE_URL

# R2 base URL for V4 index objects (stored with shards)
R2_INDEX_BASE_URL = R2_SONG_DATASET_BASE_URL

# R2 object name for precomputed artist index (generated locally and uploaded)
ARTISTS_INDEX_OBJECT = "index.json.gz"

# R2 object name for precomputed songs index (generated locally and uploaded)
SONGS_INDEX_OBJECT = "songs_index_v4.json.gz"


def _normalize_genre(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        out = []
        for x in raw:
            if isinstance(x, str):
                v = x.strip().strip('"\'')
                if v.startswith('['):
                    v = v[1:]
                if v.endswith(']'):
                    v = v[:-1]
                v = v.strip().strip('"\'')
                if v:
                    out.append(v)
        return out
    if not isinstance(raw, str):
        return []
    s = raw.strip()
    if not s:
        return []
    if s.startswith('[') and s.endswith(']'):
        s = s[1:-1]
    s = s.replace('"', "").replace("'", "")
    if s.startswith('['):
        s = s[1:]
    if s.endswith(']'):
        s = s[:-1]
    parts = [p.strip() for p in s.split(',') if p.strip()]
    return parts


def _song_has_genome(song: dict) -> bool:
    # V4 uses 'eli5_genome' field
    g = song.get('eli5_genome') or song.get('genome')
    return isinstance(g, dict) and isinstance(g.get('line_by_line_plot'), list) and bool(g.get('line_by_line_plot'))


def _song_has_pattison(song: dict) -> bool:
    p = song.get('pattison_analysis') or song.get('pattison')
    return isinstance(p, dict) and bool(p)


def _song_is_verified(song: dict) -> bool:
    if isinstance(song.get('verification'), dict):
        v = song['verification'].get('verified')
        if isinstance(v, bool):
            return v
    v2 = song.get('verified')
    return bool(v2) if isinstance(v2, bool) else False


@lru_cache(maxsize=1)
def build_songs_index_from_r2():
    manifest = fetch_manifest_from_r2()
    if not manifest:
        return None

    rows = []
    genre_counter = Counter()
    category_counter = Counter()
    source_counter = Counter()
    collection_counter = Counter()

    shard_keys = list(manifest.get('shards', {}).keys())

    max_workers = min(24, max(4, len(shard_keys)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_shard_from_r2_uncached, shard_key): shard_key for shard_key in shard_keys}
        for future in as_completed(futures):
            shard_key = futures[future]
            try:
                shard_data = future.result()
            except Exception as e:
                print(f"Error building index: shard {shard_key} failed: {e}")
                shard_data = None

            if not shard_data:
                continue
            songs = shard_data.get('songs', {})
            if not isinstance(songs, dict):
                continue
            for song_id, song in songs.items():
                if not isinstance(song, dict):
                    continue
                artist = song.get('artist')
                title = song.get('title')
                category = song.get('category')
                source = song.get('source')
                special_collection = song.get('special_collection')
                genres = _normalize_genre(song.get('genre'))

                has_genome = _song_has_genome(song)
                has_pattison = _song_has_pattison(song)
                verified = _song_is_verified(song)

                if genres:
                    for g in genres:
                        genre_counter[g] += 1
                else:
                    genre_counter['unknown'] += 1
                if isinstance(category, str) and category:
                    category_counter[category] += 1
                else:
                    category_counter['unknown'] += 1
                if isinstance(source, str) and source:
                    source_counter[source] += 1
                else:
                    source_counter['unknown'] += 1
                if isinstance(special_collection, str) and special_collection:
                    collection_counter[special_collection] += 1

                rows.append({
                    'song_id': song.get('song_id') or song_id,
                    'artist': artist or '',
                    'title': title or '',
                    'category': category if isinstance(category, str) else 'unknown',
                    'genres': genres or ['unknown'],
                    'source': source if isinstance(source, str) else 'unknown',
                    'special_collection': special_collection if isinstance(special_collection, str) else '',
                    'has_genome': bool(has_genome),
                    'has_pattison': bool(has_pattison),
                    'verified': bool(verified),
                })

    facets = {
        'genres': dict(genre_counter),
        'categories': dict(category_counter),
        'sources': dict(source_counter),
        'special_collections': dict(collection_counter),
    }
    return {
        'songs': rows,
        'facets': facets,
        'total': len(rows),
    }


def get_shard_key(song_id):
    """Get shard key (first 2 chars) from song_id."""
    if len(song_id) >= 2:
        return song_id[:2].lower()
    elif len(song_id) == 1:
        return song_id[0].lower() + '0'
    else:
        return '00'


@lru_cache(maxsize=4096)
def _find_shard_key_for_song_id(song_id: str):
    """Best-effort song_id -> shard_key resolution.

    The unified 110k dataset shard keys are not guaranteed to be song_id[:2].
    We first try the legacy prefix key, then fall back to scanning manifest shard keys.
    Result is cached to avoid repeated scans.
    """
    if not isinstance(song_id, str) or not song_id:
        return None

    manifest = fetch_manifest_from_r2()
    shards = (manifest or {}).get('shards')
    if not isinstance(shards, dict) or not shards:
        return get_shard_key(song_id)

    # First try legacy prefix shard key if it exists in manifest
    prefix_key = get_shard_key(song_id)
    if isinstance(prefix_key, str) and prefix_key in shards:
        shard_data = fetch_shard_from_r2(prefix_key)
        if shard_data and isinstance(shard_data.get('songs'), dict) and song_id in shard_data['songs']:
            return prefix_key

    # Fallback: scan shards until we find the song_id
    for shard_key in sorted([k for k in shards.keys() if isinstance(k, str)]):
        shard_data = fetch_shard_from_r2(shard_key)
        if not shard_data:
            continue
        songs = shard_data.get('songs')
        if isinstance(songs, dict) and song_id in songs:
            return shard_key

    return None


def fetch_shard_from_r2_uncached(shard_key):
    # V4 shards: genome_shards_v4_XX.json (uncompressed JSON arrays)
    shard_url = requests.utils.requote_uri(f"{R2_SONG_SHARDS_BASE_URL}genome_shards_v4_{shard_key}.json")

    try:
        response = requests.get(shard_url, timeout=10)
        response.raise_for_status()
        # V4 format: plain JSON array of songs
        songs_array = response.json()
        # Convert to dict keyed by song_id for compatibility
        return {'songs': {song['song_id']: song for song in songs_array if 'song_id' in song}}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching shard {shard_key}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching shard {shard_key}: {e}")
        return None


@lru_cache(maxsize=32)
def fetch_shard_from_r2(shard_key):
    """
    Fetch a shard from R2 with caching.
    
    Args:
        shard_key: Shard identifier (e.g., 'aa', '00', 'th')
    
    Returns:
        Shard data dict or None
    """
    # V4 shards: genome_shards_v4_XX.json (uncompressed JSON arrays)
    shard_url = requests.utils.requote_uri(f"{R2_SONG_SHARDS_BASE_URL}genome_shards_v4_{shard_key}.json")
    
    try:
        response = requests.get(shard_url, timeout=10)
        response.raise_for_status()
        
        # V4 format: plain JSON array of songs
        songs_array = response.json()
        # Convert to dict keyed by song_id for compatibility
        return {'songs': {song['song_id']: song for song in songs_array if 'song_id' in song}}
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching shard {shard_key}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching shard {shard_key}: {e}")
        return None


@lru_cache(maxsize=1)
def fetch_manifest_from_r2():
    """Fetch manifest from R2 with caching."""
    manifest_url = f"{R2_SONG_DATASET_BASE_URL}manifest.json"
    
    try:
        response = requests.get(manifest_url, timeout=10)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching manifest: {e}")
        return None


@lru_cache(maxsize=1)
def fetch_artists_index_from_r2():
    """Fetch precomputed artists index from R2 (gzipped JSON) with caching."""
    url = f"{R2_INDEX_BASE_URL}{ARTISTS_INDEX_OBJECT}"

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return json.loads(gzip.decompress(response.content))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching artists index: {e}")
        return None
    except Exception as e:
        print(f"Error parsing artists index: {e}")
        return None


def fetch_songs_index_from_r2():
    import time
    global _SONGS_INDEX_CACHE, _SONGS_INDEX_CACHE_TS

    now = time.time()
    if _SONGS_INDEX_CACHE is not None and (now - _SONGS_INDEX_CACHE_TS) < 300:
        return _SONGS_INDEX_CACHE

    url = f"{R2_INDEX_BASE_URL}{SONGS_INDEX_OBJECT}"
    last_error = None
    for _ in range(2):
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = json.loads(gzip.decompress(response.content))
            _SONGS_INDEX_CACHE = data
            _SONGS_INDEX_CACHE_TS = now
            return data
        except requests.exceptions.RequestException as e:
            last_error = e
            time.sleep(0.25)
        except Exception as e:
            last_error = e
            break

    print(f"Error fetching songs index: {last_error}")
    return None


@bp.route('/api/songs/<song_id>', methods=['GET'])
def get_song(song_id):
    """
    Get a song by ID from R2.
    
    Example: /api/songs/taylor_swift_love_story
    """
    shard_key = _find_shard_key_for_song_id(song_id) or get_shard_key(song_id)
    shard_data = fetch_shard_from_r2(shard_key)
    if not shard_data:
        return jsonify({'error': 'Shard not found'}), 404
    song = shard_data.get('songs', {}).get(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404
    return jsonify(song)


@bp.route('/api/songs/search', methods=['GET'])
def search_songs():
    """
    Faceted search using songs_index (memory-efficient).
    
    Query params:
      - q: text query (searches title, artist)
      - artist: filter by artist name
      - category: filter by category
      - genre: filter by genre
      - limit: results per page (default 50, max 200)
    
    Returns:
      { results: [...], total_returned: int }
    """
    query = request.args.get('q', '').lower().strip()
    artist_filter = request.args.get('artist', '').strip()
    category_filter = request.args.get('category', '').strip()
    genre_filter = request.args.get('genre', '').strip()
    
    try:
        limit = int(request.args.get('limit', 50))
    except:
        limit = 50
    limit = max(1, min(200, limit))
    
    # Use songs_index for memory-efficient search
    index_data = fetch_songs_index_from_r2()
    if not index_data:
        return jsonify({'error': 'Songs index not available'}), 503
    
    songs = index_data.get('songs', [])
    results = []
    
    for song in songs:
        # Apply filters
        if query:
            title_match = query in song.get('title', '').lower()
            artist_match = query in song.get('artist', '').lower()
            if not (title_match or artist_match):
                continue
        
        if artist_filter and song.get('artist', '').lower() != artist_filter.lower():
            continue
        
        if category_filter and song.get('category', '').lower() != category_filter.lower():
            continue
        
        if genre_filter:
            genres = song.get('genres', [])
            if isinstance(genres, str):
                genres = [genres]
            if genre_filter.lower() not in [g.lower() for g in genres]:
                continue

        # Build lightweight result (index already has enriched category/genres with no 'unknown')
        genres = song.get('genres', [])
        if isinstance(genres, str):
            genres = [genres]
        genres = [g for g in genres if isinstance(g, str) and g.strip() and g.strip().lower() != 'unknown']
        category = song.get('category', '')
        if not isinstance(category, str) or category.strip().lower() == 'unknown':
            category = ''
        source = song.get('source', '')
        if not isinstance(source, str) or source.strip().lower() == 'unknown':
            source = ''
        results.append({
            'song_id': song.get('song_id', ''),
            'artist': song.get('artist', ''),
            'title': song.get('title', ''),
            'category': category,
            'genres': genres,
            'year': song.get('year'),
            'has_genome': song.get('has_genome', False),
            'has_pattison': song.get('has_pattison', False),
            'verified': song.get('verified', False),
            'source': source,
            'special_collection': song.get('special_collection', '')
        })
        
        if len(results) >= limit:
            break
    
    return jsonify({
        'results': results,
        'total_returned': len(results)
    })


@bp.route('/api/songs/stats', methods=['GET'])
def get_stats():
    """Get database statistics from manifest."""
    manifest = fetch_manifest_from_r2()
    
    if not manifest:
        return jsonify({'error': 'Manifest not available'}), 503
    
    return jsonify({
        'total_songs': manifest['metadata']['total_songs'],
        'total_shards': manifest['metadata']['total_shards'],
        'version': manifest['metadata']['version'],
        'created': manifest['metadata']['created']
    })


@bp.route('/api/songs/facets', methods=['GET'])
def get_facets():
    """
    Get available facets for filtering (artists, categories, decades, genres).
    Uses cached songs_index if available, otherwise builds from manifest.
    """
    index_data = fetch_songs_index_from_r2()
    
    if index_data and isinstance(index_data, dict):
        facets = index_data.get('facets', {})
        if facets:
            try:
                # Extract decades from songs if not already in facets
                decades = set()
                for song in index_data.get('songs', []):
                    if not isinstance(song, dict):
                        continue
                    year = song.get('year')
                    if isinstance(year, (int, str)):
                        try:
                            year_int = int(year)
                            decade = f"{(year_int // 10) * 10}s"
                            decades.add(decade)
                        except Exception:
                            pass
                
                # Get top artists
                artist_counts = Counter()
                for song in index_data.get('songs', []):
                    if not isinstance(song, dict):
                        continue
                    artist_raw = song.get('artist')
                    artist = artist_raw.strip() if isinstance(artist_raw, str) else ''
                    if artist:
                        artist_counts[artist] += 1
                
                # Group artists by first letter
                artists_by_letter = {}
                for artist, count in artist_counts.items():
                    first_letter = artist[0].upper() if artist else '#'
                    if not first_letter.isalpha():
                        first_letter = '#'
                    if first_letter not in artists_by_letter:
                        artists_by_letter[first_letter] = []
                    artists_by_letter[first_letter].append({'name': artist, 'count': count})
                
                # Sort artists within each letter
                for letter in artists_by_letter:
                    artists_by_letter[letter].sort(key=lambda x: x['name'].lower())
                
                def _facet_list(val):
                    if isinstance(val, list):
                        out = []
                        for item in val:
                            if not isinstance(item, dict):
                                continue
                            name = item.get('name')
                            count = item.get('count', 0)
                            if isinstance(name, str) and name.strip() and name.strip().lower() != 'unknown':
                                out.append({'name': name.strip(), 'count': int(count) if isinstance(count, (int, float, str)) and str(count).isdigit() else count})
                        return out
                    if isinstance(val, dict):
                        return [
                            {'name': k, 'count': v}
                            for k, v in val.items()
                            if isinstance(k, str) and k.strip() and k.strip().lower() != 'unknown'
                        ]
                    return []

                categories_out = _facet_list(facets.get('categories'))
                genres_out = _facet_list(facets.get('genres'))
                sources_out = _facet_list(facets.get('sources'))
                return jsonify({
                    'artists': [{'name': artist, 'count': count} for artist, count in artist_counts.most_common(100)],
                    'artists_by_letter': artists_by_letter,
                    'total_artists': len(artist_counts),
                    'categories': categories_out,
                    'genres': genres_out,
                    'decades': sorted(list(decades), reverse=True),
                    'sources': sources_out,
                    'special_collections': [
                        x for x in _facet_list(facets.get('special_collections'))
                        if isinstance(x, dict) and isinstance(x.get('name'), str) and x.get('name').strip()
                    ]
                })
            except Exception as e:
                print(f"Error building facets from songs index: {e}")
                return jsonify({'error': 'Failed to build facets from songs index'}), 500
    
    # Fallback: build minimal facets from manifest
    manifest = fetch_manifest_from_r2()
    if not manifest:
        return jsonify({'error': 'Facets not available'}), 503
    
    return jsonify({
        'artists': [],
        'categories': [],
        'genres': [],
        'decades': [],
        'sources': [],
        'special_collections': [],
        'note': 'Full facets require songs_index.json.gz to be uploaded to R2'
    })


@bp.route('/api/songs/random', methods=['GET'])
def get_random_song():
    """
    Get a random song from the database.
    Used for 'Song of the Day' feature.
    """
    import random
    
    manifest = fetch_manifest_from_r2()
    if not manifest:
        return jsonify({'error': 'Manifest not available'}), 503
    
    shard_keys = list(manifest.get('shards', {}).keys())
    if not shard_keys:
        return jsonify({'error': 'No shards available'}), 503
    
    # Pick a random shard
    random_shard_key = random.choice(shard_keys)
    shard_data = fetch_shard_from_r2(random_shard_key)
    
    if not shard_data or not shard_data.get('songs'):
        return jsonify({'error': 'Shard empty'}), 503
    
    # Pick a random song from the shard
    song_ids = list(shard_data['songs'].keys())
    random_song_id = random.choice(song_ids)
    song = shard_data['songs'][random_song_id]
    
    return jsonify(song)


@bp.route('/api/songs/browse', methods=['GET'])
def browse_songs():
    """Browse songs with pagination without requiring a full songs index.

    Query params:
      - offset: global offset into the dataset (default 0)
      - limit: number of songs to return (default 50, max 200)

    Ordering:
      - Shard key ascending
      - Song ID ascending within each shard

    Returns:
      { offset, limit, total_songs, results: [...], next_offset }
    """
    try:
        offset = int(request.args.get('offset', 0))
    except Exception:
        offset = 0
    try:
        limit = int(request.args.get('limit', 50))
    except Exception:
        limit = 50
    offset = max(0, offset)
    limit = max(1, min(200, limit))

    manifest = fetch_manifest_from_r2()
    if not manifest:
        return jsonify({'error': 'Manifest not available'}), 503

    total_songs = (manifest.get('metadata') or {}).get('total_songs')
    if not isinstance(total_songs, int):
        total_songs = None

    shards = manifest.get('shards', {})
    if not isinstance(shards, dict) or not shards:
        return jsonify({'error': 'Manifest shards not available'}), 503

    ordered_shard_keys = sorted([k for k in shards.keys() if isinstance(k, str)])
    remaining_offset = offset
    results = []

    for shard_key in ordered_shard_keys:
        shard_meta = shards.get(shard_key) if isinstance(shards.get(shard_key), dict) else {}
        shard_count = shard_meta.get('song_count')
        if not isinstance(shard_count, int):
            shard_count = None

        if shard_count is not None and remaining_offset >= shard_count:
            remaining_offset -= shard_count
            continue

        shard_data = fetch_shard_from_r2(shard_key)
        if not shard_data:
            continue
        songs = shard_data.get('songs', {})
        if not isinstance(songs, dict) or not songs:
            continue

        song_ids = sorted(songs.keys())
        start_idx = remaining_offset if remaining_offset > 0 else 0
        remaining_offset = 0

        for song_id in song_ids[start_idx:]:
            song = songs.get(song_id)
            if not isinstance(song, dict):
                continue
            genres = _normalize_genre(song.get('genre'))
            results.append({
                'song_id': song.get('song_id') or song_id,
                'artist': song.get('artist') or '',
                'title': song.get('title') or '',
                'category': song.get('category') if isinstance(song.get('category'), str) else 'unknown',
                'genres': genres or ['unknown'],
                'source': song.get('source') if isinstance(song.get('source'), str) else 'unknown',
                'special_collection': song.get('special_collection') if isinstance(song.get('special_collection'), str) else '',
                'has_genome': bool(_song_has_genome(song) or bool(song.get('genome_analysis'))),
                'has_pattison': bool(_song_has_pattison(song)),
                'verified': bool(_song_is_verified(song)),
                'lyrics_length': len(song.get('lyrics') or song.get('cleaned_lyrics') or '')
            })
            if len(results) >= limit:
                break

        if len(results) >= limit:
            break

    next_offset = offset + len(results)
    if isinstance(total_songs, int) and next_offset >= total_songs:
        next_offset = None

    return jsonify({
        'offset': offset,
        'limit': limit,
        'total_songs': total_songs,
        'results': results,
        'next_offset': next_offset,
    })


@bp.route('/api/songs/artists', methods=['GET'])
def get_artists():
    """
    Get list of all artists.
    
    Uses a precomputed artists index (artists_index.json.gz) stored in R2.
    """
    index = fetch_artists_index_from_r2()
    if not index:
        return jsonify({
            'error': 'Artists index not available',
            'hint': f"Upload {ARTISTS_INDEX_OBJECT} to {R2_INDEX_BASE_URL}"
        }), 503

    return jsonify(index)


@bp.route('/api/songs/artist/<artist_name>', methods=['GET'])
def get_artist_songs(artist_name):
    """
    Get all songs by an artist.
    
    Example: /api/songs/artist/Taylor Swift
    """
    index = fetch_artists_index_from_r2()
    if not index:
        return jsonify({
            'error': 'Artists index not available',
            'hint': f"Upload {ARTISTS_INDEX_OBJECT} to {R2_INDEX_BASE_URL}"
        }), 503

    # index format: { artists: [{artist, song_count, songs:[{song_id,title}]}], total_artists }
    target = None
    for a in index.get('artists', []):
        if a.get('artist', '').lower() == artist_name.lower():
            target = a
            break

    if not target:
        return jsonify({'artist': artist_name, 'songs': [], 'count': 0})

    return jsonify({
        'artist': target.get('artist', artist_name),
        'songs': target.get('songs', []),
        'count': target.get('song_count', len(target.get('songs', [])))
    })


@bp.route('/api/songs/index', methods=['GET'])
def get_songs_index():
    # Server-side cache bust: refresh the in-memory lru_cache for songs_index.json.gz
    # This is necessary after uploading a new songs_index.json.gz to R2.
    if request.args.get('refresh') == '1':
        try:
            fetch_songs_index_from_r2.cache_clear()
        except Exception:
            pass

    manifest = fetch_manifest_from_r2()
    expected_total = None
    if manifest and isinstance(manifest, dict):
        expected_total = (manifest.get('metadata') or {}).get('total_songs')

    index = fetch_songs_index_from_r2()
    if index and isinstance(index, dict):
        actual_total = index.get('total')
        if not isinstance(actual_total, int):
            songs = index.get('songs')
            if isinstance(songs, list):
                actual_total = len(songs)

        if isinstance(expected_total, int) and isinstance(actual_total, int) and expected_total != actual_total:
            index = None
        else:
            return jsonify(index)

    if request.args.get('rebuild') == '1' or (isinstance(expected_total, int) and index is None):
        try:
            build_songs_index_from_r2.cache_clear()
        except Exception:
            pass
        index = build_songs_index_from_r2()
        if index:
            return jsonify(index)

    return jsonify({
        'error': 'Songs index not available',
        'hint': f"Upload {SONGS_INDEX_OBJECT} to {R2_INDEX_BASE_URL}",
        'expected_total_songs': expected_total,
    }), 503
