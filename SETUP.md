# Pidgey 🐦 (Browser Optimizer MCP) - Setup & Integration Guide

This guide provides step-by-step instructions for installing Pidgey and connecting it as a **Model Context Protocol (MCP)** server to your favorite AI clients, including **Antigravity**, **Claude Desktop**, **Cursor**, and custom agent frameworks.

---

## 🛠️ 1. Prerequisites & Installation

### Step 1: Clone and Set Up Virtual Environment
Ensure you have **Python 3.10+** installed.

```bash
# Clone the repository
git clone https://github.com/Manthan-Railkar/Hackateers.git
cd Hackateers

# Create and activate a virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate
```

### Step 2: Install Pidgey Package
Install Pidgey in editable mode so the `browser-optimizer` CLI executable is registered globally in your virtual environment:

```bash
pip install -e .
```

### Step 3: Run the Auto-Installer
Pidgey includes an automated setup script that downloads the required Playwright Chromium browser binary and initializes your configuration:

```bash
browser-optimizer install
```

### Step 4: Configure Environment Variables
Copy the `.env.example` file to `.env`:

```bash
cp .env.example .env
```

*(Optional for Vision Fallback)*: To enable Multimodal VLM fallback for Canvas apps and CAPTCHAs, add your [Groq API Key](https://console.groq.com/keys) to `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview
```

---

## 🚀 2. Connecting to AI Clients

Pidgey runs over standard input/output (**stdio**) transport. Below are setup configurations for popular AI environments.

---

### 🔹 Option A: Antigravity

Add Pidgey to your Antigravity MCP settings configuration:

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

*Alternative (Direct Python Execution)*:
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

### 🔹 Option B: Claude Desktop

Locate or create your `claude_desktop_config.json` file:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

*Note for Windows*: If using an absolute path to your Python virtual environment:
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

---

### 🔹 Option C: Cursor IDE

1. Open **Cursor Settings** (`Ctrl + ,` or `Cmd + ,`).
2. Navigate to **Features** -> **MCP Servers**.
3. Click **+ Add New MCP Server**.
4. Configure the server:
   - **Name**: `Pidgey`
   - **Type**: `command` (stdio)
   - **Command**: `browser-optimizer start`
5. Click **Save**.

---

### 🔹 Option D: Custom Agent Frameworks (LangChain, LlamaIndex, AutoGen)

If you are invoking Pidgey programmatically from custom Python/TypeScript MCP client libraries:

#### Python (mcp client):
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
        # Discover tools via progressive disclosure
        tools = await session.call_tool("list_tools", {})
        print("Available tools:", tools)
```

---

## 📊 3. Accessing the Mission Control Dashboard

When Pidgey starts, it automatically spins up a background HTTP web server at `http://localhost:8050`.

Open **`http://localhost:8050`** in your browser to monitor:
- **Live Token Savings Counter** (using exact `tiktoken` byte-pair encoding counts)
- **Cache Hit / Miss & Semantic Hit Ratios**
- **Live Viewport Stream** & screenshot playback
- **Session Replay Timelines**

---

## 🛠️ 4. MCP Tools Exposed to AI Agents

Once connected, your AI Agent will have progressive access to the following tools:

| Meta / Tool | Description |
| :--- | :--- |
| `list_tools` | Meta-tool returning lightweight names and descriptions of all tools |
| `get_tool_schema` | On-demand retrieval of full parameter schemas for specific tools |
| `extract_context` | Navigates to a URL and returns hyper-compressed interactive UI JSON |
| `execute_action` | Executes Playwright actions (`click`, `type`, `select`, `scroll`) |
| `page_diff` | Computes DOM state deltas (added/removed elements) |
| `classify_page` | Categorizes page type (`LOGIN`, `SEARCH`, `CHECKOUT`, `PRODUCT`) via LightGBM ML model |
| `summarize_page` | Generates a concise semantic summary of element counts & content |
| `watch_page` | Spawns a background WebSocket poller pushing real-time diffs |
| `start_macro_recording` / `save_macro` | Records repetitive action sequences into reusable skills |
| `suggest_skill` / `replay_skill` | Replays saved macros with confidence-based routing & fallback |
| `get_session_replay` | Fetches step-by-step session execution logs |

---

## 🧪 5. Troubleshooting & Verification

### Test manual execution from terminal:
```bash
browser-optimizer start
```
You should see:
```text
INFO | Starting Browser...
INFO | Chromium Started
INFO | Dashboard Server running on http://localhost:8050
```

### Re-run test suite:
```bash
python -m pytest
```
All 52 unit/integration tests should pass.
