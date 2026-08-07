import json
from datetime import datetime, timezone
import xxhash
import numpy as np
from typing import Dict, Any, Optional, Tuple, Union
from urllib.parse import urlparse

from browser_optimizer.config.settings import get_settings
from browser_optimizer.cache.db import get_db_connection
from browser_optimizer.cache.embedding import StructuralEmbedding
from browser_optimizer.schemas.schemas import CompressedContext
from browser_optimizer.utils.logger import logger


class SemanticCache:
    """
    Two-Tier Semantic Caching Subsystem.
    - Tier 1: Sub-millisecond 64-bit xxhash exact string matching.
    - Tier 2: 68-dimensional L2-normalized structural DOM vector embedding with Cosine Similarity matching (>= 0.90).
    - Dynamic Confidence Auto-Decay: Reward (+0.05) on success, Penalty (-0.30) on failure.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.settings = get_settings()
        self.db_path = db_path or self.settings.SQLITE_DB_PATH

    def _generate_hash(self, html: str) -> str:
        """
        Generates 64-bit xxhash hex string of raw HTML.
        """
        return xxhash.xxh64(html.encode("utf-8")).hexdigest()

    def set(
        self,
        url: str,
        html: str,
        compressed_context: Union[CompressedContext, Dict[str, Any]],
        page_type: str = "unknown",
        confidence: float = 1.0
    ) -> str:
        """
        Stores DOM compressed context, 68-D structural vector embedding, and metadata in SQLite cache table.
        Returns generated xxhash key.
        """
        if not self.settings.CACHE_ENABLED:
            return ""

        key = self._generate_hash(html)
        embedding = StructuralEmbedding.generate(html)
        vector_blob = embedding.tobytes()

        if isinstance(compressed_context, CompressedContext):
            context_json = compressed_context.model_dump_json(exclude_none=True)
        elif isinstance(compressed_context, dict):
            context_json = json.dumps(compressed_context)
        else:
            context_json = str(compressed_context)

        now = datetime.now(timezone.utc).isoformat()

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cache (xxhash, url, vector_blob, compressed_context_json, page_type, confidence, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(xxhash) DO UPDATE SET
                    url = excluded.url,
                    vector_blob = excluded.vector_blob,
                    compressed_context_json = excluded.compressed_context_json,
                    page_type = excluded.page_type,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at
            """, (key, url, vector_blob, context_json, page_type, confidence, now))
            conn.commit()

        logger.info(f"Cached context for '{url}' with xxhash key: {key} (confidence={confidence:.2f})")
        return key

    def get(self, url: str, html: str) -> Tuple[Optional[CompressedContext], bool, float]:
        """
        Retrieves compressed context from cache.
        Returns Tuple of (CompressedContext or None, is_semantic_match: bool, similarity_or_confidence: float).
        """
        if not self.settings.CACHE_ENABLED:
            return None, False, 0.0

        key = self._generate_hash(html)

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            # Tier 1: Exact Hash Match (<1ms)
            cursor.execute("SELECT compressed_context_json, confidence FROM cache WHERE xxhash = ?", (key,))
            row = cursor.fetchone()
            if row:
                confidence = row["confidence"]
                if confidence >= 0.30:
                    logger.info(f"Tier 1 Cache Hit (Exact xxhash match) for '{url}' (confidence={confidence:.2f})")
                    try:
                        ctx_dict = json.loads(row["compressed_context_json"])
                        ctx_model = CompressedContext.model_validate(ctx_dict)
                        return ctx_model, False, confidence
                    except Exception as e:
                        logger.error(f"Error parsing cached context JSON for '{key}': {e}")

            # Tier 2: Semantic Similarity Match (68-D Structural Embedding)
            query_embedding = StructuralEmbedding.generate(html)
            
            # Match against cached entries for same domain or all entries
            domain = urlparse(url).netloc
            cursor.execute("SELECT xxhash, url, vector_blob, compressed_context_json, confidence FROM cache")
            rows = cursor.fetchall()

            best_match_row = None
            max_similarity = 0.0

            for r in rows:
                if r["confidence"] < 0.30:
                    continue
                cached_vector = np.frombuffer(r["vector_blob"], dtype=np.float64)
                if len(cached_vector) == 68:
                    sim = StructuralEmbedding.cosine_similarity(query_embedding, cached_vector)
                    if sim > max_similarity:
                        max_similarity = sim
                        best_match_row = r

            if max_similarity >= self.settings.SIMILARITY_THRESHOLD and best_match_row:
                logger.info(
                    f"Tier 2 Cache Hit (Semantic Cosine Match = {max_similarity:.3f} >= {self.settings.SIMILARITY_THRESHOLD}) "
                    f"for '{url}' matching cached URL '{best_match_row['url']}'"
                )
                try:
                    ctx_dict = json.loads(best_match_row["compressed_context_json"])
                    ctx_model = CompressedContext.model_validate(ctx_dict)
                    return ctx_model, True, max_similarity
                except Exception as e:
                    logger.error(f"Error parsing semantic match context JSON: {e}")

        logger.info(f"Cache Miss for '{url}'")
        return None, False, 0.0

    def update_confidence(self, html: str, success: bool) -> float:
        """
        Updates dynamic confidence score for a cached entry.
        Applies Reward (+0.05) on success, Penalty (-0.30) on failure.
        Returns updated confidence score.
        """
        key = self._generate_hash(html)
        delta = 0.05 if success else -0.30

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT confidence FROM cache WHERE xxhash = ?", (key,))
            row = cursor.fetchone()
            if row:
                current_conf = row["confidence"]
                new_conf = round(max(0.0, min(1.0, current_conf + delta)), 2)
                cursor.execute("UPDATE cache SET confidence = ? WHERE xxhash = ?", (new_conf, key))
                conn.commit()
                logger.info(f"Updated cache confidence for xxhash {key}: {current_conf:.2f} -> {new_conf:.2f}")
                return new_conf
        return 0.0
