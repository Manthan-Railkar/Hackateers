# Pidgey (Browser Optimizer MCP) - Setup & Integration Guide

This guide provides step-by-step instructions for installing Pidgey via PyPI or source and connecting it as a **Model Context Protocol (MCP)** server to AI client environments including **Claude Desktop**, **Antigravity**, **Cursor IDE**, **Windsurf**, **VS Code (Continue)**, and custom agent frameworks.

---

## 1. Installation Methods

### Option A: Install from PyPI (Recommended)

Ensure you have **Python 3.10+** installed:

```bash
# Install PyPI package
pip install pidgey-mcp

# Install Playwright browser dependencies & auto-configure AI clients
pidgey install
```

Or run directly without manual installation via `uvx`:

```bash
uvx pidgey-mcp start
```

---

### Option B: Install from Source

```bash
# Clone the repository
git clone https://github.com/Manthan-Railkar/Hackateers.git
cd Hackateers

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install in editable mode
pip install -e .

# Run Playwright auto-installer & client detector
pidgey install

# Configure environment variables
cp .env.example .env
```

---

## 2. Connecting to AI Agent Environments

Pidgey runs over standard input/output (`stdio`) transport. Below are setup configurations for major AI client applications after downloading from PyPI.

---

### Method 1: Automated Auto-Configuration

Run:
```bash
pidgey install
```
This command automatically detects **Claude Desktop** and **Antigravity IDE** on your system and writes the MCP configuration block into their respective settings files.

---

### Method 2: Manual Configuration

### Option 1: Claude Desktop

Locate your `claude_desktop_config.json`:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

#### Using PyPI package (`pip install pidgey-mcp`):

```json
{
  "mcpServers": {
    "pidgey": {
      "command": "pidgey",
      "args": ["start"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

#### Using `uvx` (no pre-installation required):

```json
{
  "mcpServers": {
    "pidgey": {
      "command": "uvx",
      "args": ["pidgey-mcp", "start"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Restart Claude Desktop to load Pidgey tools.

---

### Option 2: Antigravity IDE

Add Pidgey to your workspace or global `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "pidgey": {
      "command": "pidgey",
      "args": ["start"]
    }
  }
}
```

Or using `uvx`:

```json
{
  "mcpServers": {
    "pidgey": {
      "command": "uvx",
      "args": ["pidgey-mcp", "start"]
    }
  }
}
```

---

### Option 3: Cursor IDE

1. Open **Cursor Settings** (`Ctrl + ,` or `Cmd + ,`).
2. Navigate to **Features** -> **MCP Servers**.
3. Click **+ Add New MCP Server**.
4. Configure details:
   - **Name**: `pidgey`
   - **Type**: `command` (stdio)
   - **Command**: `pidgey start` (or `uvx pidgey-mcp start`)
5. Click **Save**.

---

### Option 4: Custom Agent Frameworks (LangChain, LlamaIndex, AutoGen)

Programmatic Python MCP client invocation:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="browser-optimizer",
    args=["start"],
    env=None
)

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Discover tools
            tools = await session.call_tool("list_tools", {})
            print("Connected tools:", len(tools.content))
            
            # Extract compressed page context
            result = await session.call_tool("extract_context", {"url": "https://example.com"})
            print("Extracted Context:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3. Accessing the Mission Control Dashboard

When Pidgey starts, it automatically spins up a background HTTP server at `http://localhost:8050`.

Open **`http://localhost:8050/mission-control`** in your web browser to monitor:
- **Real-Time Token Savings Counter** (via `tiktoken` byte-pair encoding counts)
- **Cache Hit / Miss & Semantic Hit Ratios**
- **Live Viewport Stream & Screenshots**
- **Session Replay Timelines**

---

## 4. Verification & Testing

Verify CLI start from terminal:

```bash
browser-optimizer start
```

Run test suite:

```bash
python -m pytest tests/ -v
```

All 78 unit, integration, and protocol compliance tests should pass.
