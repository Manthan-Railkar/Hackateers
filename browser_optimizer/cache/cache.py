import json
import time
from datetime import datetime
import xxhash
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from browser_optimizer.config.settings import get_settings
from browser_optimizer.cache.db import get_db_connection
from browser_optimizer.cache.embedding import StructuralEmbedding
from browser_optimizer.utils.logger import logger

class SemanticCache:
    def __init__(self, db_path: Optional[str] = None):
        self.settings = get_settings()
        self.db_path = db_path or self.settings.SQLITE_DB_PATH

    def _generate_hash(self, html: str) -> str:
        return xxhash.xxh64(html.encode("utf-8")).hexdigest()

    def set(self, url: str, html: str, compressed_context: Dict[str, Any], page_type: str = "unknown", confidence: float = 1.0) -> None:
        if not self.settings.CACHE_ENABLED:
            return
            
        key = self._generate_hash(html)
        embedding = StructuralEmbedding.generate(html)
        vector_blob = embedding.tobytes()
        context_json = json.dumps(compressed_context)
        now = datetime.utcnow().isoformat()
        
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
        logger.debug(f"Cached context for {url} with hash {key}")

    def get(self, url: str, html: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Returns (compressed_context, is_semantic_match)
        """
        if not self.settings.CACHE_ENABLED:
            return None, False
            
        key = self._generate_hash(html)
        
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tier 1: Exact Hash Match
            cursor.execute("SELECT compressed_context_json, confidence FROM cache WHERE xxhash = ?", (key,))
            row = cursor.fetchone()
            if row:
                confidence = row["confidence"]
                if confidence >= 0.3:
                    logger.debug(f"Tier 1 Cache Hit (Exact) for {url}")
                    return json.loads(row["compressed_context_json"]), False
            
            # Tier 2: Semantic Similarity Match
            embedding = StructuralEmbedding.generate(html)
            
            cursor.execute("SELECT xxhash, vector_blob, compressed_context_json, confidence FROM cache WHERE url = ?", (url,))
            rows = cursor.fetchall()
            
            best_match = None
            max_sim = 0.0
            
            for r in rows:
                if r["confidence"] < 0.3:
                    continue
                cached_vector = np.frombuffer(r["vector_blob"], dtype=np.float64)
                if len(cached_vector) == 68: # Ensure dimensionality matches
                    sim = StructuralEmbedding.cosine_similarity(embedding, cached_vector)
                    if sim > max_sim:
                        max_sim = sim
                        best_match = r
                        
            if max_sim >= self.settings.SIMILARITY_THRESHOLD and best_match:
                logger.debug(f"Tier 2 Cache Hit (Semantic) for {url} with similarity {max_sim:.2f}")
                return json.loads(best_match["compressed_context_json"]), True
                
        return None, False

    def update_confidence(self, html: str, success: bool) -> None:
        key = self._generate_hash(html)
        delta = 0.05 if success else -0.30
        
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT confidence FROM cache WHERE xxhash = ?", (key,))
            row = cursor.fetchone()
            if row:
                new_conf = max(0.0, min(1.0, row["confidence"] + delta))
                cursor.execute("UPDATE cache SET confidence = ? WHERE xxhash = ?", (new_conf, key))
                conn.commit()
                logger.debug(f"Updated confidence for hash {key} to {new_conf:.2f}")
