import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional
from browser_optimizer.config.settings import get_settings
from browser_optimizer.utils.logger import logger


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Establishes and returns a connection to the SQLite database.
    """
    if not db_path:
        db_path = get_settings().SQLITE_DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initializes the SQLite database schema if tables do not exist.
    Creates session_states, cache, macros, and session_replay tables.
    """
    if not db_path:
        db_path = get_settings().SQLITE_DB_PATH

    logger.info(f"Initializing SQLite database schema at '{db_path}'")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Session States Table (Playwright context storage states)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_states (
                session_id TEXT PRIMARY KEY,
                storage_state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 2-Tier Cache Table (xxhash + vector embeddings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                xxhash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                vector_blob BLOB,
                compressed_context_json TEXT NOT NULL,
                page_type TEXT,
                confidence REAL DEFAULT 1.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. Macro Skills Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS macros (
                macro_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                confidence_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. Session Replay Telemetry Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_replay (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details_json TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
    logger.info("SQLite database schema initialized successfully.")


def save_session_state(session_id: str, storage_state: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """
    Persists or updates a Playwright storage state JSON payload in session_states table.
    """
    if not db_path:
        db_path = get_settings().SQLITE_DB_PATH
    
    storage_state_json = json.dumps(storage_state)
    now = datetime.utcnow().isoformat()
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO session_states (session_id, storage_state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                storage_state_json = excluded.storage_state_json,
                updated_at = excluded.updated_at
        """, (session_id, storage_state_json, now))
        conn.commit()
    logger.debug(f"Saved session state for session '{session_id}' in SQLite.")


def load_session_state(session_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves stored Playwright storage state dict for a given session_id.
    Returns None if no session state exists.
    """
    if not db_path:
        db_path = get_settings().SQLITE_DB_PATH
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT storage_state_json FROM session_states WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row and row["storage_state_json"]:
            try:
                return json.loads(row["storage_state_json"])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode storage state JSON for session '{session_id}': {e}")
                return None
    return None


def delete_session_state(session_id: str, db_path: Optional[str] = None) -> None:
    """
    Deletes the stored session state for a given session_id.
    """
    if not db_path:
        db_path = get_settings().SQLITE_DB_PATH
        
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_states WHERE session_id = ?", (session_id,))
        conn.commit()
    logger.debug(f"Deleted session state for session '{session_id}' from SQLite.")


class SessionStateStore:
    """
    OOP Wrapper for Session State operations.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_settings().SQLITE_DB_PATH
        init_db(self.db_path)

    def save(self, session_id: str, storage_state: Dict[str, Any]) -> None:
        save_session_state(session_id, storage_state, self.db_path)

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        return load_session_state(session_id, self.db_path)

    def delete(self, session_id: str) -> None:
        delete_session_state(session_id, self.db_path)
