# Pidgey: Browser Optimizer MCP
> **Bridge AI Agents to Web Applications at 85% lower token cost with 10x faster execution and zero-downtime crash recovery.**

---

## 💡 The Inspiration / Problem

AI Agents are revolutionizing web automation, but interacting with modern websites is bottlenecked by severe limitations:

- **Massive Token Bloat**: Standard web pages contain 50,000+ lines of redundant scripts, styles, SVGs, and tracking tags. Feeding raw HTML into LLMs drains context windows instantly.
- **Exorbitant API Expenses**: Processing uncompressed web contexts costs dollars per agent loop, making large-scale web scraping and automation cost-prohibitive.
- **Fragile Browser Execution**: Browsers crash, network connections drop, and Playwright sessions disconnect, causing AI agents to fail mid-workflow and lose context.
- **Redundant Browser Booting**: Launching a full Chromium browser instance to read simple documentation or static web pages wastes time and system resources.

---

## 🚀 What it Does & Key Features

**Pidgey** is an intelligent Model Context Protocol (MCP) middleware operating between AI Agents and the Web. It intercepts navigation requests, strips non-essential markup, caches structural representations, recovers transparently from browser failures, and bypasses browser execution entirely when static documentation is detected.

### Key Features

- **Extreme Token Compression**: Decomposes non-essential DOM markup and extracts interactive UI controls into a hyper-compact JSON schema, saving up to 85% on context tokens.
- **LLM-Aware Website Discovery (`llms.txt`)**: Discovers `/llms.txt` specifications to determine if browser automation is required. Bypasses Playwright to fetch and compress static documentation directly via HTTP.
- **DOM Checkpointing & Browser Recovery**: Captures versioned DOM checkpoints and Playwright state snapshots. Automatically restores browser sessions with weighted confidence validation upon crashes or network disconnects.
- **Semantic Caching & Structural Vector Embeddings**: Embeds web page structures in a local SQLite database using structural vector embeddings and cosine similarity (>0.90) for sub-millisecond cache hits.
- **Multimodal VLM Fallback**: Uses Groq Llama 3.2 Vision to extract interactive bounding boxes when encountering Canvas-heavy applications, CAPTCHAs, or pages lacking HTML controls.
- **Mission Control Live Dashboard**: Serves a real-time web dashboard (HTTP port 8050) and WebSocket push poller (port 8765) to monitor live screenshots, token savings, cost metrics, and session replay timelines.

---

## 🛠️ Tech Stack

- **Core Runtime**: Python 3.10+
- **MCP Framework**: FastMCP (MCP Protocol Version 2026-07-28 Compliance)
- **Browser Automation**: Playwright Chromium
- **Parsing & Compression**: BeautifulSoup4, lxml, xxhash
- **Machine Learning & NLP**: LightGBM Page Classifier, Structural Vector Embedding Engine
- **Multimodal AI**: Groq API (`llama-3.2-11b-vision-preview`)
- **Database & Storage**: SQLite3 (`cache.db`), JSON Session Storage State
- **Observability**: Built-in HTTP Server, WebSocket Poller, HTML5/CSS3 Mission Control Dashboard

---

## ⚙️ Installation & Setup

### Prerequisites

- **Python**: v3.10 or higher
- **Git**: Installed on your system
- **Groq API Key** *(Optional)*: Required for Multimodal VLM vision fallback on Canvas apps

### Setup Commands

1. Clone the repository:
```bash
git clone https://github.com/Manthan-Railkar/Hackateers.git
cd Hackateers
```

2. Create and activate a Python virtual environment:
```bash
python -m venv .venv
# On macOS/Linux:
source .venv/bin/activate
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
```

3. Install the package in editable mode:
```bash
pip install -e .
```

4. Run the automated Playwright browser installer:
```bash
browser-optimizer install
```

5. Copy the sample environment file:
```bash
cp .env.example .env
```

6. Configure environment variables in `.env`:
```env
LOG_LEVEL=INFO
HEADLESS=True
CACHE_ENABLED=True
ENABLE_CHECKPOINTING=True
ENABLE_LLMS_DISCOVERY=True
ENABLE_DIRECT_FETCH=True
WEBSOCKET_PORT=8765
DASHBOARD_PORT=8050
GROQ_API_KEY=your_groq_api_key_here
```

### Run Commands

Start the Browser Optimizer MCP server and Mission Control dashboard:

```bash
browser-optimizer start
```

---

## 🔌 Connecting to AI Agents

Pidgey runs over standard input/output (`stdio`) transport and integrates into any MCP-compliant agent client.

### Claude Desktop

Add Pidgey under `mcpServers` in `claude_desktop_config.json` (`%APPDATA%\Claude\claude_desktop_config.json` on Windows or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

### Antigravity

Add Pidgey to your workspace or global `mcp_config.json`:

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

### Cursor IDE

1. Open **Cursor Settings** (`Ctrl + ,` or `Cmd + ,`).
2. Navigate to **Features** -> **MCP Servers**.
3. Click **+ Add New MCP Server**.
4. Configure details:
   - **Name**: `Pidgey`
   - **Type**: `command` (stdio)
   - **Command**: `browser-optimizer start`
5. Click **Save**.

### Custom Agent Frameworks (LangChain, LlamaIndex, AutoGen)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="browser-optimizer",
    args=["start"]
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.call_tool("list_tools", {})
        print("Available MCP tools:", tools)
```

---

## 🛠️ Complete MCP Tools Reference

Pidgey exposes 28 native tools for AI Agents:

### Core Context & Execution
- `extract_context(url, session_id)`: Navigates to a URL, checks `llms.txt` discovery for direct fetch, extracts and compresses DOM.
- `execute_action(action, selector, value, session_id)`: Executes browser actions (`click`, `type`, `fill`, `select`, `scroll`, `wait`, `navigate`) with error recovery retries.
- `page_diff(url, session_id)`: Computes DOM element deltas (added/removed) since the previous observation.
- `summarize_page(url, session_id)`: Returns structural element counts and page snippet summary.
- `classify_page(url, session_id)`: Returns page category classification (`LOGIN`, `PRODUCT`, `SEARCH`, `CHECKOUT`, etc.).
- `wait_until_ready(url, timeout, session_id)`: Navigates and pauses until network load stabilizes.
- `cache_lookup(url, session_id)`: Queries local SQLite semantic cache directly.

### DOM Checkpointing & Recovery
- `create_checkpoint(session_id, trigger)`: Captures a versioned DOM checkpoint.
- `load_latest_checkpoint(session_id)`: Retrieves the latest DOM checkpoint for a session.
- `restore_checkpoint(session_id)`: Triggers recovery restoration from the latest checkpoint.
- `compare_checkpoint(session_id, checkpoint_id)`: Compares current page state against a stored checkpoint.
- `delete_session_checkpoints(session_id)`: Purges stored checkpoints for a session.

### LLM-Aware Website Discovery (`llms.txt`)
- `discover_llms(url, force_refresh)`: Discovers and parses `/llms.txt` specifications for a domain.
- `parse_llms(markdown, base_url)`: Parses raw Markdown string into a structured catalog.
- `get_cached_llms(hostname)`: Retrieves stored `llms.txt` discovery cache entry.
- `select_navigation_strategy(url)`: Queries Decision Engine for strategy (`DIRECT_FETCH`, `PLAYWRIGHT`, `HYBRID`).
- `fetch_documentation(url)`: Direct HTTP download and DOM compression without Playwright.
- `invalidate_llms_cache(hostname)`: Purges stored `llms.txt` cache entry for a hostname.

### Automation, Monitoring & Dashboard
- `start_macro_recording(session_id)`: Begins recording browser actions for skill creation.
- `save_macro(name, page_type, parameters_map, session_id)`: Saves parameterized action sequences into reusable skills.
- `list_skills(page_type)`: Lists recorded skill macros.
- `suggest_skill(page_type)`: Recommends highest confidence macro and routing strategy.
- `replay_skill(macro_id, parameters, expected_url, expected_page_type, session_id, replay_handle)`: Replays recorded macro with MRTR stateless handle resumption.
- `watch_page(url, interval_seconds, session_id)`: Starts background WebSocket poller streaming live DOM diffs.
- `stop_watch_page(session_id)`: Stops background WebSocket page watching task.
- `get_session_replay(session_id)`: Retrieves append-only action log for a session.
- `get_metrics()`: Returns real-time token savings, cost estimates, cache ratios, and discovery stats.
- `open_dashboard()`: Launches Mission Control live dashboard in the default browser.

---

## 👥 Team Members

- **Manthan Railkar** and **Ayush Mhatre**
- **Hackateers Team**

---

## 🔮 Future Roadmap

- **Multi-Browser Driver Engine**: Add support for Firefox and WebKit browser engines alongside Chromium.
- **Distributed Redis Cache**: Upgrade local SQLite cache to Redis Vector DB for enterprise team cache sharing.
- **Autonomous Skill Synthesis**: Enable LLMs to automatically record, package, and publish macro skills to a shared registry.
- **Mobile Viewport Emulation**: Provide mobile device viewport emulation and touch gesture action APIs.
