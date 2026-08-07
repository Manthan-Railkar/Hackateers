# Pidgey: Browser Optimizer MCP

A high-performance middleware between AI Agents and Web Applications designed to make browser automation blazingly fast, fault-tolerant, and cost-effective.

Pidgey acts as an intelligent intermediary Model Context Protocol (MCP) server that intercepts web navigation requests from AI Agents. Instead of feeding massive, token-heavy raw HTML back to LLMs, Pidgey compresses the DOM, strips non-essential elements, semantically caches page contexts, recovers from browser failures using versioned DOM checkpoints, and leverages LLM-aware website discovery (`llms.txt`) to bypass browser rendering altogether when inspecting static documentation.

---

## Overview

Pidgey reduces token context size by up to 85% per page load, drastically lowering LLM API costs while improving agent execution speed, session isolation, and operational reliability.

---

## Key Capabilities

- **Extreme Token Compression**: Strips non-essential markup (scripts, SVGs, styles, dynamic tracking attributes) and extracts interactive UI controls into a compact JSON schema.
- **LLM-Aware Website Discovery (`llms.txt`)**: Automatically discovers and parses `/llms.txt` specifications to determine whether browser automation is necessary. Bypasses Playwright to fetch and compress static documentation pages directly via HTTP.
- **DOM Checkpointing and Recovery Framework**: Automatically persists versioned DOM checkpoints and Playwright context storage states. Recovers transparently from browser process crashes, WebSocket disconnects, navigation timeouts, and network interruptions.
- **Semantic Caching and Structural Embedding**: Uses structural vector embeddings and cosine similarity in SQLite to return cached contexts for identical or template-similar pages without re-rendering.
- **Multimodal VLM Fallback**: Automatically captures screenshots and queries Multimodal Vision Models (Groq Llama 3.2 Vision) for canvas-heavy applications, CAPTCHAs, or pages lacking HTML controls.
- **Mission Control Live Dashboard**: Serves a real-time web dashboard (HTTP port 8050 / WebSocket port 8765) to monitor live screenshots, token savings, cost reductions, active sessions, and telemetry.
- **FastMCP Protocol Integration**: Implements MCP 2026-07-28 protocol compliance, offering stdio transport and stateless multi round-trip request (MRTR) skill macro replays.

---

## Architecture

```text
Incoming Agent Request
          |
          v
Browser Optimizer MCP Server
          |
  +-------+-------------------------+
  |                                 |
  v                                 v
LLMSDiscoveryManager         RecoveryManager
  |                                 |
  +----> Direct Fetch (No Browser)  +----> DOM Checkpoints DB (SQLite)
  |                                 |
  +----> Playwright Browser Manager <+
                 |
                 v
          Web Application
```

---

## Installation

### Prerequisites

- Python 3.10 or higher
- Git

### Quick Setup

1. Clone the repository:
```bash
git clone https://github.com/Manthan-Railkar/Hackateers.git
cd Hackateers
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install package in editable mode:
```bash
pip install -e .
```

4. Install Playwright browser dependencies:
```bash
browser-optimizer install
```

5. Configure environment variables:
```bash
cp .env.example .env
```

Configure `.env` settings as needed:
```env
LOG_LEVEL=INFO
HEADLESS=True
CACHE_ENABLED=True
ENABLE_CHECKPOINTING=True
ENABLE_LLMS_DISCOVERY=True
ENABLE_DIRECT_FETCH=True
WEBSOCKET_PORT=8765
DASHBOARD_PORT=8050
GROQ_API_KEY=your_api_key_here
```

---

## Usage

Start the Browser Optimizer MCP server and Mission Control dashboard:

```bash
browser-optimizer start
```

This starts:
1. FastMCP stdio server handling agent tool calls.
2. Mission Control live visual dashboard at `http://localhost:8050/mission-control`.
3. WebSocket push mode poller on `ws://localhost:8765`.

---

## Connecting to AI Clients

Pidgey runs over standard input/output (stdio) transport. Below are configuration steps for popular AI client platforms and agent frameworks.

### Claude Desktop

Locate or create your `claude_desktop_config.json` configuration file:
- On Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- On macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add Pidgey under `mcpServers`:

```json
{
  "mcpServers": {
    "pidgey-browser-optimizer": {
      "command": "browser-optimizer",
      "args": ["start"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

If using an absolute path to your Python virtual environment executable on Windows:

```json
{
  "mcpServers": {
    "pidgey-browser-optimizer": {
      "command": "C:\\path\\to\\Hackateers\\.venv\\Scripts\\browser-optimizer.exe",
      "args": ["start"]
    }
  }
}
```

Restart Claude Desktop to load the tools.

---

### Antigravity

Add Pidgey to your workspace or global `mcp_config.json` configuration file:

```json
{
  "mcpServers": {
    "pidgey": {
      "command": "browser-optimizer",
      "args": ["start"]
    }
  }
}
```

Alternatively using direct Python execution:

```json
{
  "mcpServers": {
    "pidgey": {
      "command": "python",
      "args": ["-m", "browser_optimizer.server.main"]
    }
  }
}
```

---

### Cursor IDE

1. Open Cursor Settings (`Ctrl + ,` or `Cmd + ,`).
2. Navigate to Features -> MCP Servers.
3. Click + Add New MCP Server.
4. Fill in the server details:
   - Name: `Pidgey`
   - Type: `command` (stdio)
   - Command: `browser-optimizer start`
5. Click Save.

---

### Custom Agent Frameworks (LangChain, LlamaIndex, AutoGen)

You can invoke Pidgey programmatically from custom Python MCP client applications:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="browser-optimizer",
    args=["start"],
    env=None
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.call_tool("list_tools", {})
        print("Discovered tools:", tools)
```

---

## Exposed MCP Tools

The server exposes the following protocol tools:

### Core Context & Execution
- `extract_context(url, session_id)`: Extracts compressed UI context. Consults `llms.txt` discovery engine to use direct HTTP fetch when possible, avoiding browser launch.
- `execute_action(action, selector, value, session_id)`: Executes browser actions (click, type, fill, select, scroll, wait, navigate) with automatic error recovery retries.
- `page_diff(url, session_id)`: Computes DOM deltas (added/removed elements) since the previous observation.
- `summarize_page(url, session_id)`: Returns a concise structural summary of the page.
- `classify_page(url, session_id)`: Categorizes page type (LOGIN, SEARCH, PRODUCT, CHECKOUT, etc.).
- `wait_until_ready(url, timeout, session_id)`: Waits for network stability and DOM load.
- `cache_lookup(url, session_id)`: Queries local SQLite semantic cache directly.

### DOM Checkpointing & Recovery
- `create_checkpoint(session_id, trigger)`: Captures a versioned DOM checkpoint.
- `load_latest_checkpoint(session_id)`: Retrieves latest checkpoint for a session.
- `restore_checkpoint(session_id)`: Restores browser state from latest checkpoint with confidence validation.
- `compare_checkpoint(session_id, checkpoint_id)`: Returns structural diff between checkpoint and current page.
- `delete_session_checkpoints(session_id)`: Purges stored checkpoints for a session.

### LLM-Aware Website Discovery (`llms.txt`)
- `discover_llms(url, force_refresh)`: Discovers and parses `/llms.txt` specification for a website.
- `parse_llms(markdown, base_url)`: Parses raw Markdown into structured documentation catalog.
- `get_cached_llms(hostname)`: Retrieves stored discovery cache entry.
- `select_navigation_strategy(url)`: Queries Decision Engine for strategy (DIRECT_FETCH, PLAYWRIGHT, HYBRID).
- `fetch_documentation(url)`: Direct HTTP download and DOM compression without Playwright.
- `invalidate_llms_cache(hostname)`: Purges stored `llms.txt` cache for a host.

### Automation, Monitoring & Dashboard
- `start_macro_recording(session_id)` & `save_macro(name, page_type, parameters_map, session_id)`: Record action sequences into reusable skills.
- `replay_skill(macro_id, parameters, session_id)`: Replays macro with stateless handle resumption.
- `list_skills(page_type)` & `suggest_skill(page_type)`: Recommend recorded skills based on page category.
- `watch_page(url, interval_seconds, session_id)` & `stop_watch_page(session_id)`: Stream live DOM changes via WebSocket.
- `get_session_replay(session_id)`: Retrieve append-only action execution log.
- `get_metrics()`: Returns real-time token savings, cache hit ratios, and discovery stats.
- `open_dashboard()`: Launches Mission Control dashboard in default browser.

---

## Testing

Run the full pytest suite:

```bash
python -m pytest tests/ -v
```

The test suite covers:
- Semantic caching and structural embeddings (`test_cache.py`, `test_embedding.py`)
- DOM compression and visual fallback (`test_compressor.py`, `test_visual_fallback.py`)
- Page classification (`test_classifier.py`)
- Macro skills and MRTR replay (`test_confidence.py`, `test_sessions.py`)
- MCP 2026-07-28 protocol compliance (`test_mcp_compliance.py`)
- DOM Checkpointing and Failure Recovery (`test_recovery.py`)
- LLM-Aware Website Discovery (`test_discovery.py`)
- Dashboard API & Observability (`test_dashboard.py`, `test_observability.py`)

---

## License

MIT License. Developed for Hackateers.
