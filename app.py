import os
import time
from collections import deque
from pathlib import Path
import gzip
import requests

import json
import re
from typing import Any, Dict, Optional

from flask import Flask, Response, send_file, abort, redirect, request, jsonify


APP_ROOT = Path(__file__).resolve().parent
DYNAMIC_GENS_HTML_PATH = APP_ROOT / "dynamic_gens.html"
RHYME_HTML_PATH = APP_ROOT / "rhyme_search_tool.html"
HOME_HTML_PATH = APP_ROOT / "home.html"
TONE_HTML_PATH = APP_ROOT / "tone_search.html"
CREATIVE_GENS_HTML_PATH = APP_ROOT / "creative_gens.html"
CREATIVE_QUOTES_HTML_PATH = APP_ROOT / "creative_quotes.html"
QUICK_HELPER_HTML_PATH = APP_ROOT / "quick_helper.html"
IDIOMS_LIST_JSON_PATH = APP_ROOT / "IdiomsList.json"
QUICK_HITS_SOURCE_PATH = APP_ROOT / "LLM_Latest_Quick_Hits_Page"
GLOBAL_NAV_JS_PATH = APP_ROOT / "global_nav.js"
NOTES_MANAGER_JS_PATH = APP_ROOT / "notes_manager.js"
SHARED_INTERACTIONS_JS_PATH = APP_ROOT / "shared_interactions.js"
SW_JS_PATH = APP_ROOT / "sw.js"
OFFLINE_LIBRARY_HTML_PATH = APP_ROOT / "offline_library.html"
OFFLINE_LIBRARY_MANAGER_JS_PATH = APP_ROOT / "offline_library_manager.js"
EXPORT_MANAGER_HTML_PATH = APP_ROOT / "export_manager.html"
EXPORT_MANAGER_JS_PATH = APP_ROOT / "export_manager.js"

PATTISON_EXERCISE_LAB_HTML_PATH = APP_ROOT / "pattison_exercise_lab.html"
PAT_BOOK_TXT_PATH = APP_ROOT / "docs" / "handoff" / "PattisonPlan" / "PatBook.txt"

# R2 CDN URL for rhyme data
R2_CDN_BASE = os.getenv("R2_CDN_BASE", "https://pub-53b5eb7528ba49eaaf533b48541508ae.r2.dev")
# Local data path for Creative Quotes
DATA_DIR = APP_ROOT / "data"


def create_app() -> Flask:
    app = Flask(__name__)

    _rate_limit_buckets = {}

    def _client_ip() -> str:
        try:
            xff = (request.headers.get("X-Forwarded-For") or "").strip()
            if xff:
                return xff.split(",")[0].strip()
        except Exception:
            pass
        try:
            return (request.remote_addr or "").strip() or "unknown"
        except Exception:
            return "unknown"

    def _rate_limit_check(key: str, *, limit: int, window_seconds: int):
        now = time.time()
        bucket = _rate_limit_buckets.get(key)
        if bucket is None:
            bucket = deque()
            _rate_limit_buckets[key] = bucket

        cutoff = now - float(window_seconds)
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= int(limit):
            oldest = bucket[0] if bucket else now
            retry_after = max(1, int(window_seconds - (now - oldest)))
            resp = jsonify({
                "success": False,
                "error": "Rate limit exceeded",
                "retry_after_seconds": retry_after,
                "limit": int(limit),
                "window_seconds": int(window_seconds),
            })
            out = Response(resp.get_data(as_text=False), status=429, mimetype="application/json")
            out.headers["Retry-After"] = str(retry_after)
            out.headers["Cache-Control"] = "no-store"
            return out

        bucket.append(now)
        return None

    def _enforce_agentic_rate_limit(endpoint_name: str):
        if not _is_staging_request():
            return None
        ip = _client_ip()
        key = f"agentic:{endpoint_name}:{ip}"
        return _rate_limit_check(key, limit=30, window_seconds=60)

    def _is_staging_env() -> bool:
        env = (os.getenv("TUNE_TUNER_ENV") or os.getenv("FLASK_ENV") or "").strip().lower()
        return env == "staging"

    def _is_staging_request() -> bool:
        if _is_staging_env():
            return True
        try:
            host = (request.host or "").strip().lower()
        except RuntimeError:
            host = ""
        return "staging" in host

    def _anthropic_enabled() -> bool:
        if not _is_staging_request():
            return False
        enabled = (os.getenv("ENABLE_ANTHROPIC_LLM") or "").strip().lower() in {"1", "true", "yes"}
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        return bool(enabled and api_key)

    def _anthropic_model() -> str:
        return (os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest").strip()

    def _anthropic_messages(*, system: str, user: str, max_tokens: int = 1200, temperature: float = 0.7) -> str:
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY")

        payload = {
            "model": _anthropic_model(),
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            timeout=45,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        if not resp.ok:
            raise RuntimeError(f"Anthropic HTTP {resp.status_code}: {(resp.text or '')[:400]}")

        data = resp.json()
        content = data.get("content")
        if not isinstance(content, list) or not content:
            raise RuntimeError("Anthropic response missing content")
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text") or ""))
        return "\n".join(text_parts).strip()

    def _extract_json_object(text: str) -> Dict[str, Any]:
        raw = (text or "").strip()
        if not raw:
            raise ValueError("Empty response")
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found")
        candidate = raw[start : end + 1]
        return json.loads(candidate)

    def _anthropic_enrich_outline(*, theme: str, tone: str, structure: str, outline: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        system = (
            "You are an expert songwriting assistant. You will be given a song outline scaffold (sections, rhyme plan, tone words). "
            "Return ONLY a JSON object. Do not include backticks or commentary."
        )
        user = (
            "TASK: Fill in 'goal' for each section with 1-2 vivid sentences, and add 'bullets' (array of 3-5 short beat ideas) per section. "
            "Do NOT change rhyme_scheme, rhyme_plan, tone_words, or constraints.\n\n"
            f"Theme: {theme}\nTone: {tone}\nStructure: {structure}\n\n"
            "Outline scaffold JSON:\n"
            + json.dumps(outline, ensure_ascii=False)
            + "\n\nReturn JSON: {\"sections\": {<section_name>: {\"goal\": str, \"bullets\": [str,...]}}}"
        )
        text = _anthropic_messages(system=system, user=user, max_tokens=1400, temperature=0.6)
        obj = _extract_json_object(text)
        if not isinstance(obj, dict):
            return None
        sections = obj.get("sections")
        if not isinstance(sections, dict):
            return None
        for section_name, patch in sections.items():
            if section_name in outline and isinstance(outline.get(section_name), dict) and isinstance(patch, dict):
                goal = patch.get("goal")
                if isinstance(goal, str):
                    outline[section_name]["goal"] = goal
                bullets = patch.get("bullets")
                if isinstance(bullets, list):
                    outline[section_name]["bullets"] = [str(b) for b in bullets if b is not None][:6]
        return outline

    def _anthropic_generate_lyrics(*, theme: str, tone: str, structure: str, outline: Dict[str, Any]) -> Optional[str]:
        system = (
            "You are an expert songwriter. Generate lyrics that feel musical and concrete. "
            "You MUST follow rhyme endings exactly where provided."
        )
        user = (
            "Return ONLY the lyrics text (no JSON, no markdown).\n\n"
            "Format rules:\n"
            "- For each section, write a header line: [section_name]\n"
            "- Then write one lyric line per rhyme_plan line_*_ending.\n"
            "- Each lyric line MUST end with the exact ending word given (case-insensitive).\n"
            "- Put a blank line between sections.\n\n"
            f"Theme: {theme}\nTone: {tone}\nStructure: {structure}\n\n"
            "Outline JSON (includes rhyme_plan endings):\n"
            + json.dumps(outline, ensure_ascii=False)
        )
        text = _anthropic_messages(system=system, user=user, max_tokens=1600, temperature=0.8)
        lyrics = (text or "").strip()
        if not lyrics:
            return None
        if not lyrics.endswith("\n"):
            lyrics += "\n"
        return lyrics

    def _anthropic_critique(*, lyrics: str, focus_areas: Optional[list[str]] = None) -> Optional[Dict[str, Any]]:
        system = (
            "You are a precise songwriting critic. Return ONLY a JSON object matching the requested schema. "
            "No markdown, no backticks, no commentary."
        )
        focus = focus_areas or ["rhyme", "meter", "imagery", "cliche", "repetition"]
        user = (
            "Analyze the lyrics and return JSON with:\n"
            "{\n"
            "  \"success\": true,\n"
            "  \"scores\": {\"overall\": number, \"originality\": number, \"meter_consistency\": number, \"repetition_control\": number},\n"
            "  \"issues\": [{\"type\": str, \"severity\": \"low\"|\"medium\"|\"high\", \"location\": str, \"text\": str, \"note\": str?}],\n"
            "  \"strengths\": [str],\n"
            "  \"metadata\": {\"lines\": number}\n"
            "}\n\n"
            f"Focus areas: {', '.join(focus)}\n\nLyrics:\n{lyrics}\n"
        )
        text = _anthropic_messages(system=system, user=user, max_tokens=900, temperature=0.4)
        obj = _extract_json_object(text)
        if not isinstance(obj, dict) or not obj.get("success"):
            return None
        return obj

    def _feature_flags() -> dict:
        is_staging = _is_staging_request()
        return {
            "mcp_server": bool(is_staging),
            "service_worker": bool(is_staging),
            "agentic_endpoints": bool(is_staging),
            "offline_library_ui": bool(is_staging),
            "export_manager": bool(is_staging),
            "pattison_exercise_lab": bool(is_staging),
            "anthropic_llm": bool(_anthropic_enabled()),
        }

    from app_r2_songs import bp as r2_songs_bp
    app.register_blueprint(r2_songs_bp)

    @app.route("/favicon.ico")
    def favicon():
        icon_path = APP_ROOT / "favicon.ico"
        if icon_path.exists():
            return send_file(icon_path)
        return Response(status=204)

    @app.route("/api/features")
    def api_features():
        if not _is_staging_request():
            abort(404)
        response = jsonify({
            "environment": "staging" if _is_staging_request() else "production",
            "features": _feature_flags(),
        })
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/")
    def index():
        """Serve Search (canonical)"""
        return send_file(RHYME_HTML_PATH)

    @app.route("/home")
    def home():
        """Serve Home dashboard"""
        return send_file(HOME_HTML_PATH)

    @app.route("/rhyme-search")
    def rhyme_search():
        qs = request.query_string.decode("utf-8", errors="ignore") if request.query_string else ""
        target = f"/?{qs}" if qs else "/"
        return redirect(target, code=302)
    
    @app.route("/tones")
    def tones():
        """Serve tone cluster search"""
        return send_file(TONE_HTML_PATH)
    
    @app.route("/creative-gens")
    def creative_gens():
        """Serve Creative Gens browser"""
        return send_file(CREATIVE_GENS_HTML_PATH)

    @app.route("/quick-helper")
    def quick_helper():
        """Serve Quick Helper browser"""
        return send_file(QUICK_HELPER_HTML_PATH)
    
    @app.route("/global-nav.js")
    def global_nav_js():
        """Serve the shared global navbar script"""
        return send_file(GLOBAL_NAV_JS_PATH, mimetype='application/javascript')

    @app.route("/notes_manager.js")
    def notes_manager_js():
        """Serve the shared notes drawer manager script"""
        return send_file(NOTES_MANAGER_JS_PATH, mimetype='application/javascript')
    
    @app.route("/shared_interactions.js")
    def shared_interactions_js():
        """Serve shared interactions JS"""
        return send_file(SHARED_INTERACTIONS_JS_PATH, mimetype='application/javascript')
    
    @app.route("/shared-cache.js")
    def shared_cache_js():
        """Serve the shared caching script"""
        return send_file(APP_ROOT / "shared_cache.js")

    @app.route("/sw.js")
    def service_worker_js():
        if not _is_staging_request():
            abort(404)
        return send_file(SW_JS_PATH, mimetype='application/javascript')

    @app.route("/offline-library")
    def offline_library():
        if not _is_staging_request():
            abort(404)
        return send_file(OFFLINE_LIBRARY_HTML_PATH)

    @app.route("/offline_library_manager.js")
    def offline_library_manager_js():
        if not _is_staging_request():
            abort(404)
        return send_file(OFFLINE_LIBRARY_MANAGER_JS_PATH, mimetype='application/javascript')

    @app.route("/export-manager")
    def export_manager():
        if not _is_staging_request():
            abort(404)
        return send_file(EXPORT_MANAGER_HTML_PATH)

    @app.route("/export_manager.js")
    def export_manager_js():
        if not _is_staging_request():
            abort(404)
        return send_file(EXPORT_MANAGER_JS_PATH, mimetype='application/javascript')

    @app.route("/pattison-exercise-lab")
    def pattison_exercise_lab():
        if not _is_staging_request():
            abort(404)
        if PATTISON_EXERCISE_LAB_HTML_PATH.exists():
            return send_file(PATTISON_EXERCISE_LAB_HTML_PATH)
        abort(404, description="Pattison Exercise Lab page not found")

    def _extract_quick_hits_json() -> dict:
        if not QUICK_HITS_SOURCE_PATH.exists():
            abort(404, description="Quick hits source file not found")
        text = QUICK_HITS_SOURCE_PATH.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"```json\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        if not m:
            abort(500, description="Unable to locate JSON block in quick hits source")
        raw = m.group(1)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            abort(500, description="Quick hits JSON block is not valid JSON")

    @app.route("/api/quick-hits")
    def quick_hits_data():
        """Return the embedded Quick Hits dictionary JSON from the source file."""
        payload = _extract_quick_hits_json()
        return Response(json.dumps(payload), mimetype="application/json")

    @app.route("/api/idioms-list")
    def idioms_list_data():
        if not IDIOMS_LIST_JSON_PATH.exists():
            abort(404, description="IdiomsList.json not found")
        return send_file(IDIOMS_LIST_JSON_PATH, mimetype="application/json")

    @app.route("/api/fallback/rhymes")
    def fallback_rhymes():
        word = (os.environ.get("_", "") and "")  # no-op to keep linters quiet
        from flask import request
        word = (request.args.get("word") or "").strip()
        if not word:
            return Response("[]", mimetype="application/json")
        upstream = requests.get(
            "https://api.datamuse.com/words",
            params={"rel_rhy": word, "max": 60},
            timeout=15,
        )
        if not upstream.ok:
            abort(502, description="Fallback rhyme upstream failed")
        return Response(upstream.content, mimetype="application/json")

    @app.route("/api/fallback/synonyms")
    def fallback_synonyms():
        from flask import request
        word = (request.args.get("word") or "").strip()
        if not word:
            return Response("[]", mimetype="application/json")
        upstream = requests.get(
            "https://api.datamuse.com/words",
            params={"rel_syn": word, "max": 20},
            timeout=15,
        )
        if not upstream.ok:
            abort(502, description="Fallback synonym upstream failed")
        return Response(upstream.content, mimetype="application/json")
    
    def _proxy_r2_json(
        path_suffix: str,
        etag: str,
        compressed: bool = True,
        passthrough_gzip: bool = False,
    ):
        """Fetch JSON (optionally gzipped) from R2.

        For large .json.gz files, set passthrough_gzip=True to stream the gz payload
        directly to the client with Content-Encoding: gzip (avoids server OOM).
        """

        r2_url = f"{R2_CDN_BASE}/{path_suffix.lstrip('/')}"
        try:
            upstream = requests.get(
                r2_url,
                timeout=30,
                stream=True,
                headers={"Accept-Encoding": "identity"},
            )
            upstream.raise_for_status()
        except requests.RequestException:
            abort(502, description=f"Failed to fetch {path_suffix} from R2")

        upstream.raw.decode_content = False

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        if passthrough_gzip:
            if not compressed:
                abort(500, description="passthrough_gzip requires compressed=True")
            response = Response(generate(), mimetype="application/json")
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Vary"] = "Accept-Encoding"
        else:
            payload = upstream.content
            upstream.close()
            if compressed:
                try:
                    payload = gzip.decompress(payload)
                except OSError:
                    abort(502, description=f"Unable to decode gzip payload for {path_suffix}")
            response = Response(payload, mimetype="application/json")

        if passthrough_gzip:
            response.headers["Cache-Control"] = "public, max-age=604800"
        else:
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        response.headers["ETag"] = etag
        return response

    @app.route("/api/rhyme-data")
    def rhyme_data():
        return _proxy_r2_json(
            "rhyme/rhyme_data_v3_integrated.json.gz",
            "rhyme-v3-integrated-r2-v2",
            compressed=True,
            passthrough_gzip=True,
        )
    
    @app.route("/api/creative-gens/web-data")
    def creative_gens_web_data():
        """Proxy Creative Gens web display data from R2"""
        return _proxy_r2_json(
            "creative-gems/web_display_data_FULL.json.gz",
            "creative-gens-web-v1",
            compressed=True,
            passthrough_gzip=True,
        )
    
    @app.route("/api/creative-gens/rhymes")
    def creative_gens_rhymes():
        """Proxy Creative Gens rhyme index from R2"""
        return _proxy_r2_json(
            "creative-gems/creative_gens_rhyme_index_FULL.json.gz",
            "creative-gens-rhymes-v2",
            compressed=True,
            passthrough_gzip=True,
        )
    
    @app.route("/api/creative-gens/clusters")
    def creative_gens_clusters():
        """Proxy Creative Gens cluster index from R2"""
        return _proxy_r2_json(
            "creative-gems/creative_gens_cluster_index_FULL.json.gz",
            "creative-gens-clusters-v1",
            compressed=True,
            passthrough_gzip=True,
        )
    
    @app.route("/api/tone-associations")
    def tone_associations():
        """Proxy tone associations from R2"""
        return _proxy_r2_json(
            "metadata/associations_categorized.json.gz",
            "tone-associations-v1",
            compressed=True,
            passthrough_gzip=True,
        )
    
    @app.route("/creative-quotes")
    def creative_quotes():
        """Serve Creative Quotes browser"""
        return send_file(CREATIVE_QUOTES_HTML_PATH)
    
    @app.route("/api/creative-quotes/data")
    def creative_quotes_data():
        """Serve Creative Quotes V6 data from local file"""
        quotes_path = DATA_DIR / "creative_quotes_data_v6.json"
        if not quotes_path.exists():
            abort(404, description="Creative quotes V6 data not found")
        return send_file(quotes_path, mimetype="application/json")
    
    @app.route("/api/creative-quotes/categories-grouped")
    def creative_quotes_categories_grouped():
        """Serve Creative Quotes category groupings (master buckets -> sub-categories)"""
        grouped_path = DATA_DIR / "categories_grouped.json"
        if not grouped_path.exists():
            abort(404, description="Categories grouped data not found")
        return send_file(grouped_path, mimetype="application/json")
    
    @app.route("/Songsmith")
    def songsmith():
        """Serve legacy Songsmith viewer (comprehensive genome viewer)."""
        viewer_path = APP_ROOT / "comprehensive_genome_viewer.html"
        if not viewer_path.exists():
            abort(404, description="Songsmith viewer not found")
        return send_file(viewer_path)
    
    @app.route("/comprehensive-songs")
    def comprehensive_songs():
        """Serve Comprehensive Song Analysis viewer"""
        if not _is_staging_request():
            abort(404)
        comprehensive_html_path = APP_ROOT / "comprehensive_song_viewer.html"
        if not comprehensive_html_path.exists():
            abort(404, description="Comprehensive song viewer not found")
        return send_file(comprehensive_html_path)

    @app.route("/comprehensive-songs-r2")
    def comprehensive_songs_r2():
        """Serve Comprehensive Song Analysis viewer (R2-backed, isolated route)."""
        if not _is_staging_request():
            abort(404)
        comprehensive_html_path = APP_ROOT / "comprehensive_song_viewer_r2.html"
        if not comprehensive_html_path.exists():
            abort(404, description="Comprehensive song viewer (R2) not found")
        return send_file(comprehensive_html_path)

    @app.route("/comprehensive-songs-r2/song/<path:song_id>")
    def comprehensive_songs_r2_song(song_id: str):
        """Serve Comprehensive Song Analysis viewer (R2) with deep-linkable song URL."""
        if not _is_staging_request():
            abort(404)
        comprehensive_html_path = APP_ROOT / "comprehensive_song_viewer_r2.html"
        if not comprehensive_html_path.exists():
            abort(404, description="Comprehensive song viewer (R2) not found")
        return send_file(comprehensive_html_path)

    @app.route("/comprehensive-songs-r2/artist/<artist_slug>")
    def comprehensive_songs_r2_artist(artist_slug: str):
        """Serve Comprehensive Song Analysis viewer (R2) with deep-linkable artist URL."""
        if not _is_staging_request():
            abort(404)
        comprehensive_html_path = APP_ROOT / "comprehensive_song_viewer_r2.html"
        if not comprehensive_html_path.exists():
            abort(404, description="Comprehensive song viewer (R2) not found")
        return send_file(comprehensive_html_path)
    
    @app.route("/api/comprehensive-songs/data")
    def comprehensive_songs_data():
        """Serve comprehensive song analysis data (1K songs with genome + Pattison)"""
        if not _is_staging_request():
            abort(404)
        data_path = APP_ROOT / "comprehensive_1k_songs" / "comprehensive_metadata.json"
        if not data_path.exists():
            abort(404, description="Comprehensive songs data not found")
        return send_file(data_path, mimetype="application/json")
    
    @app.route("/api/comprehensive-songs/artist/<artist_slug>")
    def comprehensive_artist_songs(artist_slug: str):
        """Get all songs by a specific artist"""
        if not _is_staging_request():
            abort(404)
        data_path = APP_ROOT / "comprehensive_1k_songs" / "comprehensive_metadata.json"
        if not data_path.exists():
            abort(404, description="Comprehensive songs data not found")
        
        import json
        with open(data_path, 'r') as f:
            songs = json.load(f)
        
        # Filter songs by artist slug
        artist_songs = [s for s in songs if s.get('artist', '').lower().replace(' ', '-').replace('&', 'and') == artist_slug.lower()]
        
        return jsonify(artist_songs)
    
    @app.route("/api/comprehensive-songs/song/<song_id>")
    def comprehensive_single_song(song_id: str):
        """Get a single song by song_id"""
        if not _is_staging_request():
            abort(404)
        song_file = APP_ROOT / "comprehensive_1k_songs" / "songs" / f"{song_id}.json"
        if not song_file.exists():
            abort(404, description="Song not found")
        return send_file(song_file, mimetype="application/json")
    
    @app.route("/api/rhyme-data-shard/<shard_id>")
    def rhyme_data_shard(shard_id: str):
        """Proxy individual rhyme data shard from R2."""
        if not shard_id or len(shard_id) != 2:
            abort(400, description="Invalid shard_id (must be 2-char hex)")
        
        try:
            int(shard_id, 16)
        except ValueError:
            abort(400, description="Invalid shard_id (must be hex)")
        
        return _proxy_r2_json(
            f"rhyme/v3i_shards_256/{shard_id}.json.gz",
            f"rhyme-shard-v3i-{shard_id}-v2",
            compressed=True,
            passthrough_gzip=True,
        )
    
    @app.route("/api/phonetic-data-shard/<shard_id>")
    def phonetic_data_shard(shard_id: str):
        """Proxy individual phonetic data shard from R2 (lazy-loading)"""
        if not shard_id or len(shard_id) != 2:
            abort(400, description="Invalid shard_id (must be 2-char hex)")
        
        try:
            int(shard_id, 16)
        except ValueError:
            abort(400, description="Invalid shard_id (must be hex)")
        
        return _proxy_r2_json(
            f"phonetics/v1_shards_256/{shard_id}.json.gz",
            f"phonetic-shard-v1-{shard_id}",
            compressed=True,
            passthrough_gzip=True,
        )

    # =========================================================================
    # LLM API Endpoints
    # =========================================================================
    
    @app.route("/dynamic-gens")
    def dynamic_gens():
        """Serve Dynamic Generations page"""
        if DYNAMIC_GENS_HTML_PATH.exists():
            return send_file(DYNAMIC_GENS_HTML_PATH)
        abort(404, description="Dynamic Gens page not yet implemented")
    
    @app.route("/api/llm/resources")
    def llm_resources():
        """List all available data sources for LLM agents."""
        resources = {
            "version": "1.0",
            "description": "Lyric Writing Assistant API for LLM Agents",
            "resources": {
                "phonetics": {
                    "description": "Phonetic analysis with stress patterns and rhyme anchors",
                    "endpoints": [
                        "GET /api/llm/phonetics?word=<word>"
                    ],
                    "capabilities": ["syllable_count", "stress_pattern", "rhyme_anchor"]
                },
                "rhymes": {
                    "description": "Phonetic rhyme lookup with Pattison classification",
                    "endpoints": [
                        "GET /api/llm/rhymes?word=<word>&types=<types>&limit=20"
                    ],
                    "capabilities": ["phonetic_match", "rhyme_classification", "type_filter"]
                },
                "tones": {
                    "description": "500+ tones with rich association clusters",
                    "endpoints": [
                        "GET /api/llm/tones?mood=<mood>&limit=10"
                    ],
                    "capabilities": ["mood_search", "association_browse"]
                },
                "quotes": {
                    "description": "70,000+ quotes with metaphorical transformations",
                    "endpoints": [
                        "GET /api/llm/quotes?theme=<theme>&limit=10"
                    ],
                    "capabilities": ["theme_search", "transformation_variants"]
                },
                "creative_gens": {
                    "description": "25,000+ polished creative writing exercises",
                    "endpoints": [
                        "GET /api/llm/creative-gens?exercise=<type>&limit=10"
                    ],
                    "capabilities": ["exercise_filter", "semantic_search"]
                },
                "generate": {
                    "description": "On-the-fly content generation",
                    "endpoints": [
                        "POST /api/llm/generate"
                    ],
                    "capabilities": ["starter_word", "eccentricity_control", "exercise_selection"]
                },
                "semantic_search": {
                    "description": "Cross-source semantic search",
                    "endpoints": [
                        "GET /api/llm/search?q=<query>&sources=<comma-separated>&limit=20"
                    ],
                    "capabilities": ["embedding_search", "multi_source"]
                }
            }
        }
        return jsonify(resources)
    
    @app.route("/api/llm/search")
    def llm_search():
        """
        Unified semantic search across all sources.
        
        Query params:
            q: Search query (required)
            sources: Comma-separated list of sources (optional)
            limit: Max results (default 20)
        """
        query = (request.args.get("q") or "").strip()
        if not query:
            return jsonify({"error": "Missing required parameter: q"}), 400
        
        sources_param = request.args.get("sources", "")
        sources = [s.strip() for s in sources_param.split(",") if s.strip()] or None
        limit = min(int(request.args.get("limit", 20)), 100)
        
        try:
            from semantic_search import semantic_search, get_embedding_stats
            
            # Check if semantic search is available
            stats = get_embedding_stats()
            if not stats.get("has_sentence_transformers"):
                return jsonify({
                    "error": "Semantic search not available",
                    "reason": "sentence-transformers not installed"
                }), 503
            
            results = semantic_search(query, sources=sources, limit=limit)
            
            return jsonify({
                "success": True,
                "query": {"q": query, "sources": sources, "limit": limit},
                "results": results,
                "metadata": {
                    "returned": len(results),
                    "sources_available": list(stats.get("sources", {}).keys())
                }
            })
        except ImportError:
            return jsonify({
                "error": "Semantic search module not available"
            }), 503
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/llm/phonetics")
    def llm_phonetics():
        """
        Get phonetic data for a word including stress patterns and rhyme anchors.
        
        Query params:
            word: Word to analyze (required)
        """
        word = (request.args.get("word") or "").strip()
        if not word:
            return jsonify({"error": "Missing required parameter: word"}), 400
        
        try:
            from pattison.core.phonetic_engine import PhoneticEngine
            engine = PhoneticEngine()
            
            wp = engine.get_word_phonetics(word)
            if not wp:
                return jsonify({
                    "success": False,
                    "word": word,
                    "error": "No phonetic data available for this word"
                }), 404
            
            return jsonify({
                "success": True,
                "word": word,
                "phonetics": {
                    "phonemes": [p.arpabet for p in wp.phonemes],
                    "syllable_count": wp.syllable_count,
                    "stressed_vowel": wp.stressed_vowel,
                    "onset_consonants": wp.onset_consonants,
                    "post_vowel_consonants": wp.post_vowel_consonants
                },
                "metadata": {
                    "rhyme_anchor": {
                        "vowel": wp.stressed_vowel,
                        "post_consonants": wp.post_vowel_consonants
                    }
                }
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/llm/rhymes")
    def llm_rhymes():
        """
        Find rhymes for a word with phonetic classification.
        
        Query params:
            word: Word to find rhymes for (required)
            types: Comma-separated rhyme types (optional: perfect,family,assonance,consonance,additive,slant)
            limit: Max results (default 20)
        """
        word = (request.args.get("word") or "").strip().lower()
        if not word:
            return jsonify({"error": "Missing required parameter: word"}), 400
        
        types_param = request.args.get("types", "")
        allowed_types = set([t.strip() for t in types_param.split(",") if t.strip()]) or None
        limit = min(int(request.args.get("limit", 20)), 100)
        
        try:
            from pattison.core.phonetic_engine import PhoneticEngine
            from pattison.core.rhyme_classifier import RhymeClassifier
            
            engine = PhoneticEngine()
            classifier = RhymeClassifier(engine)
            
            # Get phonetic data for input word
            wp = engine.get_word_phonetics(word)
            if not wp:
                return jsonify({
                    "success": False,
                    "word": word,
                    "error": "No phonetic data available for input word"
                }), 404
            
            # Load rhyme shard for this word
            import hashlib
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            shard_id = f"{digest[0]:02x}"
            
            # Fetch rhyme data from R2
            r2_url = f"{R2_CDN_BASE}/rhyme/v3i_shards_256/{shard_id}.json.gz"
            try:
                upstream = requests.get(r2_url, timeout=10)
                upstream.raise_for_status()
                rhyme_data = json.loads(gzip.decompress(upstream.content))
            except Exception as e:
                return jsonify({
                    "success": False,
                    "word": word,
                    "error": f"Failed to load rhyme shard: {str(e)}"
                }), 500
            
            if not rhyme_data or word not in rhyme_data:
                return jsonify({
                    "success": True,
                    "word": word,
                    "rhymes": [],
                    "metadata": {"note": "Word not found in rhyme database"}
                })
            
            entry = rhyme_data[word]
            rhyme_candidates = entry.get("rhymes", [])
            
            # Classify and filter rhymes
            results = []
            for candidate in rhyme_candidates[:limit * 3]:  # Get extra for filtering
                if not isinstance(candidate, dict):
                    continue
                
                rhyme_word = candidate.get("word")
                if not rhyme_word:
                    continue
                
                # Classify rhyme
                classification = classifier.classify(word, rhyme_word)
                if not classification:
                    continue
                
                # Filter by type if specified
                if allowed_types and classification.pattison_type not in allowed_types:
                    continue
                
                results.append({
                    "word": rhyme_word,
                    "rhyme_type": classification.pattison_type,
                    "stability": classification.stability,
                    "score": candidate.get("score", 0),
                    "syllables": candidate.get("numSyllables"),
                    "tags": candidate.get("tags", [])
                })
                
                if len(results) >= limit:
                    break
            
            return jsonify({
                "success": True,
                "word": word,
                "phonetics": {
                    "syllables": wp.syllable_count,
                    "stressed_vowel": wp.stressed_vowel,
                    "rhyme_anchor": wp.post_vowel_consonants
                },
                "rhymes": results,
                "metadata": {
                    "total_candidates": len(rhyme_candidates),
                    "returned": len(results),
                    "types_filter": list(allowed_types) if allowed_types else None
                }
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/rhyme-phrases")
    def rhyme_phrases():
        """
        Get phrases that end with words rhyming with the query word.
        
        Query params:
            word: Word to find rhyming phrases for (required)
            limit: Max results per rhyme (default 5)
        """
        word = (request.args.get("word") or "").strip().lower()
        if not word:
            return jsonify({"error": "Missing required parameter: word"}), 400
        
        limit = min(int(request.args.get("limit", 5)), 20)
        
        try:
            from rhyme_phrase_search import search_rhyming_phrases
            results = search_rhyming_phrases(word, limit=limit)
            return jsonify({
                "success": True,
                "query": {"word": word, "limit": limit},
                "results": results["phrases"],
                "metadata": {
                    "total_phrases": results["total"],
                    "rhyme_endings": results["endings"]
                }
            })
        except ImportError as e:
            return jsonify({
                "success": False,
                "error": "Rhyme phrase search module not available",
                "detail": str(e)
            }), 503
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route("/api/rhyme-word-phrases/<word>")
    def rhyme_word_phrases(word):
        """
        Get phrases that end with a specific word.
        Used for expanding rhyme chips to show phrase alts.
        
        This is different from /api/rhyme-phrases which finds phrases
        ending with words that RHYME with the query.
        This endpoint finds phrases ending with the EXACT word.
        
        Path params:
            word: The exact ending word to find phrases for
        Query params:
            limit: Max results (default 10)
        """
        word = (word or "").strip().lower()
        if not word:
            return jsonify({"error": "Missing word parameter"}), 400
        
        limit = min(int(request.args.get("limit", 10)), 50)
        
        try:
            from rhyme_phrase_search import search_phrases_by_ending, get_phrase_count_for_word
            phrases = search_phrases_by_ending(word, limit=limit)
            total = get_phrase_count_for_word(word)
            return jsonify({
                "success": True,
                "word": word,
                "phrases": phrases,
                "count": len(phrases),
                "total_available": total
            })
        except ImportError as e:
            return jsonify({
                "success": False,
                "error": "Rhyme phrase search module not available",
                "detail": str(e)
            }), 503
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route("/api/rhyme-words-phrases", methods=["POST"])
    def rhyme_words_phrases_batch():
        """
        Get phrases for multiple rhyme words at once.
        Used to batch-load phrase alts for all rhyme chips.
        
        POST body:
            words: List of rhyme words
            limit: Max phrases per word (default 5)
        """
        try:
            data = request.get_json() or {}
            words = data.get("words", [])
            limit = min(int(data.get("limit", 5)), 20)
            
            if not words or not isinstance(words, list):
                return jsonify({"error": "Missing or invalid 'words' array"}), 400
            
            from rhyme_phrase_search import get_phrases_for_rhyme_words
            result = get_phrases_for_rhyme_words(words, limit_per_word=limit)
            
            # Count total phrases
            total = sum(len(phrases) for phrases in result.values())
            
            return jsonify({
                "success": True,
                "phrases_by_word": result,
                "words_with_phrases": len(result),
                "total_phrases": total
            })
        except ImportError as e:
            return jsonify({
                "success": False,
                "error": "Rhyme phrase search module not available",
                "detail": str(e)
            }), 503
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route("/api/semantic-rhyme-search")
    def semantic_rhyme_search():
        """
        Semantic search for rhyming phrases matching a concept.
        
        Query params:
            concept: The concept/theme to search for (required)
            rhymes: Comma-separated list of rhyme words to filter by (optional)
            limit: Max results (default 20)
        
        Example: /api/semantic-rhyme-search?concept=heartbreak&rhymes=love,above,dove
        """
        concept = (request.args.get("concept") or "").strip()
        if not concept:
            return jsonify({"error": "Missing required parameter: concept"}), 400
        
        rhymes_str = request.args.get("rhymes", "")
        rhyme_words = [w.strip() for w in rhymes_str.split(",") if w.strip()] if rhymes_str else None
        limit = min(int(request.args.get("limit", 20)), 100)
        
        try:
            from rhyme_phrase_search import semantic_search_rhyming_phrases
            results = semantic_search_rhyming_phrases(
                concept=concept,
                rhyme_words=rhyme_words,
                limit=limit
            )
            return jsonify(results)
        except ImportError as e:
            return jsonify({
                "success": False,
                "error": "Semantic search module not available",
                "detail": str(e)
            }), 503
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route("/api/llm/tones")
    def llm_tones():
        """
        Find tones matching a mood or concept.
        
        Query params:
            mood: Mood/concept to search for (required)
            limit: Max results (default 10)
        """
        mood = (request.args.get("mood") or "").strip()
        if not mood:
            return jsonify({"error": "Missing required parameter: mood"}), 400
        
        limit = min(int(request.args.get("limit", 10)), 50)
        
        return jsonify({
            "success": True,
            "query": {"mood": mood, "limit": limit},
            "note": "Use /api/tone-associations for full tone data. Semantic filtering coming soon.",
            "results": [],
            "metadata": {
                "feature_status": "partial",
                "tone_endpoint": "/api/tone-associations"
            }
        })
    
    @app.route("/api/llm/quotes")
    def llm_quotes():
        """
        Find quotes by theme with transformations.
        
        Query params:
            theme: Theme to search for (required)
            style: Transformation style (original|title|metaphorical|bold)
            limit: Max results (default 10)
        """
        theme = (request.args.get("theme") or "").strip()
        if not theme:
            return jsonify({"error": "Missing required parameter: theme"}), 400
        
        style = request.args.get("style", "all")
        limit = min(int(request.args.get("limit", 10)), 50)
        
        return jsonify({
            "success": True,
            "query": {"theme": theme, "style": style, "limit": limit},
            "note": "Use /api/creative-quotes/data for full quote data. Semantic filtering coming soon.",
            "results": [],
            "metadata": {
                "feature_status": "partial",
                "quotes_endpoint": "/api/creative-quotes/data"
            }
        })
    
    @app.route("/api/llm/generate", methods=["POST"])
    def llm_generate():
        """
        Generate content on-the-fly using Evocative Generator patterns.
        
        JSON body:
            exercise: One of "expanded_titles", "object_characteristics", 
                      "emotional_landscapes", "metaphorical_bridges"
            starter_word: Optional anchor word
            eccentricity: 0.0 (simple) to 1.0 (complex), default 0.5
            count: Number of items to generate (1-20), default 10
        """
        try:
            data = request.get_json() or {}
        except Exception:
            data = {}
        
        starter_word = data.get("starter_word", "")
        exclude_proper_nouns = data.get("exclude_proper_nouns", False)
        
        try:
            from evocative_generator import generate, get_available_exercises
            
            # Always generate 5 per exercise across all 4 types = 20 total
            results = generate(
                starter_word=starter_word,
                count=5,
                all_exercises=True,
                exclude_proper_nouns=exclude_proper_nouns
            )
            
            return jsonify({
                "success": True,
                "query": {
                    "starter_word": starter_word,
                    "exclude_proper_nouns": exclude_proper_nouns
                },
                "results": results,
                "metadata": {
                    "feature_status": "active",
                    "available_exercises": [ex["id"] for ex in get_available_exercises()]
                }
            })
        except ImportError:
            return jsonify({
                "success": False,
                "error": "Evocative Generator module not available",
                "query": {
                    "starter_word": starter_word,
                    "exclude_proper_nouns": exclude_proper_nouns
                },
                "results": [],
                "metadata": {
                    "feature_status": "unavailable"
                }
            }), 503
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "results": []
            }), 500

    @app.route("/api/llm/song-outline", methods=["POST"])
    def llm_song_outline():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("song-outline")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        theme = (data.get("theme") or "").strip()
        if not theme:
            return jsonify({"success": False, "error": "Missing required field: theme"}), 400

        tone = (data.get("tone") or "").strip()
        structure = (data.get("structure") or "verse-chorus-verse-chorus-bridge-chorus").strip()
        rhyme_scheme = data.get("rhyme_scheme") if isinstance(data.get("rhyme_scheme"), dict) else None
        constraints = data.get("constraints") if isinstance(data.get("constraints"), dict) else None

        try:
            from song_generator import generate_song_outline

            result = generate_song_outline(
                theme=theme,
                tone=tone,
                structure=structure,
                rhyme_scheme=rhyme_scheme,
                constraints=constraints,
            )

            if _anthropic_enabled() and isinstance(result, dict) and isinstance(result.get("outline"), dict):
                try:
                    enriched = _anthropic_enrich_outline(theme=theme, tone=tone, structure=structure, outline=result["outline"])
                    if enriched is not None:
                        result["outline"] = enriched
                        meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
                        meta.update({"llm_provider": "anthropic", "llm_model": _anthropic_model()})
                        result["metadata"] = meta
                except Exception:
                    pass

            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/exercises")
    def pattison_exercises_index():
        if not _is_staging_request():
            abort(404)
        try:
            from pattison.exercises.definitions import EXERCISES

            exercises = []
            for ex_id, ex in (EXERCISES or {}).items():
                if not isinstance(ex, dict):
                    continue
                exercises.append({
                    "exercise_id": ex_id,
                    "chapter": ex.get("chapter"),
                    "title": ex.get("title"),
                    "inputs": ex.get("inputs") or [],
                    "writeup": ex.get("writeup") or "",
                    "input_hints": ex.get("input_hints") or {},
                    "input_placeholders": ex.get("input_placeholders") or {},
                    "presets": ex.get("presets") or [],
                })

            exercises.sort(key=lambda x: (int(x.get("chapter") or 9999), str(x.get("exercise_id") or "")))
            return jsonify({"success": True, "exercises": exercises})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/book-exercises")
    def pattison_book_exercises_index():
        if not _is_staging_request():
            abort(404)
        try:
            from pattison.integration.pat_book_exercises import list_book_exercises

            return jsonify({"success": True, "exercises": list_book_exercises(book_path=str(PAT_BOOK_TXT_PATH))})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/book-exercises/<exercise_id>")
    def pattison_book_exercise_get(exercise_id: str):
        if not _is_staging_request():
            abort(404)
        try:
            from pattison.integration.pat_book_exercises import get_book_exercise

            ex = get_book_exercise(book_path=str(PAT_BOOK_TXT_PATH), exercise_id=exercise_id)
            if not ex:
                return jsonify({"success": False, "error": "Unknown exercise_id"}), 404
            return jsonify({"success": True, "exercise": ex})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/analysis-report", methods=["POST"])
    def pattison_analysis_report():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-analysis-report")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        lyrics = data.get("lyrics")
        lines = data.get("lines")
        if lines is None and lyrics is None:
            return jsonify({"success": False, "error": "Provide either 'lines' (array) or 'lyrics' (string)"}), 400

        include_consonance = bool(data.get("include_consonance_in_scheme") or False)

        try:
            from pattison.reports.analysis_report import generate_analysis_report

            result = generate_analysis_report(
                lyrics=lyrics if isinstance(lyrics, str) else None,
                lines=lines if isinstance(lines, list) else None,
                cmu_path=(os.getenv("CMU_DICT_PATH") or None),
                jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
                include_consonance_in_scheme=include_consonance,
            )
            status = 200 if result.get("success") else 400
            return jsonify(result), status
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/instruction-package", methods=["POST"])
    def pattison_instruction_package():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-instruction-package")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        concept = (data.get("concept") or "").strip()
        if not concept:
            return jsonify({"success": False, "error": "Missing required field: concept"}), 400

        emotional_arc = (data.get("emotional_arc") or "").strip()
        structure = (data.get("structure") or "verse-chorus-verse-chorus-bridge-chorus").strip()
        stability_goal = (data.get("stability_goal") or "balanced").strip()
        include_rhyme_suggestions = bool(data.get("include_rhyme_suggestions") if "include_rhyme_suggestions" in data else True)
        rhyme_seed = (data.get("rhyme_seed") or "").strip()
        try:
            min_sophistication_score = float(data.get("min_sophistication_score", 0.7))
        except Exception:
            min_sophistication_score = 0.7

        try:
            from pattison.generator.llm_instruction_generator import generate_instruction_package

            result = generate_instruction_package(
                concept=concept,
                emotional_arc=emotional_arc,
                structure=structure,
                stability_goal=stability_goal,
                rhyme_seed=rhyme_seed,
                include_rhyme_suggestions=include_rhyme_suggestions,
                jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
                pat_db_path=(os.getenv("PAT_RHYME_DB_PATH") or None),
                cmu_path=(os.getenv("CMU_DICT_PATH") or None),
                min_sophistication_score=min_sophistication_score,
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/exercise/<exercise_id>", methods=["POST"])
    def pattison_exercise(exercise_id: str):
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-exercise")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        action = (data.get("action") or "describe").strip().lower()
        if action not in {"describe", "solve", "validate"}:
            return jsonify({"success": False, "error": "Invalid field: action"}), 400

        try:
            from pattison.exercises.solver import describe_exercise, solve_exercise, validate_exercise

            cmu_path = (os.getenv("CMU_DICT_PATH") or None)
            jon_db = (os.getenv("JONATHAN_RHYME_DB_PATH") or None)

            if action == "describe":
                return jsonify(describe_exercise(exercise_id))
            if action == "solve":
                return jsonify(solve_exercise(exercise_id, payload=data, cmu_path=cmu_path, jonathan_db_path=jon_db))
            return jsonify(validate_exercise(exercise_id, payload=data, cmu_path=cmu_path, jonathan_db_path=jon_db))
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/llm/song-draft", methods=["POST"])
    def llm_song_draft():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("song-draft")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        theme = (data.get("theme") or "").strip()
        tone = (data.get("tone") or "").strip()
        structure = (data.get("structure") or "verse-chorus-verse-chorus-bridge-chorus").strip()
        use_pattison_pkg = bool(data.get("use_pattison_instruction_package") or False)
        stability_goal = (data.get("stability_goal") or "balanced").strip()
        emotional_arc = (data.get("emotional_arc") or "").strip() or tone

        outline = data.get("outline")
        if outline is not None and not isinstance(outline, dict):
            return jsonify({"success": False, "error": "Invalid field: outline (must be object)"}), 400

        try:
            from song_generator import generate_song_outline, draft_from_outline

            if outline is None:
                if not theme:
                    return jsonify({"success": False, "error": "Missing required field: theme (or provide outline)"}), 400

                outline_result = generate_song_outline(
                    theme=theme,
                    tone=tone,
                    structure=structure,
                    rhyme_scheme=(data.get("rhyme_scheme") if isinstance(data.get("rhyme_scheme"), dict) else None),
                    constraints=(data.get("constraints") if isinstance(data.get("constraints"), dict) else None),
                )
                if not outline_result.get("success"):
                    return jsonify(outline_result), 500
                outline = outline_result.get("outline") or {}

            llm_lyrics = None
            pattison_pkg = None
            if use_pattison_pkg and theme:
                try:
                    from pattison.generator.llm_instruction_generator import generate_instruction_package

                    pattison_pkg = generate_instruction_package(
                        concept=theme,
                        emotional_arc=emotional_arc,
                        structure=structure,
                        stability_goal=stability_goal,
                        rhyme_seed=(data.get("rhyme_seed") or ""),
                        include_rhyme_suggestions=bool(data.get("include_rhyme_suggestions") if "include_rhyme_suggestions" in data else True),
                        jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
                        pat_db_path=(os.getenv("PAT_RHYME_DB_PATH") or None),
                        cmu_path=(os.getenv("CMU_DICT_PATH") or None),
                        min_sophistication_score=float(data.get("min_sophistication_score", 0.7) or 0.7),
                    )
                    if not isinstance(pattison_pkg, dict) or not pattison_pkg.get("success"):
                        pattison_pkg = None
                except Exception:
                    pattison_pkg = None

            if _anthropic_enabled() and isinstance(outline, dict) and outline:
                try:
                    if pattison_pkg and isinstance(pattison_pkg.get("formatted_prompt"), str) and pattison_pkg.get("formatted_prompt"):
                        system = "You are an expert songwriter. Return ONLY the lyrics text (no JSON, no markdown)."
                        user = pattison_pkg.get("formatted_prompt") + "\n\nReturn ONLY the lyrics text. Use section headers as shown."
                        llm_lyrics = _anthropic_messages(system=system, user=user, max_tokens=1800, temperature=0.8)
                    else:
                        llm_lyrics = _anthropic_generate_lyrics(theme=theme, tone=tone, structure=structure, outline=outline)
                except Exception:
                    llm_lyrics = None

            if llm_lyrics:
                draft = {"success": True, "lyrics": llm_lyrics, "metadata": {"llm_provider": "anthropic", "llm_model": _anthropic_model()}}
            else:
                draft = draft_from_outline(outline=outline, theme=theme, tone=tone)
                if not draft.get("success"):
                    return jsonify(draft), 500

            return jsonify({
                "success": True,
                "outline": outline,
                "lyrics": draft.get("lyrics", ""),
                "metadata": {
                    "theme": theme,
                    "tone": tone,
                    "structure": structure,
                    **({"pattison_instruction_package": pattison_pkg} if pattison_pkg else {}),
                    **(draft.get("metadata") or {}),
                },
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/analyze", methods=["POST"])
    def pattison_analyze():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-analyze")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        lines = data.get("lines")
        lyrics = data.get("lyrics")
        if lines is None and lyrics is None:
            return jsonify({"success": False, "error": "Provide either 'lines' (array) or 'lyrics' (string)"}), 400

        if lines is not None and not isinstance(lines, list):
            return jsonify({"success": False, "error": "Invalid field: lines (must be array)"}), 400
        if lyrics is not None and not isinstance(lyrics, str):
            return jsonify({"success": False, "error": "Invalid field: lyrics (must be string)"}), 400

        include_consonance = bool(data.get("include_consonance_in_scheme") or False)

        try:
            from pattison.reports.analysis_report import split_sections_from_lines, split_sections_from_lyrics
            from pattison.structure.analyzer import analyze_section

            cmu_path = (os.getenv("CMU_DICT_PATH") or None)
            jon_db = (os.getenv("JONATHAN_RHYME_DB_PATH") or None)

            if lyrics is not None and isinstance(lyrics, str):
                sections = split_sections_from_lyrics(lyrics)
            else:
                sections = split_sections_from_lines([l for l in (lines or []) if isinstance(l, str)])

            # Detect if the input actually contains bracket headers.
            has_headers = False
            if lyrics is not None and isinstance(lyrics, str):
                has_headers = any((ln or "").strip().startswith("[") and (ln or "").strip().endswith("]") for ln in lyrics.splitlines())
            elif isinstance(lines, list):
                has_headers = any(isinstance(ln, str) and ln.strip().startswith("[") and ln.strip().endswith("]") for ln in lines)

            if not has_headers:
                # Preserve the existing response shape.
                flat_lines = sections[0][1] if sections else []
                result = analyze_section(
                    flat_lines,
                    cmu_path=cmu_path,
                    jonathan_db_path=jon_db,
                    include_consonance_in_scheme=include_consonance,
                )
                return jsonify(result)

            out_sections = []
            stabilities: List[float] = []
            for name, sec_lines in sections:
                res = analyze_section(
                    sec_lines,
                    cmu_path=cmu_path,
                    jonathan_db_path=jon_db,
                    include_consonance_in_scheme=include_consonance,
                )
                out_sections.append({"name": name, "analysis": res})
                try:
                    stabilities.append(float(res.get("stability") or 0.0))
                except Exception:
                    stabilities.append(0.0)

            avg = sum(stabilities) / len(stabilities) if stabilities else 0.0
            return jsonify({"success": True, "sections": out_sections, "overall": {"average_stability": avg}})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/rhyme-ladder", methods=["GET"])
    def pattison_rhyme_ladder():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-rhyme-ladder")
        if limited is not None:
            return limited

        word = (request.args.get("word") or "").strip().lower()
        if not word:
            return jsonify({"success": False, "error": "Missing required parameter: word"}), 400

        include_phrases = (request.args.get("include_phrases") or "true").strip().lower() not in {"0", "false", "no"}
        exclude_banned_pairs = (request.args.get("exclude_banned_pairs") or "true").strip().lower() not in {"0", "false", "no"}
        include_pat = (request.args.get("include_pat") or "true").strip().lower() not in {"0", "false", "no"}
        try:
            min_sophistication_score = float(request.args.get("min_sophistication_score", 0.7))
        except Exception:
            min_sophistication_score = 0.7
        try:
            limit = min(int(request.args.get("limit", 60)), 200)
        except Exception:
            limit = 60

        try:
            from pattison.integration.rhyme_service import get_rhymes

            rh = get_rhymes(
                word,
                rhyme_type="any",
                limit=limit,
                include_phrases=include_phrases,
                min_sophistication_score=min_sophistication_score,
                exclude_banned_pairs=exclude_banned_pairs,
                include_pat=include_pat,
                jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
                pat_db_path=(os.getenv("PAT_RHYME_DB_PATH") or None),
                cmu_path=(os.getenv("CMU_DICT_PATH") or None),
            )
            results = rh.get("results") if isinstance(rh, dict) else None
            if not isinstance(results, list):
                results = []

            buckets = {
                "perfect": [],
                "family": [],
                "additive": [],
                "subtractive": [],
                "assonance": [],
                "consonance": [],
            }

            for r in results:
                if not isinstance(r, dict):
                    continue
                t = (r.get("pattison_type") or "").strip().lower()
                if t in buckets:
                    buckets[t].append(r)

            counts = {k: len(v) for k, v in buckets.items()}
            total = sum(counts.values())
            return jsonify({"success": True, "word": word, "results_by_type": buckets, "counts": counts, "count": total})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/get-rhymes", methods=["GET"])
    def pattison_get_rhymes():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-get-rhymes")
        if limited is not None:
            return limited

        word = (request.args.get("word") or "").strip().lower()
        if not word:
            return jsonify({"success": False, "error": "Missing required parameter: word"}), 400

        rhyme_type = (request.args.get("rhyme_type") or "any").strip().lower()
        include_phrases = (request.args.get("include_phrases") or "true").strip().lower() not in {"0", "false", "no"}
        exclude_banned_pairs = (request.args.get("exclude_banned_pairs") or "true").strip().lower() not in {"0", "false", "no"}
        include_pat = (request.args.get("include_pat") or "true").strip().lower() not in {"0", "false", "no"}
        try:
            min_sophistication_score = float(request.args.get("min_sophistication_score", 0.7))
        except Exception:
            min_sophistication_score = 0.7
        try:
            limit = min(int(request.args.get("limit", 10)), 50)
        except Exception:
            limit = 10

        try:
            from pattison.integration.rhyme_service import get_rhymes

            result = get_rhymes(
                word,
                rhyme_type=rhyme_type,
                limit=limit,
                include_phrases=include_phrases,
                min_sophistication_score=min_sophistication_score,
                exclude_banned_pairs=exclude_banned_pairs,
                include_pat=include_pat,
                jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
                pat_db_path=(os.getenv("PAT_RHYME_DB_PATH") or None),
                cmu_path=(os.getenv("CMU_DICT_PATH") or None),
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/template", methods=["POST"])
    def pattison_template():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-template")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        concept = (data.get("concept") or "").strip()
        if not concept:
            return jsonify({"success": False, "error": "Missing required field: concept"}), 400

        emotional_arc = (data.get("emotional_arc") or "").strip()
        structure = (data.get("structure") or "verse-chorus-verse-chorus-bridge-chorus").strip()
        stability_goal = (data.get("stability_goal") or "balanced").strip()

        include_rhyme_suggestions = bool(data.get("include_rhyme_suggestions") or False)
        try:
            rhyme_seed = (data.get("rhyme_seed") or "").strip().lower()
        except Exception:
            rhyme_seed = ""
        if include_rhyme_suggestions and not rhyme_seed:
            rhyme_seed = concept.split()[-1].strip().lower() if concept.split() else ""

        try:
            from pattison.generator.template_generator import generate_template

            end_word_options_by_label = None
            if include_rhyme_suggestions and rhyme_seed:
                try:
                    from pattison.integration.rhyme_service import get_rhymes

                    rh = get_rhymes(
                        rhyme_seed,
                        rhyme_type="any",
                        limit=12,
                        include_phrases=True,
                        jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
                        pat_db_path=(os.getenv("PAT_RHYME_DB_PATH") or None),
                        cmu_path=(os.getenv("CMU_DICT_PATH") or None),
                    )
                    results = rh.get("results") if isinstance(rh, dict) else None
                    if isinstance(results, list):
                        words = [str(r.get("word") or "").strip() for r in results if isinstance(r, dict)]
                        words = [w for w in words if w]
                        end_word_options_by_label = {"A": words[:10], "B": words[:10], "C": words[:10]}
                except Exception:
                    end_word_options_by_label = None

            result = generate_template(
                concept=concept,
                emotional_arc=emotional_arc,
                structure=structure,
                stability_goal=stability_goal,
                end_word_options_by_label=end_word_options_by_label,
            )
            if isinstance(result, dict) and result.get("success") and include_rhyme_suggestions:
                meta = result.get("template") if isinstance(result.get("template"), dict) else {}
                meta["rhyme_seed"] = rhyme_seed
                meta["include_rhyme_suggestions"] = True
                result["template"] = meta
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/llm/critique", methods=["POST"])
    def llm_critique():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("critique")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        lyrics = data.get("lyrics")
        if not isinstance(lyrics, str) or not lyrics.strip():
            return jsonify({"success": False, "error": "Missing required field: lyrics"}), 400

        focus_areas = data.get("focus_areas")
        if focus_areas is not None and not isinstance(focus_areas, list):
            return jsonify({"success": False, "error": "Invalid field: focus_areas (must be array)"}), 400

        try:
            if _anthropic_enabled():
                try:
                    result = _anthropic_critique(lyrics=lyrics, focus_areas=focus_areas)
                    if isinstance(result, dict) and result.get("success"):
                        meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
                        meta.update({"llm_provider": "anthropic", "llm_model": _anthropic_model()})
                        result["metadata"] = meta
                        return jsonify(result)
                except Exception:
                    pass

            from critique_engine import critique_lyrics

            result = critique_lyrics(lyrics=lyrics, focus_areas=focus_areas)
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/stress-count", methods=["POST"])
    def pattison_stress_count():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-stress-count")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        line = data.get("line")
        if not isinstance(line, str) or not line.strip():
            return jsonify({"success": False, "error": "Missing required field: line"}), 400

        try:
            from pattison.core.phonetic_engine import PhoneticEngine

            engine = PhoneticEngine(
                cmu_path=(os.getenv("CMU_DICT_PATH") or None),
                jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
            )
            count = engine.count_line_primary_stresses(line)
            return jsonify({
                "success": True,
                "line": line,
                "primary_stress_count": count,
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pattison/classify-rhyme", methods=["POST"])
    def pattison_classify_rhyme():
        if not _is_staging_request():
            abort(404)

        limited = _enforce_agentic_rate_limit("pattison-classify-rhyme")
        if limited is not None:
            return limited

        try:
            data = request.get_json() or {}
        except Exception:
            data = {}

        word1 = data.get("word1")
        word2 = data.get("word2")
        if not isinstance(word1, str) or not word1.strip():
            return jsonify({"success": False, "error": "Missing required field: word1"}), 400
        if not isinstance(word2, str) or not word2.strip():
            return jsonify({"success": False, "error": "Missing required field: word2"}), 400

        try:
            from pattison.core.phonetic_engine import PhoneticEngine
            from pattison.core.rhyme_classifier import RhymeClassifier

            engine = PhoneticEngine(
                cmu_path=(os.getenv("CMU_DICT_PATH") or None),
                jonathan_db_path=(os.getenv("JONATHAN_RHYME_DB_PATH") or None),
            )
            classifier = RhymeClassifier(engine)
            res = classifier.classify(word1, word2)
            return jsonify({
                "success": True,
                "word1": word1,
                "word2": word2,
                "pattison_type": res.pattison_type.value,
                "pattison_stability": res.pattison_stability,
                "explanation": res.explanation,
                "details": {
                    "vowel1": res.vowel1,
                    "vowel2": res.vowel2,
                    "post1": res.post1 or [],
                    "post2": res.post2 or [],
                },
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/llm/embedding-stats")
    def llm_embedding_stats():
        """Get statistics about available embeddings."""
        try:
            from semantic_search import get_embedding_stats
            stats = get_embedding_stats()
            return jsonify(stats)
        except ImportError:
            return jsonify({
                "error": "Semantic search module not available",
                "has_sentence_transformers": False,
                "has_faiss": False
            })

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
