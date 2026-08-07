# Pidgey: Browser Optimizer MCP
## PowerPoint Presentation Deck Guide

*Use this Markdown structure to easily generate slides in PowerPoint, Marp, Gamma, or Keynote.*

---

## Slide 1: Title Slide

### Pidgey: Browser Optimizer MCP
**The High-Speed, Token-Saving Middleware for AI Agent Web Automation**

- **Project Name**: Pidgey (Browser Optimizer MCP)
- **Tagline**: Bridge AI Agents to the Web at 85% Lower Token Cost & 10x Faster Execution
- **Team**: Hackateers
- **Target Audience**: AI Developers, Enterprise Automation Teams, & LLM System Architects

---

## Slide 2: Problem & Solution

### Why Do AI Agents Need Pidgey?

#### The Problem
- **Massive Token Waste**: Raw Web DOMs contain 50,000+ lines of scripts, CSS, and SVG noise.
- **High API Expenses**: Feeding full HTML into LLMs costs dollars per session.
- **Fragile Automation**: Browsers crash, network timeouts occur, and AI agents lose their state.
- **Slow Execution**: Launching a full Chromium browser for simple documentation reading is wasteful.

#### The Pidgey Solution
- **Intelligent Intermediate Layer**: Sits between AI Agents and the Web.
- **DOM Compression Engine**: Converts huge web pages into compact, interactive UI schemas.
- **Bypasses Browser Launches**: Reads `/llms.txt` specifications to fetch static docs directly.
- **Auto-Recovery**: Recovers from crashes automatically using versioned DOM checkpoints.

---

## Slide 3: Key Features (In Simple Words)

### Core Features Explained Simply

1. **Smart Web Shrinker (Token Compression)**:
   - Removes hidden code, ads, and styles, keeping ONLY buttons, text fields, links, and forms.
2. **Instant Memory Cache (Semantic Caching)**:
   - If an AI agent visits a page it saw before, Pidgey loads it instantly from a local database without re-rendering.
3. **No-Browser Fast Track (`llms.txt` Discovery)**:
   - For documentation and manuals, Pidgey downloads the text directly via HTTP without opening a heavy browser window.
4. **Crash Recovery (DOM Checkpointing)**:
   - Saves mini snapshots of the browser state so if a webpage or network crashes, the agent resumes right where it left off.
5. **AI Vision Fallback (VLM Integration)**:
   - If a page uses complex canvas graphics or CAPTCHAs, Pidgey takes a screenshot and uses AI Vision (Llama 3.2 Vision) to understand it.
6. **Live Mission Control Dashboard**:
   - A real-time web dashboard showing live screenshots, token savings, cost reductions, and session playback.

---

## Slide 4: System Architecture

### High-Level System Architecture

```text
+-----------------------------------------------------------------------+
|                              AI AGENTS                                |
|             (Claude Desktop, Antigravity, Cursor, LangChain)           |
+-----------------------------------------------------------------------+
                                   |
                                   v  (MCP Stdio Transport Protocol)
+-----------------------------------------------------------------------+
|                    PIDGEY: BROWSER OPTIMIZER MCP                      |
|                                                                       |
|  +--------------------+   +-------------------+   +----------------+  |
|  |  LLMS DISCOVERY    |   | RECOVERY MANAGER  |   | SEMANTIC CACHE |  |
|  | (Direct HTTP Fetch)|   | (DOM Checkpoints) |   | (Vector Embed) |  |
|  +--------------------+   +-------------------+   +----------------+  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |              PLAYWRIGHT CHROMIUM AUTOMATION ENGINE              |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                             THE WEB                                   |
|                (Web Applications, Documentation, APIs)                |
+-----------------------------------------------------------------------+
```

---

## Slide 5: Process Flow

### Step-by-Step Execution Lifecycle

1. **Agent Sends Request**:
   - The AI Agent requests to inspect a URL or click a button via MCP stdio tool call.
2. **Strategy Selection (Decision Engine)**:
   - Pidgey checks if the URL is static documentation (`llms.txt`) or a dynamic web application.
3. **Smart Routing**:
   - **Path A (Direct Fetch)**: Downloads raw markdown/HTML via HTTP -> Compresses -> Returns payload in milliseconds.
   - **Path B (Playwright Browser)**: Launches Chromium -> Intercepts DOM -> Strips noise -> Compresses UI elements.
4. **Cache & Checkpoint Recording**:
   - Saves a structural vector embedding in SQLite for instant cache hits next time.
   - Creates a versioned DOM checkpoint to protect against crash failures.
5. **Compressed Response to Agent**:
   - Returns a hyper-compressed JSON payload (up to 85% fewer tokens) back to the LLM.

---

## Slide 6: Complete MCP Tools Catalog (Part 1 - Core & Recovery)

### 28 Tools Exposed to AI Agents

#### Core Context & Browser Control (7 Tools)
- `extract_context`: Navigates to a URL and returns compressed interactive UI context.
- `execute_action`: Executes click, type, select, scroll, wait, or navigate actions.
- `page_diff`: Calculates added/removed DOM elements since previous visit.
- `summarize_page`: Generates a quick structural summary of the page.
- `classify_page`: Identifies page type (LOGIN, SEARCH, PRODUCT, CHECKOUT).
- `wait_until_ready`: Pauses until network load and DOM stabilize.
- `cache_lookup`: Queries local SQLite semantic cache directly.

#### DOM Checkpointing & Crash Recovery (5 Tools)
- `create_checkpoint`: Captures a versioned DOM snapshot and browser cookies.
- `load_latest_checkpoint`: Retrieves the most recent checkpoint for a session.
- `restore_checkpoint`: Restores browser state from a checkpoint after a crash.
- `compare_checkpoint`: Compares current DOM state against a stored checkpoint.
- `delete_session_checkpoints`: Purges stored checkpoints for a session.

---

## Slide 7: Complete MCP Tools Catalog (Part 2 - Discovery, Skills & Admin)

### 28 Tools Exposed to AI Agents (Continued)

#### LLM-Aware Website Discovery (`llms.txt`) (6 Tools)
- `discover_llms`: Discovers and parses `/llms.txt` specifications for a website.
- `parse_llms`: Parses raw Markdown text into structured documentation catalogs.
- `get_cached_llms`: Fetches cached discovery metadata for a host.
- `select_navigation_strategy`: Queries Decision Engine for strategy (DIRECT_FETCH vs PLAYWRIGHT).
- `fetch_documentation`: Downloads and compresses documentation pages without Playwright.
- `invalidate_llms_cache`: Clears stored discovery cache for a domain.

#### Automation, Skills, Monitoring & Dashboard (10 Tools)
- `start_macro_recording` & `save_macro`: Records action sequences into reusable skills.
- `list_skills`, `suggest_skill`, & `replay_skill`: Replays recorded automation macros with stateless resumption.
- `watch_page` & `stop_watch_page`: Streams live DOM changes via WebSocket.
- `get_session_replay`: Returns step-by-step action execution logs.
- `get_metrics`: Returns live token savings, cost reductions, and cache hit ratios.
- `open_dashboard`: Launches the Mission Control visual web dashboard.

---

## Slide 8: Users Benefitted

### Who Benefits from Pidgey?

- **AI Agent Developers**:
  - Build web-scraping and browser automation bots without managing complex Playwright scripts.
- **Enterprise Automation Teams**:
  - Reduce LLM API bills dramatically while processing thousands of automated tasks daily.
- **LLM Application Developers**:
  - Integrate Pidgey into Claude Desktop, Cursor, or custom LangChain setups in under 2 minutes via standard MCP stdio.
- **Web Researchers & Data Analysts**:
  - Extract structured UI controls, form fields, and documentation instantaneously without manual DOM inspection.

---

## Slide 9: Measurable Results & Impact

### Performance Metrics & Token Savings

- **85%+ Token Context Reduction**:
  - Raw HTML size reduced from ~500KB to ~15KB per page load.
- **Cost Savings**:
  - Saves an estimated $0.002+ per 1K tokens saved, adding up to massive savings across millions of agent tool calls.
- **10x Faster Documentation Inspection**:
  - `llms.txt` Direct Fetch bypasses browser boot time, returning results in under 200ms instead of 2500ms+.
- **Zero-Downtime Session Recovery**:
  - Automated DOM checkpoints achieve 95%+ confidence page restoration after browser process crashes.

---

## Slide 10: Future Enhancements

### Roadmap & Next Steps

1. **Multi-Browser Support**:
   - Add support for Firefox and WebKit browser drivers alongside Chromium.
2. **Distributed Distributed Cache**:
   - Upgrade local SQLite cache to Redis / Cloud Vector DB for shared enterprise team caching.
3. **Automated CAPTCHA Solver Integration**:
   - Expand Vision VLM fallback to auto-solve complex turnstile and hCaptcha challenges.
4. **Autonomous Skill Synthesis**:
   - Allow LLMs to automatically record, package, and publish macro skills to a public skill registry.
5. **Mobile Viewport Emulation**:
   - Provide mobile device viewport emulation and touch gesture action APIs.

---

## Slide 11: Conclusion

### Conclusion & Summary

- **Pidgey transforms AI Web Automation**:
  - Makes web agents faster, cheaper, and resilient against failures.
- **Production-Ready & Fully Verified**:
  - 100% test pass rate across 78 unit, integration, and protocol compliance test suites.
- **Plug-and-Play MCP Standard**:
  - Seamlessly compatible with Claude Desktop, Antigravity, Cursor, and any MCP-compliant AI client.

**Thank You!**
- **Repository**: https://github.com/Manthan-Railkar/Hackateers
- **Team**: Hackateers
