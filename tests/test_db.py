import os
import pytest
from browser_optimizer.cache.db import (
    init_db,
    save_session_state,
    load_session_state,
    delete_session_state,
    SessionStateStore,
)


@pytest.fixture
def test_db_path(tmp_path):
    """Provides a temporary SQLite database path for isolated testing."""
    db_file = tmp_path / "test_cache.db"
    return str(db_file)


def test_init_db(test_db_path):
    """Verify SQLite database tables are created."""
    init_db(test_db_path)
    assert os.path.exists(test_db_path)


def test_session_state_lifecycle(test_db_path):
    """Verify saving, loading, and deleting Playwright storage states."""
    init_db(test_db_path)
    
    session_id = "test_session_1"
    sample_state = {
        "cookies": [{"name": "auth_token", "value": "xyz123", "domain": "example.com"}],
        "origins": []
    }
    
    # Initially should be None
    assert load_session_state(session_id, test_db_path) is None
    
    # Save session state
    save_session_state(session_id, sample_state, test_db_path)
    
    # Load and verify
    loaded = load_session_state(session_id, test_db_path)
    assert loaded is not None
    assert loaded["cookies"][0]["name"] == "auth_token"
    
    # Delete and verify
    delete_session_state(session_id, test_db_path)
    assert load_session_state(session_id, test_db_path) is None


def test_session_state_store_class(test_db_path):
    """Verify SessionStateStore OOP wrapper methods."""
    store = SessionStateStore(test_db_path)
    session_id = "test_session_2"
    sample_state = {"cookies": [], "origins": []}
    
    store.save(session_id, sample_state)
    assert store.load(session_id) == sample_state
    
    store.delete(session_id)
    assert store.load(session_id) is None
