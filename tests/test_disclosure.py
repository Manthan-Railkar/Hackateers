import pytest
import asyncio
from typing import cast, Any, Dict, Tuple, List
from browser_optimizer.server.main import mcp
from browser_optimizer.config.protocol import ResultType, MCP_PROTOCOL_VERSION

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_all_tools_exposed_in_list():
    """
    MCP 2026-07-28: All tools must be exposed in tools/list.
    No progressive disclosure — stateless protocols cannot rely on a handshake
    to progressively reveal tools.
    """
    exposed = await mcp.list_tools()
    exposed_names = {t.name for t in exposed}
    
    # All tools should be exposed, including the actual browser optimization tools
    assert "extract_context" in exposed_names
    assert "execute_action" in exposed_names
    assert "replay_skill" in exposed_names
    assert "list_tools" in exposed_names
    assert "get_tool_schema" in exposed_names


import json

async def _call_tool_compat(mcp_server, tool_name, args):
    ret = await mcp_server.call_tool(tool_name, args)
    if isinstance(ret, tuple):
        if len(ret) == 2 and isinstance(ret[1], dict):
            return ret[0], ret[1]
        content = ret[0]
        text = content[0].text if content and hasattr(content[0], "text") else "{}"
        return content, {"result": json.loads(text)}
    elif hasattr(ret, "content"):
        text = ret.content[0].text if ret.content and hasattr(ret.content[0], "text") else "{}"
        return ret.content, {"result": json.loads(text)}
    return ret, {}


@pytest.mark.anyio
async def test_list_tools_meta_tool_returns_caching_metadata():
    """
    MCP 2026-07-28: list_tools response must include ttlMs and cacheScope
    caching metadata so clients know how long to cache tool catalogs.
    """
    res, extra = await _call_tool_compat(mcp, "list_tools", {})
    assert "result" in extra
    result = extra["result"]
    
    # Verify _meta with resultType
    assert "_meta" in result
    assert result["_meta"]["resultType"] == ResultType.COMPLETE.value
    
    # Verify tools list
    tools = result["tools"]
    tool_names = {t["name"] for t in tools}
    assert "extract_context" in tool_names
    assert "execute_action" in tool_names
    assert "replay_skill" in tool_names
    
    # Meta-tools themselves should not be listed as optimization tools
    assert "list_tools" not in tool_names
    assert "get_tool_schema" not in tool_names
    
    # Verify caching metadata
    assert "_cache" in result
    assert "ttlMs" in result["_cache"]
    assert "cacheScope" in result["_cache"]
    assert isinstance(result["_cache"]["ttlMs"], int)
    assert result["_cache"]["ttlMs"] > 0


@pytest.mark.anyio
async def test_get_tool_schema_tool():
    """Verify that get_tool_schema returns the correct parameters schema for a tool."""
    res, extra = await _call_tool_compat(mcp, "get_tool_schema", {"tool_name": "extract_context"})
    assert "result" in extra
    result = extra["result"]
    
    # Verify _meta with resultType
    assert "_meta" in result
    assert result["_meta"]["resultType"] == ResultType.COMPLETE.value
    
    assert result["success"] is True
    assert result["tool_name"] == "extract_context"
    
    input_schema = result["input_schema"]
    assert "properties" in input_schema
    assert "url" in input_schema["properties"]
    assert "session_id" in input_schema["properties"]


@pytest.mark.anyio
async def test_resume_skill_no_longer_exists():
    """
    MCP 2026-07-28: resume_skill has been removed in favour of MRTR.
    Verify it is not registered as a tool.
    """
    all_tools = await mcp._original_list_tools()
    tool_names = {t.name for t in all_tools}
    assert "resume_skill" not in tool_names


@pytest.mark.anyio
async def test_unexposed_tool_execution():
    """Verify that tools can be successfully executed by name via call_tool."""
    from browser_optimizer.browser.manager import manager
    
    class DummyPage:
        url = "https://example.com"
        async def title(self):
            return "Test Title"
        async def wait_for_load_state(self, state, timeout=None):
            pass
        async def content(self):
            return "<html></html>"
            
    async def mock_get_page(session_id="default"):
        return DummyPage()
        
    original_get_page = manager.get_page
    setattr(manager, "get_page", mock_get_page)
    
    try:
        # Call extract_context directly via call_tool
        res, extra = await _call_tool_compat(mcp, "extract_context", {"url": "https://example.com", "session_id": "test_exec"})
        assert "result" in extra
        result = extra["result"]
        
        # Verify _meta with resultType
        assert "_meta" in result
        assert result["_meta"]["resultType"] == ResultType.COMPLETE.value
        
        assert result["url"] == "https://example.com"
        assert result["title"] == "Test Title"
    finally:
        setattr(manager, "get_page", original_get_page)
