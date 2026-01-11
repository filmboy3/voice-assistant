"""
Semantic Search Module

Provides embedding-based semantic search capabilities for the lyric writing app.
Supports:
- Semantic sub-filtering of rhyme results
- Cross-source semantic search
- LLM API integration
"""

import os
import json
import gzip
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

# Try to import optional dependencies
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

# Configuration
EMBEDDING_MODEL = "all-mpnet-base-v2"
EMBEDDING_DIM = 768

# Paths - check for external volume first, fall back to local
EXTERNAL_VOLUME = Path("/Volumes/Jonathan")
if EXTERNAL_VOLUME.exists():
    EMBEDDINGS_DIR = EXTERNAL_VOLUME / "AI_DATA" / "unified_embeddings"
    PRE_GEN_DIR = EXTERNAL_VOLUME / "Pre_Gen"
else:
    # Fallback for Heroku (would need R2 integration)
    EMBEDDINGS_DIR = Path(__file__).parent / "data" / "embeddings"
    PRE_GEN_DIR = Path(__file__).parent / "data"

# Cached resources
_model = None
_embeddings_cache = {}
_faiss_indices = {}
_metadata_cache = {}


def get_model():
    """Get or load the embedding model."""
    global _model
    if _model is None:
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError("sentence-transformers not installed")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_text(text: str) -> np.ndarray:
    """Embed a single text string."""
    model = get_model()
    embedding = model.encode([text], convert_to_numpy=True)[0]
    return embedding


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed multiple texts."""
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def cosine_similarity_batch(query: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and multiple candidates."""
    # Normalize
    query_norm = query / (np.linalg.norm(query) + 1e-9)
    cand_norms = candidates / (np.linalg.norm(candidates, axis=1, keepdims=True) + 1e-9)
    # Dot product
    similarities = np.dot(cand_norms, query_norm)
    return similarities


def load_embeddings_shard(source: str, shard: int = 0) -> Tuple[np.ndarray, List[Dict]]:
    """Load embeddings and metadata for a source shard."""
    cache_key = f"{source}_{shard}"
    
    if cache_key in _embeddings_cache:
        return _embeddings_cache[cache_key], _metadata_cache[cache_key]
    
    shards_dir = EMBEDDINGS_DIR / "shards"
    
    emb_path = shards_dir / f"{source}_{shard:02d}.npy"
    meta_path = shards_dir / f"{source}_{shard:02d}.json"
    
    if not emb_path.exists() or not meta_path.exists():
        return np.array([]), []
    
    embeddings = np.load(emb_path)
    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    items = metadata.get("items", [])
    
    _embeddings_cache[cache_key] = embeddings
    _metadata_cache[cache_key] = items
    
    return embeddings, items


def load_all_embeddings(source: str) -> Tuple[np.ndarray, List[Dict]]:
    """Load all embeddings for a source (all shards)."""
    all_embeddings = []
    all_items = []
    
    shard = 0
    while True:
        embeddings, items = load_embeddings_shard(source, shard)
        if len(embeddings) == 0:
            break
        all_embeddings.append(embeddings)
        all_items.extend(items)
        shard += 1
    
    if not all_embeddings:
        return np.array([]), []
    
    return np.vstack(all_embeddings), all_items


def load_creative_gens_embeddings() -> Tuple[np.ndarray, List[Dict]]:
    """Load pre-existing Creative Gens embeddings from Pre_Gen."""
    cache_key = "creative_gens_pregen"
    
    if cache_key in _embeddings_cache:
        return _embeddings_cache[cache_key], _metadata_cache[cache_key]
    
    emb_path = PRE_GEN_DIR / "polished_embeddings.npy"
    meta_path = PRE_GEN_DIR / "polished_metadata.json"
    
    if not emb_path.exists() or not meta_path.exists():
        return np.array([]), []
    
    embeddings = np.load(emb_path)
    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    items = metadata.get("items", [])
    
    _embeddings_cache[cache_key] = embeddings
    _metadata_cache[cache_key] = items
    
    return embeddings, items


def get_faiss_index(source: str):
    """Get or load a FAISS index for a source."""
    if not HAS_FAISS:
        return None
    
    if source in _faiss_indices:
        return _faiss_indices[source]
    
    index_path = EMBEDDINGS_DIR / "faiss_indices" / f"{source}.faiss"
    
    if not index_path.exists():
        return None
    
    index = faiss.read_index(str(index_path))
    _faiss_indices[source] = index
    return index


def semantic_search(
    query: str,
    sources: List[str] = None,
    limit: int = 20,
    min_score: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Perform semantic search across specified sources.
    
    Args:
        query: The search query text
        sources: List of sources to search (e.g., ["rhyme_phrases", "quotes"])
                 If None, searches all available sources
        limit: Maximum number of results to return
        min_score: Minimum similarity score threshold
    
    Returns:
        List of results with text, score, source, and metadata
    """
    if sources is None:
        sources = ["rhyme_phrases", "quotes", "tones", "idioms", "creative_gens"]
    
    # Embed the query
    query_embedding = embed_text(query)
    
    all_results = []
    
    for source in sources:
        if source == "creative_gens":
            embeddings, items = load_creative_gens_embeddings()
        else:
            embeddings, items = load_all_embeddings(source)
        
        if len(embeddings) == 0:
            continue
        
        # Compute similarities
        similarities = cosine_similarity_batch(query_embedding, embeddings)
        
        # Get top results for this source
        top_indices = np.argsort(similarities)[::-1][:limit * 2]  # Get extra for filtering
        
        for idx in top_indices:
            score = float(similarities[idx])
            if score < min_score:
                continue
            
            item = items[idx]
            all_results.append({
                "text": item.get("text", ""),
                "score": score,
                "source": source,
                "id": item.get("id", ""),
                "metadata": item.get("metadata", {})
            })
    
    # Sort all results by score and limit
    all_results.sort(key=lambda x: -x["score"])
    return all_results[:limit]


def filter_rhymes_by_concept(
    rhyme_texts: List[str],
    concept: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Filter a list of rhyme texts by semantic similarity to a concept.
    
    This is the core function for semantic sub-filtering:
    1. User searches for rhymes of "time"
    2. Gets pool of rhyming words/phrases
    3. Filters by concept "place" to find place-related rhymes
    
    Args:
        rhyme_texts: List of rhyme words or phrases to filter
        concept: The concept to filter by
        limit: Maximum number of results
    
    Returns:
        List of filtered rhymes with similarity scores
    """
    if not rhyme_texts:
        return []
    
    # Embed the concept
    concept_embedding = embed_text(concept)
    
    # Embed all rhyme texts
    rhyme_embeddings = embed_texts(rhyme_texts)
    
    # Compute similarities
    similarities = cosine_similarity_batch(concept_embedding, rhyme_embeddings)
    
    # Rank and return
    results = []
    for i, (text, score) in enumerate(zip(rhyme_texts, similarities)):
        results.append({
            "text": text,
            "score": float(score),
            "rank": i
        })
    
    results.sort(key=lambda x: -x["score"])
    
    # Update ranks after sorting
    for i, r in enumerate(results):
        r["rank"] = i
    
    return results[:limit]


def find_similar_to_text(
    text: str,
    source: str = None,
    limit: int = 10,
    exclude_self: bool = True
) -> List[Dict[str, Any]]:
    """
    Find items similar to a given text.
    
    Args:
        text: The text to find similar items for
        source: Specific source to search, or None for all
        limit: Maximum results
        exclude_self: Whether to exclude exact matches
    
    Returns:
        List of similar items with scores
    """
    results = semantic_search(
        query=text,
        sources=[source] if source else None,
        limit=limit + (1 if exclude_self else 0)
    )
    
    if exclude_self:
        # Remove exact match if present
        results = [r for r in results if r["text"].lower() != text.lower()]
    
    return results[:limit]


def get_embedding_stats() -> Dict[str, Any]:
    """Get statistics about available embeddings."""
    stats = {
        "has_sentence_transformers": HAS_SENTENCE_TRANSFORMERS,
        "has_faiss": HAS_FAISS,
        "embeddings_dir": str(EMBEDDINGS_DIR),
        "embeddings_dir_exists": EMBEDDINGS_DIR.exists(),
        "sources": {}
    }
    
    if EMBEDDINGS_DIR.exists():
        shards_dir = EMBEDDINGS_DIR / "shards"
        if shards_dir.exists():
            for meta_path in shards_dir.glob("*.json"):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    source = meta.get("source", "unknown")
                    count = meta.get("count", 0)
                    
                    if source not in stats["sources"]:
                        stats["sources"][source] = {"total": 0, "shards": 0}
                    
                    stats["sources"][source]["total"] += count
                    stats["sources"][source]["shards"] += 1
                except Exception:
                    pass
    
    # Check for Creative Gens embeddings
    if PRE_GEN_DIR.exists():
        emb_path = PRE_GEN_DIR / "polished_embeddings.npy"
        if emb_path.exists():
            try:
                emb = np.load(emb_path)
                stats["sources"]["creative_gens"] = {
                    "total": emb.shape[0],
                    "shards": 1,
                    "location": "pre_gen"
                }
            except Exception:
                pass
    
    return stats


# Simple in-memory embedding cache for runtime use
class RuntimeEmbeddingCache:
    """
    Lightweight embedding cache for runtime semantic operations.
    Useful when full FAISS indices aren't available (e.g., on Heroku).
    """
    
    def __init__(self, max_items: int = 10000):
        self.max_items = max_items
        self.texts = []
        self.embeddings = None
        self.metadata = []
    
    def add(self, text: str, metadata: Dict = None):
        """Add a text to the cache."""
        if len(self.texts) >= self.max_items:
            # Remove oldest
            self.texts.pop(0)
            self.metadata.pop(0)
            if self.embeddings is not None:
                self.embeddings = self.embeddings[1:]
        
        self.texts.append(text)
        self.metadata.append(metadata or {})
        self.embeddings = None  # Invalidate embeddings
    
    def add_batch(self, texts: List[str], metadata_list: List[Dict] = None):
        """Add multiple texts to the cache."""
        if metadata_list is None:
            metadata_list = [{}] * len(texts)
        
        for text, meta in zip(texts, metadata_list):
            self.add(text, meta)
    
    def ensure_embeddings(self):
        """Ensure embeddings are computed."""
        if self.embeddings is None and self.texts:
            self.embeddings = embed_texts(self.texts)
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search the cache."""
        if not self.texts:
            return []
        
        self.ensure_embeddings()
        
        query_emb = embed_text(query)
        similarities = cosine_similarity_batch(query_emb, self.embeddings)
        
        results = []
        top_indices = np.argsort(similarities)[::-1][:limit]
        
        for idx in top_indices:
            results.append({
                "text": self.texts[idx],
                "score": float(similarities[idx]),
                "metadata": self.metadata[idx]
            })
        
        return results
    
    def clear(self):
        """Clear the cache."""
        self.texts = []
        self.embeddings = None
        self.metadata = []
