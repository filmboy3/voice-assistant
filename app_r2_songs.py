#!/usr/bin/env python3
"""
R2 Songs Database API (V4 Shards)

Fetches songs from R2 master database at:
https://pub-53b5eb7528ba49eaaf533b48541508ae.r2.dev/genome_shards_v4/
"""

from flask import Blueprint, jsonify, request
import json
import gzip
import requests
import hashlib
import time
from functools import lru_cache
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

bp = Blueprint('r2_songs', __name__)

_SONGS_INDEX_CACHE = None
_SONGS_INDEX_CACHE_TS = 0

# R2 base URL for songs dataset (V4 genome shards with full metadata)
R2_SONG_DATASET_BASE_URL = "https://pub-53b5eb7528ba49eaaf533b48541508ae.r2.dev/genome_shards_v4/"
R2_SONG_SHARDS_BASE_URL = R2_SONG_DATASET_BASE_URL
R2_INDEX_BASE_URL = R2_SONG_DATASET_BASE_URL

# R2 object names
ARTISTS_INDEX_OBJECT = "index.json.gz"
SONGS_INDEX_OBJECT = "songs_index_v4.json.gz"

def _rename_source(source):
    if source == 'production_pipeline_v3_inclusive':
        return 'V4 R2 Master'
    return source

def _process_index_for_display(index):
    if not index or not isinstance(index, dict):
        return index
    
    # Rename in facets
    if 'facets' in index and 'sources' in index['facets']:
        sources = index['facets']['sources']
        if isinstance(sources, dict) and 'production_pipeline_v3_inclusive' in sources:
            val = sources.pop('production_pipeline_v3_inclusive')
            sources['V4 R2 Master'] = val
        elif isinstance(sources, list):
            for item in sources:
                if isinstance(item, dict) and item.get('name') == 'production_pipeline_v3_inclusive':
                    item['name'] = 'V4 R2 Master'
    
    # Rename in songs list
    if 'songs' in index and isinstance(index['songs'], list):
        for song in index['songs']:
            if song.get('source') == 'production_pipeline_v3_inclusive':
                song['source'] = 'V4 R2 Master'
    
    return index

def _normalize_genre(raw):
    if raw is None: return []
    if isinstance(raw, list):
        out = []
        for x in raw:
            if isinstance(x, str):
                v = x.strip().strip('"\'')
                if v.startswith('['): v = v[1:]
                if v.endswith(']'): v = v[:-1]
                v = v.strip().strip('"\'')
                if v: out.append(v)
        return out
    if not isinstance(raw, str): return []
    s = raw.strip()
    if not s: return []
    if s.startswith('[') and s.endswith(']'): s = s[1:-1]
    s = s.replace('"', "").replace("'", "")
    return [p.strip() for p in s.split(',') if p.strip()]

def _song_has_genome(song: dict) -> bool:
    g = song.get('eli5_genome') or song.get('genome')
    return isinstance(g, dict) and isinstance(g.get('line_by_line_plot'), list) and bool(g.get('line_by_line_plot'))

def _song_has_pattison(song: dict) -> bool:
    p = song.get('pattison_analysis') or song.get('pattison')
    return isinstance(p, dict) and bool(p)

def _song_is_verified(song: dict) -> bool:
    if isinstance(song.get('verification'), dict):
        v = song['verification'].get('verified')
        if isinstance(v, bool): return v
    v2 = song.get('verified')
    return bool(v2) if isinstance(v2, bool) else False

@lru_cache(maxsize=1)
def fetch_manifest_from_r2():
    manifest_url = f"{R2_SONG_DATASET_BASE_URL}manifest.json"
    try:
        response = requests.get(manifest_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching manifest: {e}")
        return None

def fetch_songs_index_from_r2():
    global _SONGS_INDEX_CACHE, _SONGS_INDEX_CACHE_TS
    now = time.time()
    if _SONGS_INDEX_CACHE is not None and (now - _SONGS_INDEX_CACHE_TS) < 300:
        return _SONGS_INDEX_CACHE

    url = f"{R2_INDEX_BASE_URL}{SONGS_INDEX_OBJECT}"
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = json.loads(gzip.decompress(response.content))
        _SONGS_INDEX_CACHE = data
        _SONGS_INDEX_CACHE_TS = now
        return data
    except Exception as e:
        print(f"Error fetching songs index: {e}")
        return None

def fetch_artists_index_from_r2():
    url = f"{R2_INDEX_BASE_URL}{ARTISTS_INDEX_OBJECT}"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return json.loads(gzip.decompress(response.content))
    except Exception as e:
        print(f"Error fetching artists index: {e}")
        return None

def get_shard_key(song_id):
    if not song_id: return '00'
    return hashlib.md5(str(song_id).encode('utf-8')).hexdigest()[:2].lower()

@lru_cache(maxsize=4096)
def _find_shard_key_for_song_id(song_id: str):
    if not isinstance(song_id, str) or not song_id: return None
    return get_shard_key(song_id)

@lru_cache(maxsize=32)
def fetch_shard_from_r2(shard_key):
    shard_url = requests.utils.requote_uri(f"{R2_SONG_SHARDS_BASE_URL}genome_shards_v4_{shard_key}.json")
    try:
        response = requests.get(shard_url, timeout=10)
        response.raise_for_status()
        songs_array = response.json()
        return {'songs': {song['song_id']: song for song in songs_array if 'song_id' in song}}
    except Exception as e:
        print(f"Error fetching shard {shard_key}: {e}")
        return None

@bp.route('/api/songs/<song_id>', methods=['GET'])
def get_song(song_id):
    shard_key = _find_shard_key_for_song_id(song_id)
    shard_data = fetch_shard_from_r2(shard_key)
    if not shard_data: return jsonify({'error': 'Shard not found'}), 404
    song = shard_data.get('songs', {}).get(song_id)
    if not song: return jsonify({'error': 'Song not found'}), 404
    if song.get('source') == 'production_pipeline_v3_inclusive':
        song['source'] = 'V4 R2 Master'
    return jsonify(song)

@bp.route('/api/songs/index', methods=['GET'])
def get_songs_index():
    if request.args.get('refresh') == '1':
        fetch_songs_index_from_r2.cache_clear()
    index = fetch_songs_index_from_r2()
    if not index:
        return jsonify({'error': 'Songs index not available'}), 503
    return jsonify(_process_index_for_display(index))

@bp.route('/api/songs/stats', methods=['GET'])
def get_stats():
    manifest = fetch_manifest_from_r2()
    if not manifest: return jsonify({'error': 'Manifest not available'}), 503
    total_songs = sum(s.get('song_count', 0) for s in manifest.get('shards', {}).values())
    return jsonify({
        'total_songs': total_songs,
        'total_shards': len(manifest.get('shards', {})),
        'version': manifest.get('metadata', {}).get('version', 'v4'),
        'created': manifest.get('metadata', {}).get('created', 'unknown')
    })

@bp.route('/api/songs/search', methods=['GET'])
def search_songs():
    query = request.args.get('q', '').lower().strip()
    artist_filter = request.args.get('artist', '').strip()
    category_filter = request.args.get('category', '').strip()
    genre_filter = request.args.get('genre', '').strip()
    try: limit = int(request.args.get('limit', 50))
    except: limit = 50
    limit = max(1, min(200, limit))
    index_data = fetch_songs_index_from_r2()
    if not index_data: return jsonify({'error': 'Songs index not available'}), 503
    songs = index_data.get('songs', [])
    results = []
    for song in songs:
        if query:
            if query not in song.get('title', '').lower() and query not in song.get('artist', '').lower():
                continue
        if artist_filter and song.get('artist', '').lower() != artist_filter.lower(): continue
        if category_filter and song.get('category', '').lower() != category_filter.lower(): continue
        if genre_filter:
            genres = [g.lower() for g in (song.get('genres') or [])]
            if genre_filter.lower() not in genres: continue
        res = song.copy()
        res['source'] = _rename_source(res.get('source', ''))
        results.append(res)
        if len(results) >= limit: break
    return jsonify({'results': results, 'total_returned': len(results)})

@bp.route('/api/songs/facets', methods=['GET'])
def get_facets():
    index_data = fetch_songs_index_from_r2()
    if not index_data: return jsonify({'error': 'Facets not available'}), 503
    facets = index_data.get('facets', {})
    def _facet_list(val):
        if isinstance(val, dict):
            return [{'name': _rename_source(k), 'count': v} for k, v in val.items() if k.lower() != 'unknown']
        return []
    artist_counts = Counter()
    decades = set()
    for song in index_data.get('songs', []):
        if song.get('artist'): artist_counts[song['artist']] += 1
        if song.get('decade'): decades.add(song['decade'])
    artists_by_letter = {}
    for artist, count in artist_counts.items():
        letter = artist[0].upper() if artist else '#'
        if not letter.isalpha(): letter = '#'
        if letter not in artists_by_letter: artists_by_letter[letter] = []
        artists_by_letter[letter].append({'name': artist, 'count': count})
    for letter in artists_by_letter:
        artists_by_letter[letter].sort(key=lambda x: x['name'].lower())
    return jsonify({
        'artists': [{'name': artist, 'count': count} for artist, count in artist_counts.most_common(100)],
        'artists_by_letter': artists_by_letter,
        'total_artists': len(artist_counts),
        'categories': _facet_list(facets.get('categories')),
        'genres': _facet_list(facets.get('genres')),
        'decades': sorted(list(decades), reverse=True),
        'sources': _facet_list(facets.get('sources')),
        'special_collections': _facet_list(facets.get('special_collections'))
    })

@bp.route('/api/songs/random', methods=['GET'])
def get_random_song():
    import random
    manifest = fetch_manifest_from_r2()
    if not manifest: return jsonify({'error': 'Manifest not available'}), 503
    shard_keys = list(manifest.get('shards', {}).keys())
    if not shard_keys: return jsonify({'error': 'No shards available'}), 503
    random_shard_key = random.choice(shard_keys)
    shard_data = fetch_shard_from_r2(random_shard_key)
    if not shard_data or not shard_data.get('songs'): return jsonify({'error': 'Shard empty'}), 503
    song_ids = list(shard_data['songs'].keys())
    random_song_id = random.choice(song_ids)
    song = shard_data['songs'][random_song_id]
    if song.get('source') == 'production_pipeline_v3_inclusive':
        song['source'] = 'V4 R2 Master'
    return jsonify(song)

@bp.route('/api/songs/browse', methods=['GET'])
def browse_songs():
    try: offset = int(request.args.get('offset', 0))
    except: offset = 0
    try: limit = int(request.args.get('limit', 50))
    except: limit = 50
    offset = max(0, offset)
    limit = max(1, min(200, limit))
    manifest = fetch_manifest_from_r2()
    if not manifest: return jsonify({'error': 'Manifest not available'}), 503
    shards = manifest.get('shards', {})
    ordered_keys = sorted(shards.keys())
    total_songs = sum(s.get('song_count', 0) for s in shards.values())
    results = []
    curr = 0
    for skey in ordered_keys:
        scount = shards[skey].get('song_count', 0)
        if curr + scount <= offset:
            curr += scount
            continue
        shard_data = fetch_shard_from_r2(skey)
        if not shard_data: continue
        songs = sorted(shard_data['songs'].values(), key=lambda x: x.get('song_id'))
        for s in songs:
            if curr < offset:
                curr += 1
                continue
            res = {
                'song_id': s.get('song_id'),
                'artist': s.get('artist'),
                'title': s.get('title'),
                'category': s.get('category'),
                'genres': s.get('genres'),
                'source': _rename_source(s.get('source')),
                'has_genome': _song_has_genome(s),
                'has_pattison': _song_has_pattison(s),
                'verified': _song_is_verified(s)
            }
            results.append(res)
            curr += 1
            if len(results) >= limit: break
        if len(results) >= limit: break
    return jsonify({
        'results': results,
        'offset': offset,
        'limit': limit,
        'total_songs': total_songs,
        'next_offset': offset + len(results) if offset + len(results) < total_songs else None
    })

@bp.route('/api/songs/artist/<artist_name>', methods=['GET'])
def get_artist_songs(artist_name):
    index = fetch_artists_index_from_r2()
    if not index: return jsonify({'error': 'Artists index not available'}), 503
    target = None
    for a in index.get('artists', []):
        if a.get('artist', '').lower() == artist_name.lower():
            target = a
            break
    if not target: return jsonify({'artist': artist_name, 'songs': [], 'count': 0})
    return jsonify({
        'artist': target.get('artist', artist_name),
        'songs': target.get('songs', []),
        'count': target.get('song_count', len(target.get('songs', [])))
    })

@bp.route('/api/songs/artists', methods=['GET'])
def get_artists():
    index = fetch_artists_index_from_r2()
    if not index: return jsonify({'error': 'Artists index not available'}), 503
    return jsonify(_process_index_for_display(index))
