# Pidgey (Browser Optimizer MCP)

**A powerful middleware between AI Agents and Websites designed to make Web Automation tasks blazingly fast and cost-effective.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-Server-brightgreen.svg)](https://github.com/fastmcp)
[![Playwright](https://img.shields.io/badge/Playwright-Enabled-red.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Pidgey acts as an intelligent intermediary (Model Context Protocol Server) that intercepts web navigation requests from AI Agents. Instead of feeding massive, token-heavy raw HTML back to your LLM, Pidgey compresses the DOM, strips away noise, semantically caches pages, and leverages Multimodal Vision Models (VLMs) to provide an ultra-lean, highly actionable UI payload.

**The Result?** You save up to 85% on LLM context tokens per page load, dramatically reducing API costs while increasing your agent's execution speed and reliability.

---

## Key Features

- **Extreme Token Compression**: Decomposes non-essential tags (scripts, SVGs, styles) and extracts purely interactive UI controls into a compact JSON schema.
- **Semantic Caching & Embedding**: Automatically embeds web page contexts locally using `SentenceTransformers` and SQLite. Identical or highly similar (cosine similarity > 0.90) page hits return instantly without re-rendering the DOM.
- **Multimodal VLM Fallback**: For Canvas-heavy apps, CAPTCHAs, or SPAs lacking standard HTML controls, Pidgey automatically captures a screenshot and uses **Groq's Llama 3.2 Vision** model to extract interactive bounding boxes.
- **Real-time Metrics Dashboard**: Includes a live, glassmorphic HTTP dashboard to visually track your LLM token savings (powered by accurate `tiktoken` byte-pair encoding counts) and cache hit ratios.
- **FastMCP Integration**: Exposes a standard MCP stdio interface, instantly pluggable into any agent framework (like Claude Desktop or custom LangChain setups).

---

## Installation

Pidgey is designed to be installed as a local CLI tool and Python package.

### 1. Clone the repository
```bash
git clone https://github.com/Manthan-Railkar/Hackateers.git
cd Hackateers
```

### 2. Set up a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Pidgey
Install the project in editable mode so the CLI commands are registered.
```bash
pip install -e .
```

### 4. Install Playwright Browsers
Pidgey requires Chromium to natively control the browser. We've built an auto-installer to handle this and register the MCP server config for you:
```bash
browser-optimizer install
```

### 5. Environment Configuration
Copy the sample environment file and configure your settings:
```bash
cp .env.example .env
```
*(Optional)* To enable the VLM Fallback for Canvas apps, add your [Groq API Key](https://console.groq.com/keys) to the `.env` file:
```env
GROQ_API_KEY=your_api_key_here
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview
```

---

## Usage

Starting Pidgey is incredibly simple. Just run:

```bash
browser-optimizer start
```

This single command will:
1. Launch the **FastMCP stdio server**, ready to receive tool calls (`extract_context`, `execute_action`, `page_diff`, etc.) from your AI Agents.
2. Spin up a background **Dashboard Web Server** at `http://localhost:8050`.

You can open `http://localhost:8050` in your browser at any time to watch your token savings grow in real-time as your agents navigate the web!

---

## MCP Tools Exposed

Once connected, your AI Agent will have access to the following native tools:

- `extract_context(url)`: Navigates to a URL and returns the hyper-compressed JSON representation of interactive UI elements.
- `execute_action(url, action, selector, value)`: Triggers a Playwright browser action (click, fill, select, scroll) on the page.
- `page_diff(url)`: Computes the exact DOM state delta (added/removed elements) after a click or navigation.
- `summarize_page(url)`: Uses lightweight NLP heuristic logic to return a summary of the page structure.
- `classify_page(url)`: Uses a LightGBM ML model (or heuristic fallback) to categorize the page (e.g. LOGIN, SEARCH, CHECKOUT).
- `watch_page(url, frequency)`: Spawns a background WebSocket task that streams live DOM changes back to the agent.
- `start_macro_recording(session_id)` & `save_macro(macro_id)`: Records a sequence of actions into an automated skill pipeline for repetitive workflows.

---

## Testing and Benchmarks

We've included a synthetic benchmark suite to verify the token compression ratios across complex webpages (e.g., HackerNews).
```bash
PYTHONPATH=. .venv/bin/python scripts/benchmark.py
```
*(Note: Expect >85% token savings compared to raw DOM ingestion!)*

---

*Built for the Hackateers.*
