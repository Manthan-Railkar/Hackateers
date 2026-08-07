"""
SQLite database module for persistent caching.
Replaces the in-memory TTLCache with a persistent store that survives process restarts.
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple, Dict
from browser_optimizer.utils.logger import logger

class SQLiteCache:
    """
    A dictionary-like interface over an SQLite database to act as a persistent TTL cache.
    """
    _PURGE_INTERVAL = 60  # seconds between automatic purge sweeps during get() calls

    def __init__(self, db_path: str = "cache.db", ttl: int = 300):
        self.db_path = db_path
        self.ttl = ttl
        self._last_purge: float = 0.0
        self._init_db()
        self.purge_expired()

    def _init_db(self):
        """Initialize the SQLite schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at REAL,
                    ttl REAL,
                    hit_count INTEGER DEFAULT 0,
                    embedding TEXT,
                    confidence REAL DEFAULT 0.8
                )
            ''')
            # Migrations: add columns if missing (existing databases)
            try:
                conn.execute("ALTER TABLE cache ADD COLUMN embedding TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists
            try:
                conn.execute("ALTER TABLE cache ADD COLUMN confidence REAL DEFAULT 0.8")
            except sqlite3.OperationalError:
                pass  # column already exists
            conn.commit()

    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """
        Retrieve an item from the cache. Purges expired items at most once per 60 seconds.
        Increments the hit count if the item is found.
        """
        now = time.time()
        if now - self._last_purge >= self._PURGE_INTERVAL:
            self.purge_expired()
            self._last_purge = now
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, hit_count, confidence, created_at, ttl FROM cache WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row:
                value_str, hit_count, confidence, created_at, row_ttl = row
                # Per-row TTL check: honour expiry even if bulk purge hasn't run yet
                if time.time() > created_at + row_ttl:
                    return default
                # Increment hit_count
                conn.execute("UPDATE cache SET hit_count = ? WHERE key = ?", (hit_count + 1, key))
                conn.commit()
                try:
                    data = json.loads(value_str)
                    if isinstance(data, dict):
                        data["confidence"] = confidence
                    return data
                except (json.JSONDecodeError, TypeError):
                    pass
        return default

    def set(self, key: str, value: Any, embedding: Optional[List[float]] = None):
        """
        Store an item in the cache with an optional structural embedding.
        """
        value_str = json.dumps(value)
        embedding_str = json.dumps(embedding) if embedding is not None else None
        created_at = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO cache (key, value, created_at, ttl, hit_count, embedding, confidence)
                VALUES (?, ?, ?, ?, 0, ?, 0.8)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    created_at=excluded.created_at,
                    ttl=excluded.ttl,
                    hit_count=0,
                    embedding=excluded.embedding,
                    confidence=0.8
            ''', (key, value_str, created_at, self.ttl, embedding_str))
            conn.commit()

    def update_confidence(self, key: str, success: bool):
        """
        Adjust the confidence score of a page context cache entry based on success/failure.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT confidence FROM cache WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                confidence = row[0]
                if success:
                    confidence = min(1.0, confidence + 0.05)
                else:
                    confidence = max(0.0, confidence - 0.3)
                conn.execute("UPDATE cache SET confidence = ? WHERE key = ?", (confidence, key))
                conn.commit()

    def __setitem__(self, key: str, value: Any):
        """
        Store an item in the cache (dict-style, without embedding).
        """
        self.set(key, value)

    def get_all_embeddings(self) -> List[Tuple[str, List[float], Any]]:
        """
        Retrieve all non-expired entries that have an embedding stored.

        Returns:
            List of (key, embedding, value) tuples.
        """
        self.purge_expired()
        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT key, embedding, value, confidence FROM cache WHERE embedding IS NOT NULL"
            )
            for row in cursor.fetchall():
                key, emb_str, val_str, confidence = row
                try:
                    embedding = json.loads(emb_str)
                    value = json.loads(val_str)
                    if isinstance(value, dict):
                        value["confidence"] = confidence
                    results.append((key, embedding, value))
                except (json.JSONDecodeError, TypeError):
                    continue
        return results

    def clear(self):
        """
        Clear all entries from the cache.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def purge_expired(self):
        """
        Remove entries that have exceeded their TTL.
        """
        current_time = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache WHERE created_at + ttl < ?", (current_time,))
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Purged {deleted} expired cache entries.")
            conn.commit()

class MacroStore:
    """
    Persistent storage for recorded action macros (Skill-level caching).
    """
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS macros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    page_type TEXT,
                    sequence TEXT,
                    confidence REAL DEFAULT 0.8,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0
                )
            ''')
            # Migration: alter macros table confidence default to 0.8 if already exists
            # SQLite does not easily allow altering column defaults, but new rows can insert 0.8 explicitly.
            conn.commit()

    def save_macro(self, name: str, page_type: str, sequence: list) -> int:
        sequence_str = json.dumps(sequence)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO macros (name, page_type, sequence, confidence, success_count, fail_count)
                VALUES (?, ?, ?, 0.8, 0, 0)
            ''', (name, page_type, sequence_str))
            conn.commit()
            row_id = cursor.lastrowid
            assert row_id is not None, "INSERT into macros failed to return a row ID"
            return row_id

    def list_macros(self, page_type: Optional[str] = None) -> list:
        with sqlite3.connect(self.db_path) as conn:
            if page_type:
                cursor = conn.execute("SELECT id, name, page_type, sequence, confidence, success_count, fail_count FROM macros WHERE page_type = ?", (page_type,))
            else:
                cursor = conn.execute("SELECT id, name, page_type, sequence, confidence, success_count, fail_count FROM macros")
            
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "page_type": r[2],
                    "sequence": json.loads(r[3]),
                    "confidence": r[4],
                    "success_count": r[5],
                    "fail_count": r[6]
                }
                for r in rows
            ]

    def get_macro(self, macro_id: int) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, name, page_type, sequence, confidence, success_count, fail_count FROM macros WHERE id = ?", (macro_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "page_type": row[2],
                    "sequence": json.loads(row[3]),
                    "confidence": row[4],
                    "success_count": row[5],
                    "fail_count": row[6]
                }
        return None

    def get_best_macro(self, page_type: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, name, page_type, sequence, confidence, success_count, fail_count "
                "FROM macros WHERE page_type = ? ORDER BY confidence DESC, success_count DESC LIMIT 1", 
                (page_type,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "page_type": row[2],
                    "sequence": json.loads(row[3]),
                    "confidence": row[4],
                    "success_count": row[5],
                    "fail_count": row[6]
                }
        return None

    def update_confidence(self, macro_id: int, success: bool):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT confidence, success_count, fail_count FROM macros WHERE id = ?", (macro_id,))
            row = cursor.fetchone()
            if row:
                confidence, success_count, fail_count = row
                if success:
                    success_count += 1
                    confidence = min(1.0, confidence + 0.05)
                else:
                    fail_count += 1
                    confidence = max(0.0, confidence - 0.3)
                
                conn.execute('''
                    UPDATE macros
                    SET confidence = ?, success_count = ?, fail_count = ?
                    WHERE id = ?
                ''', (confidence, success_count, fail_count, macro_id))
                conn.commit()


class SessionReplayStore:
    """
    Persistent append-only log for lightweight session replays.
    Logs each (timestamp, page_classification, action_taken, confidence_used, outcome) tuple.
    """
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS session_replay (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp REAL,
                    page_classification TEXT,
                    action_taken TEXT,
                    confidence_used REAL,
                    outcome TEXT
                )
            ''')
            conn.commit()

    def log_event(self, session_id: str, page_classification: Optional[str], action_taken: str, confidence_used: Optional[float], outcome: str):
        timestamp = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO session_replay (session_id, timestamp, page_classification, action_taken, confidence_used, outcome)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, timestamp, page_classification, action_taken, confidence_used, outcome))
            conn.commit()

    def get_replay(self, session_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT timestamp, page_classification, action_taken, confidence_used, outcome "
                "FROM session_replay WHERE session_id = ? ORDER BY id ASC", (session_id,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "timestamp": r[0],
                    "page_classification": r[1],
                    "action_taken": r[2],
                    "confidence_used": r[3],
                    "outcome": r[4]
                }
                for r in rows
            ]

    def clear_replay(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM session_replay WHERE session_id = ?", (session_id,))
            conn.commit()

    def clear_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM session_replay")
            conn.commit()


class SessionStateStore:
    """
    Persistent store for browser context session states (cookies, localStorage, etc.).
    """
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS session_states (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT,
                    updated_at REAL
                )
            ''')
            conn.commit()

    def save_state(self, session_id: str, state: Any):
        state_json = json.dumps(state)
        updated_at = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO session_states (session_id, state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
            ''', (session_id, state_json, updated_at))
            conn.commit()

    def get_state(self, session_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT state_json FROM session_states WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return None
        return None

    def clear_state(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM session_states WHERE session_id = ?", (session_id,))
            conn.commit()


class DOMCheckpointDB:
    """
    Persistent store for DOM Checkpoints in SQLite table 'dom_checkpoints'.
    Supports fast queries indexed by session_id, timestamp, and dom_hash.
    Enforces checkpoint retention limits per session and automatic age pruning.
    """
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dom_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    url TEXT,
                    title TEXT,
                    compressed_dom TEXT,
                    dom_hash TEXT,
                    scroll_x INTEGER DEFAULT 0,
                    scroll_y INTEGER DEFAULT 0,
                    viewport_width INTEGER DEFAULT 1280,
                    viewport_height INTEGER DEFAULT 720,
                    focused_element TEXT,
                    timestamp REAL,
                    version TEXT DEFAULT '1.0',
                    metadata TEXT
                )
            ''')
            # Create indexes for fast lookup and pruning
            conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON dom_checkpoints(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_timestamp ON dom_checkpoints(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_dom_hash ON dom_checkpoints(dom_hash)")
            conn.commit()

    def save_checkpoint(self, checkpoint_data: dict, max_checkpoints: int = 20, retention_days: int = 7) -> int:
        """
        Store a new DOM checkpoint record and automatically prune old entries.
        """
        session_id = checkpoint_data.get("session_id", "default")
        url = checkpoint_data.get("url", "")
        title = checkpoint_data.get("page_title") or checkpoint_data.get("title") or ""
        compressed_dom_str = json.dumps(checkpoint_data.get("compressed_dom") or {})
        dom_hash = checkpoint_data.get("dom_hash", "")
        scroll_x = int(checkpoint_data.get("scroll_x", 0))
        scroll_y = int(checkpoint_data.get("scroll_y", 0))
        viewport_width = int(checkpoint_data.get("viewport_width", 1280))
        viewport_height = int(checkpoint_data.get("viewport_height", 720))
        focused_element = checkpoint_data.get("focused_element")
        timestamp = float(checkpoint_data.get("timestamp", time.time()))
        version = checkpoint_data.get("checkpoint_version") or checkpoint_data.get("version") or "1.0"
        metadata_str = json.dumps(checkpoint_data.get("metadata") or {})

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO dom_checkpoints (
                    session_id, url, title, compressed_dom, dom_hash,
                    scroll_x, scroll_y, viewport_width, viewport_height,
                    focused_element, timestamp, version, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, url, title, compressed_dom_str, dom_hash,
                scroll_x, scroll_y, viewport_width, viewport_height,
                focused_element, timestamp, version, metadata_str
            ))
            conn.commit()
            checkpoint_id = cursor.lastrowid or 0

        # Perform retention pruning
        self.prune_checkpoints(session_id, max_checkpoints=max_checkpoints, max_age_days=retention_days)
        return checkpoint_id

    def _row_to_dict(self, row: Tuple) -> dict:
        (
            c_id, session_id, url, title, compressed_dom_str, dom_hash,
            scroll_x, scroll_y, viewport_width, viewport_height,
            focused_element, timestamp, version, metadata_str
        ) = row

        try:
            compressed_dom = json.loads(compressed_dom_str)
        except Exception:
            compressed_dom = {}

        try:
            metadata = json.loads(metadata_str)
        except Exception:
            metadata = {}

        return {
            "checkpoint_id": c_id,
            "session_id": session_id,
            "url": url,
            "page_title": title,
            "compressed_dom": compressed_dom,
            "dom_hash": dom_hash,
            "scroll_x": scroll_x,
            "scroll_y": scroll_y,
            "viewport_width": viewport_width,
            "viewport_height": viewport_height,
            "focused_element": focused_element,
            "timestamp": timestamp,
            "checkpoint_version": version,
            "metadata": metadata
        }

    def get_latest_checkpoint(self, session_id: str = "default") -> Optional[dict]:
        """
        Fetch the most recent checkpoint for a given session ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, session_id, url, title, compressed_dom, dom_hash,
                       scroll_x, scroll_y, viewport_width, viewport_height,
                       focused_element, timestamp, version, metadata
                FROM dom_checkpoints
                WHERE session_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
            ''', (session_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    def get_checkpoint_by_id(self, checkpoint_id: int) -> Optional[dict]:
        """
        Fetch a specific checkpoint by primary key ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, session_id, url, title, compressed_dom, dom_hash,
                       scroll_x, scroll_y, viewport_width, viewport_height,
                       focused_element, timestamp, version, metadata
                FROM dom_checkpoints
                WHERE id = ?
            ''', (checkpoint_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    def list_checkpoints(self, session_id: str = "default", limit: int = 20) -> List[dict]:
        """
        List recent checkpoints for a session ordered by timestamp descending.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, session_id, url, title, compressed_dom, dom_hash,
                       scroll_x, scroll_y, viewport_width, viewport_height,
                       focused_element, timestamp, version, metadata
                FROM dom_checkpoints
                WHERE session_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            ''', (session_id, limit))
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def delete_session_checkpoints(self, session_id: str):
        """
        Delete all checkpoints associated with a session ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM dom_checkpoints WHERE session_id = ?", (session_id,))
            conn.commit()

    def prune_checkpoints(self, session_id: str, max_checkpoints: int = 20, max_age_days: int = 7):
        """
        Prune checkpoints exceeding max_checkpoints count or max_age_days threshold for a session.
        """
        cutoff_timestamp = time.time() - (max_age_days * 86400)
        with sqlite3.connect(self.db_path) as conn:
            # Delete expired by age
            conn.execute(
                "DELETE FROM dom_checkpoints WHERE session_id = ? AND timestamp < ?",
                (session_id, cutoff_timestamp)
            )
            # Delete excess beyond max_checkpoints count
            cursor = conn.execute('''
                SELECT id FROM dom_checkpoints
                WHERE session_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT -1 OFFSET ?
            ''', (session_id, max_checkpoints))
            old_ids = [r[0] for r in cursor.fetchall()]
            if old_ids:
                placeholders = ",".join("?" for _ in old_ids)
                conn.execute(f"DELETE FROM dom_checkpoints WHERE id IN ({placeholders})", old_ids)
            conn.commit()


class LLMSCacheDB:
    """
    Persistent SQLite storage for llms.txt discovery payloads, parsed schemas,
    ETags, and HTTP Last-Modified headers.
    """
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS llms_cache (
                    hostname TEXT PRIMARY KEY,
                    fetched_at REAL,
                    expires_at REAL,
                    version TEXT,
                    raw_content TEXT,
                    parsed_json TEXT,
                    etag TEXT,
                    last_modified TEXT
                )
            ''')
            conn.commit()

    def save_llms_cache(
        self,
        hostname: str,
        raw_content: str,
        parsed_dict: dict,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        version: Optional[str] = None,
        ttl: int = 86400
    ):
        fetched_at = time.time()
        expires_at = fetched_at + ttl
        parsed_json = json.dumps(parsed_dict)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO llms_cache (
                    hostname, fetched_at, expires_at, version, raw_content, parsed_json, etag, last_modified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hostname) DO UPDATE SET
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at,
                    version=excluded.version,
                    raw_content=excluded.raw_content,
                    parsed_json=excluded.parsed_json,
                    etag=excluded.etag,
                    last_modified=excluded.last_modified
            ''', (hostname, fetched_at, expires_at, version, raw_content, parsed_json, etag, last_modified))
            conn.commit()

    def get_llms_cache(self, hostname: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT hostname, fetched_at, expires_at, version, raw_content, parsed_json, etag, last_modified
                FROM llms_cache
                WHERE hostname = ?
            ''', (hostname,))
            row = cursor.fetchone()
            if row:
                h_name, fetched_at, expires_at, version, raw_content, parsed_str, etag, last_modified = row
                try:
                    parsed = json.loads(parsed_str)
                except Exception:
                    parsed = {}

                return {
                    "hostname": h_name,
                    "fetched_at": fetched_at,
                    "expires_at": expires_at,
                    "is_expired": time.time() > expires_at,
                    "version": version,
                    "raw_content": raw_content,
                    "parsed": parsed,
                    "etag": etag,
                    "last_modified": last_modified
                }
        return None

    def invalidate_cache(self, hostname: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM llms_cache WHERE hostname = ?", (hostname,))
            conn.commit()


macro_store = MacroStore()
session_replay_store = SessionReplayStore()
session_state_store = SessionStateStore()
dom_checkpoint_db = DOMCheckpointDB()
llms_cache_db = LLMSCacheDB()


