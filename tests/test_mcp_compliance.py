"""
Tests for MCP 2026-07-28 Protocol Compliance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies that the Browser Optimizer server adheres to the new stateless
MCP specification: resultType tagging, MRTR replay handles, caching metadata,
and protocol version constants.
"""

import pytest
from typing import cast, Any, Dict, Tuple, List

from browser_optimizer.server.main import (
    mcp,
    encode_replay_handle,
    decode_replay_handle,
    _complete_result,
    _input_required_result,
    extract_context,
    execute_action,
    get_metrics,
    replay_skill,
)
from browser_optimizer.config.protocol import (
    MCP_PROTOCOL_VERSION,
    ResultType,
    CacheScope,
)
from browser_optimizer.schemas.schemas import ReplayHandlePayload
from browser_optimizer.cache.db import macro_store
from browser_optimizer.browser.manager import manager


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Clean state between tests."""
    from browser_optimizer.cache.cache import semantic_cache
    semantic_cache.clear()
    manager.sessions.clear()

    class DummyBrowser:
        async def new_context(self):
            class DummyContext:
                async def new_page(self):
                    class DummyPage:
                        url = "about:blank"
                        is_closed_flag = False
                        async def goto(self, url, timeout=None, wait_until=None):
                            self.url = url
                        async def content(self):
                            return "<html><body>Hello</body></html>"
                        async def title(self):
                            return "Dummy Page"
                        def is_closed(self):
                            return self.is_closed_flag
                        async def close(self):
                            self.is_closed_flag = True
                        async def wait_for_load_state(self, state, timeout=None):
                            pass
                        async def wait_for_selector(self, selector, timeout=None):
                            if selector == "#fail":
                                raise Exception("Selector not found")
                        async def click(self, selector):
                            pass
                        async def fill(self, selector, value):
                            pass
                        async def select_option(self, selector, value=None):
                            pass
                        async def evaluate(self, script):
                            pass
                        async def wait_for_timeout(self, timeout):
                            pass
                    return DummyPage()
                async def close(self):
                    pass
            return DummyContext()

    setattr(manager, "browser", DummyBrowser())

    import sqlite3
    with sqlite3.connect("cache.db") as conn:
        conn.execute("DELETE FROM macros")
        conn.commit()

    yield
    manager.sessions.clear()


# ─────────────────────────────────────────────────────────────
# Protocol Version
# ─────────────────────────────────────────────────────────────

def test_protocol_version_constant():
    """The protocol version must be the 2026-07-28 spec."""
    assert MCP_PROTOCOL_VERSION == "2026-07-28"


# ─────────────────────────────────────────────────────────────
# Result Type: complete
# ─────────────────────────────────────────────────────────────

def test_complete_result_wrapper():
    """_complete_result must inject _meta.resultType = 'complete'."""
    result = _complete_result({"foo": "bar"})
    assert "_meta" in result
    assert result["_meta"]["resultType"] == "complete"
    assert result["_meta"]["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert result["foo"] == "bar"


def test_input_required_result_wrapper():
    """_input_required_result must inject _meta.resultType = 'input_required' with questions."""
    questions = [{"id": "q1", "description": "Are you sure?", "type": "confirmation"}]
    result = _input_required_result({"status": "pending"}, questions)
    assert "_meta" in result
    assert result["_meta"]["resultType"] == "input_required"
    assert result["_meta"]["questions"] == questions
    assert result["status"] == "pending"


@pytest.mark.anyio
async def test_extract_context_returns_complete_result():
    """extract_context must return resultType='complete'."""
    class DummyPage:
        url = "https://example.com"
        async def title(self):
            return "Test"
        async def wait_for_load_state(self, state, timeout=None):
            pass
        async def content(self):
            return "<html></html>"

    async def mock_get_page(session_id="default"):
        return DummyPage()

    original = manager.get_page
    setattr(manager, "get_page", mock_get_page)
    try:
        result = await extract_context("https://example.com", "test")
        assert "_meta" in result
        assert result["_meta"]["resultType"] == "complete"
    finally:
        setattr(manager, "get_page", original)


@pytest.mark.anyio
async def test_execute_action_returns_complete_result():
    """execute_action must return resultType='complete'."""
    result = await execute_action("click", "#btn", None, "default")
    assert "_meta" in result
    assert result["_meta"]["resultType"] == "complete"


def test_get_metrics_returns_complete_result():
    """get_metrics must return resultType='complete'."""
    result = get_metrics()
    assert "_meta" in result
    assert result["_meta"]["resultType"] == "complete"


# ─────────────────────────────────────────────────────────────
# Result Type: input_required (MRTR)
# ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_replay_skill_returns_input_required_on_failure():
    """
    When a macro step fails, replay_skill must return
    resultType='input_required' with a replay_handle and questions.
    """
    sequence = [
        {"action": "click", "selector": "#ok", "value": None},
        {"action": "click", "selector": "#fail", "value": None},
    ]
    macro_id = macro_store.save_macro("Test Macro", "TEST", sequence)

    result = await replay_skill(macro_id, {}, session_id="test_mrtr")

    assert "_meta" in result
    assert result["_meta"]["resultType"] == "input_required"
    assert "questions" in result["_meta"]
    assert len(result["_meta"]["questions"]) > 0
    assert result["_meta"]["questions"][0]["type"] == "confirmation"
    assert "replay_handle" in result
    assert result["failed_step_index"] == 1


@pytest.mark.anyio
async def test_replay_skill_success_returns_complete():
    """When all macro steps succeed, replay_skill must return resultType='complete'."""
    sequence = [
        {"action": "click", "selector": "#ok", "value": None},
    ]
    macro_id = macro_store.save_macro("Good Macro", "TEST", sequence)

    result = await replay_skill(macro_id, {}, session_id="test_ok")
    assert "_meta" in result
    assert result["_meta"]["resultType"] == "complete"
    assert result["success"] is True


# ─────────────────────────────────────────────────────────────
# Replay Handle Encode/Decode (Stateless State)
# ─────────────────────────────────────────────────────────────

def test_replay_handle_roundtrip():
    """Encoding and decoding a replay handle must preserve all fields."""
    original = ReplayHandlePayload(
        macro_id=42,
        next_step_index=3,
        parameters={"username": "alice", "password": "secret"},
        session_id="my-session",
    )
    encoded = encode_replay_handle(original)
    decoded = decode_replay_handle(encoded)

    assert decoded.macro_id == 42
    assert decoded.next_step_index == 3
    assert decoded.parameters == {"username": "alice", "password": "secret"}
    assert decoded.session_id == "my-session"


def test_replay_handle_is_url_safe():
    """The encoded handle must be URL-safe (no +, /, or = padding issues)."""
    payload = ReplayHandlePayload(
        macro_id=1,
        next_step_index=0,
        parameters={"key": "value with spaces & special=chars"},
        session_id="test",
    )
    encoded = encode_replay_handle(payload)
    # url-safe base64 uses - and _ instead of + and /
    assert "+" not in encoded
    assert "/" not in encoded


def test_decode_invalid_handle():
    """Decoding an invalid handle must raise an error."""
    with pytest.raises(Exception):
        decode_replay_handle("not-a-valid-handle!!!")


# ─────────────────────────────────────────────────────────────
# Caching Metadata on List Responses
# ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_caching_metadata_on_list_tools():
    """
    MCP 2026-07-28: The list_tools meta-tool response must include
    _cache.ttlMs and _cache.cacheScope tags.
    """
    res, extra = cast(
        Tuple[List[Any], Dict[str, Any]],
        await mcp.call_tool("list_tools", {}),
    )
    assert "result" in extra
    result = extra["result"]

    # Must have _cache metadata
    assert "_cache" in result
    cache_meta = result["_cache"]
    assert "ttlMs" in cache_meta
    assert "cacheScope" in cache_meta
    assert isinstance(cache_meta["ttlMs"], int)
    assert cache_meta["ttlMs"] > 0
    assert cache_meta["cacheScope"] in ("public", "private")


# ─────────────────────────────────────────────────────────────
# No Stale APIs
# ─────────────────────────────────────────────────────────────

def test_no_suspended_replays_global():
    """The legacy suspended_replays global dict must not exist."""
    import browser_optimizer.server.main as server_module
    assert not hasattr(server_module, "suspended_replays")


def test_no_resume_skill_tool():
    """The legacy resume_skill tool must not be registered."""
    import browser_optimizer.server.main as server_module
    assert not hasattr(server_module, "resume_skill")
