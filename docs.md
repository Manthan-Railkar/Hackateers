# Browser Optimizer MCP Technical Documentation

## 1. System Architecture

The Browser Optimizer MCP is a production-grade, fault-tolerant middleware operating between AI Agent frameworks (via Model Context Protocol stdio transport) and Web Applications (via Playwright Chromium automation and HTTP direct fetch).

```text
                               +----------------------------------+
                               |            AI Agent              |
                               +----------------------------------+
                                                |
                                                v  (MCP Stdio Protocol)
                               +----------------------------------+
                               |   Browser Optimizer MCP Server   |
                               +----------------------------------+
                                                |
        +---------------------------------------+---------------------------------------+
        |                                       |                                       |
        v                                       v                                       v
+-----------------------+              +-----------------------+              +-----------------------+
|  LLMSDiscoveryManager |              |    RecoveryManager    |              |     SemanticCache     |
+-----------------------+              +-----------------------+              +-----------------------+
| - llms.txt Parser     |              | - Checkpoint Creator  |              | - xxhash Exact Match  |
| - Decision Engine     |              | - Failure Detector    |              | - Vector Embedding    |
| - Direct Fetch Engine |              | - Validation Scoring  |              | - Cosine Similarity   |
+-----------------------+              +-----------------------+              +-----------------------+
        |                                       |                                       |
        +---------------------------------------+---------------------------------------+
                                                |
                                                v
                               +----------------------------------+
                               |     BrowserManager (Playwright)  |
                               +----------------------------------+
                                                |
                                                v
                               +----------------------------------+
                               |     SQLite Cache & Store (DB)    |
                               +----------------------------------+
```

---

## 2. Core Subsystems

### 2.1 LLM-Aware Website Discovery (`llms.txt` Standard)

The discovery subsystem (`browser_optimizer/discovery/`) provides an intelligent optimization layer that checks whether a website exposes an `/llms.txt` specification before launching Playwright.

- **Parser (`LLMSParser`)**:
  Parses Markdown content conforming to the `llms.txt` standard. Strips HTML comments, resolves relative and absolute URLs against target hostnames, extracts metadata blockquotes, and categorizes links into structured sections: `documentation`, `api_reference`, `guides`, `tutorials`, `examples`, `openapi`, `changelog`, `repository`, `sitemap`, `quickstart`, `sdk`, `cli`.
- **Discovery Manager (`LLMSDiscoveryManager`)**:
  - Automatically queries `https://<domain>/llms.txt` and `https://www.<domain>/llms.txt`.
  - Supports HTTP conditional revalidation via `If-None-Match: <etag>` and `If-Modified-Since: <last_modified>` headers. On HTTP 304 Not Modified, extends cache TTL without re-downloading.
  - Stores discovery metadata in SQLite `llms_cache` table.
- **Intelligent Decision Engine**:
  - `select_navigation_strategy(url)` evaluates request characteristics:
    - **`DIRECT_FETCH`**: Selected for static documentation URLs listed in `llms.txt`, raw `.md`/`.txt`/`.json`/`.yaml` files, or static doc path patterns. Bypasses Playwright entirely.
    - **`PLAYWRIGHT`**: Selected for auth/login pages, forms, interactive dashboards, dynamic search, checkout, file uploads, and JS-heavy SPAs.
    - **`HYBRID`**: Selected for documentation pages containing dynamic interactive playground widgets.
- **Direct Fetch Engine**:
  - `direct_fetch(url)` downloads HTML via `httpx.AsyncClient` without opening a browser process. Passes HTML through `PageExtractor` and `DOMCompressor`, caches the semantic representation, records latency and browser launch savings, and returns compressed context payload.

### 2.2 DOM Checkpointing & Browser Recovery Framework

The recovery subsystem (`browser_optimizer/recovery/`) guarantees fault tolerance against browser process crashes, Playwright WebSocket disconnects, navigation timeouts, and network interruptions.

- **Deterministic DOM Hashing**:
  `compute_dom_hash()` normalizes DOM markup by stripping dynamic React IDs (`data-reactid`), CSRF tokens, script/style tags, non-semantic attributes, and whitespace. Computes an `xxhash` 64-bit digest in under 50ms.
- **Deduplicated Checkpointing**:
  `create_checkpoint()` extracts page state, scroll position (`window.scrollX`, `window.scrollY`), viewport dimensions, focused element, and compressed DOM. Skips saving if URL, page title, and DOM hash match the previous checkpoint.
- **Failure Detection**:
  `detect_failure(exception)` categorizes Playwright and network exceptions into recoverable types: `BROWSER_CLOSED`, `BROWSER_CRASH`, `WEBSOCKET_DISCONNECT`, `NAVIGATION_TIMEOUT`, `NETWORK_INTERRUPTION`.
- **State Validation & Confidence Scoring**:
  `calculate_recovery_confidence()` validates recovered live page state against stored checkpoint using a weighted scoring model (0.0 to 1.0):
  - URL match: 40 points
  - DOM Hash / Structural similarity match: 35 points
  - Page Title match: 15 points
  - Interactive element presence: 10 points
- **Automated Recovery & Auto-Resume**:
  `restore_checkpoint()` pauses execution, loads the latest checkpoint, re-initializes Playwright context with saved `storage_state`, re-navigates to the checkpoint URL, restores scroll position and element focus, extracts fresh live state, and auto-resumes if confidence >= `0.70` (configurable via `MINIMUM_RESUME_CONFIDENCE`).

### 2.3 Semantic Caching & Vector Embeddings

The caching subsystem (`browser_optimizer/cache/`) provides two-tier persistent caching in SQLite:

- **Tier 1 (Exact Hash Match)**:
  Computes `xxhash` digest of HTML. If match exists in SQLite `cache` table and confidence >= 0.3, returns cached compressed context instantly.
- **Tier 2 (Semantic Similarity Fallback)**:
  If exact hash misses, generates a structural vector embedding (`structural_embedding`) from HTML element tree tags and attributes. Scans cached embeddings using cosine similarity. If similarity >= `SIMILARITY_THRESHOLD` (0.90), returns cached context annotated with `semantic_match: True`.
- **Dynamic Confidence Scoring**:
  Adjusts cache entry confidence scores based on interaction success (+0.05 on success, -0.3 on failure). For entries with confidence between 0.3 and 0.7, verifies title match before reuse.

### 2.4 Multimodal Vision Fallback

For Canvas-heavy applications, CAPTCHAs, or complex SPAs lacking standard HTML interactive elements:

- `PageExtractor` counts interactive DOM elements (`button`, `input`, `select`, `a`, `form`).
- If interactive element count < `VISUAL_FALLBACK_THRESHOLD` (3), triggers `VisionAnalyzer`.
- Captures JPEG screenshot, encodes to base64, and queries Groq Llama 3.2 Vision model (`llama-3.2-11b-vision-preview`) to extract interactive UI bounding boxes and descriptions.

### 2.5 Macro Skills & MRTR Stateless Replay Handles

- `RuleBasedExecutor` records session-isolated action sequences (`start_macro_recording`, `stop_recording`).
- `MacroStore` saves parameterized macros in SQLite.
- `replay_skill()` executes recorded sequences with parameter injection.
- **MCP 2026-07-28 MRTR Compliance**:
  If a macro step fails, `replay_skill()` returns `resultType="input_required"` containing an opaque, base64-encoded `replay_handle` token encoding (`macro_id`, `next_step_index`, `parameters`, `session_id`). The client can execute the failed step manually and pass `replay_handle` back to resume execution from the correct step — requiring no server-side suspension state.

### 2.6 Mission Control Live Dashboard & Push Mode

- Serves an HTTP dashboard server on port 8050 (`/mission-control` and `/api/metrics`, `/api/telemetry`, `/api/screenshot`).
- `LiveScreenshotStore` captures JPEG screenshots in memory for live visual streaming.
- `watch_page()` spawns an `asyncio` task polling page diffs (`difference_engine`) and pushing real-time updates over WebSocket (`ws://localhost:8765`).

---

## 3. Database Schema Reference (`cache.db`)

SQLite database storing persistent application state:

### 3.1 `cache` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `key` | TEXT (PK) | Target URL string |
| `value` | TEXT (JSON) | Compressed context payload |
| `created_at` | REAL | UNIX timestamp |
| `ttl` | REAL | Time-to-live in seconds |
| `hit_count` | INTEGER | Access hit count |
| `embedding` | TEXT (JSON) | Structural vector embedding |
| `confidence` | REAL | Confidence score (0.0 to 1.0) |

### 3.2 `dom_checkpoints` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER (PK AUTO) | Primary key ID |
| `session_id` | TEXT | Session identifier |
| `url` | TEXT | Active page URL |
| `title` | TEXT | Page title |
| `compressed_dom` | TEXT (JSON) | Compressed UI representation |
| `dom_hash` | TEXT | Normalized DOM `xxhash` digest |
| `scroll_x` | INTEGER | Horizontal scroll position |
| `scroll_y` | INTEGER | Vertical scroll position |
| `viewport_width` | INTEGER | Viewport width in pixels |
| `viewport_height` | INTEGER | Viewport height in pixels |
| `focused_element` | TEXT | Active focused element selector |
| `timestamp` | REAL | UNIX creation timestamp |
| `version` | TEXT | Schema version ("1.0") |
| `metadata` | TEXT (JSON) | Action trigger & creation latency metadata |

### 3.3 `llms_cache` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `hostname` | TEXT (PK) | Target website domain |
| `fetched_at` | REAL | UNIX fetch timestamp |
| `expires_at` | REAL | UNIX expiration timestamp |
| `version` | TEXT | Discovered `llms.txt` version |
| `raw_content` | TEXT | Raw Markdown specification |
| `parsed_json` | TEXT (JSON) | Categorized discovery result |
| `etag` | TEXT | HTTP ETag header |
| `last_modified` | TEXT | HTTP Last-Modified header |

### 3.4 `session_states` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `session_id` | TEXT (PK) | Session identifier |
| `state_json` | TEXT (JSON) | Playwright `storage_state` (cookies, localStorage) |
| `updated_at` | REAL | UNIX update timestamp |

### 3.5 `session_replay` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER (PK AUTO) | Log entry ID |
| `session_id` | TEXT | Session identifier |
| `timestamp` | REAL | Event timestamp |
| `page_classification` | TEXT | Page category (LOGIN, SEARCH, etc.) |
| `action_taken` | TEXT | Action description |
| `confidence_used` | REAL | Confidence score used |
| `outcome` | TEXT | Action result / status |

### 3.6 `macros` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER (PK AUTO) | Macro ID |
| `name` | TEXT | Macro name |
| `page_type` | TEXT | Target page classification |
| `sequence` | TEXT (JSON) | Parameterized action steps |
| `confidence` | REAL | Skill confidence score |
| `success_count` | INTEGER | Successful replay count |
| `fail_count` | INTEGER | Failed replay count |

---

## 4. MCP Tool Reference

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `extract_context` | `url: str, session_id: str` | Navigates to URL, checks discovery engine for direct fetch, extracts and compresses DOM. |
| `execute_action` | `action: str, selector: str, value: str, session_id: str` | Executes browser action (click, type, fill, select, scroll, wait, navigate) with recovery retry. |
| `page_diff` | `url: str, session_id: str` | Computes DOM element deltas (added/removed) since previous URL observation. |
| `summarize_page` | `url: str, session_id: str` | Returns structural element counts and page snippet summary. |
| `classify_page` | `url: str, session_id: str` | Returns page category classification (LOGIN, PRODUCT, SEARCH, CHECKOUT, etc.). |
| `wait_until_ready` | `url: str, timeout: int, session_id: str` | Navigates and waits for network idle stabilization. |
| `cache_lookup` | `url: str, session_id: str` | Performs direct lookup in SQLite semantic cache. |
| `create_checkpoint` | `session_id: str, trigger: str` | Captures a versioned DOM checkpoint. |
| `load_latest_checkpoint` | `session_id: str` | Retrieves latest DOM checkpoint for a session. |
| `restore_checkpoint` | `session_id: str` | Triggers recovery restoration from latest checkpoint. |
| `compare_checkpoint` | `session_id: str, checkpoint_id: int` | Compares page state against a stored checkpoint. |
| `delete_session_checkpoints` | `session_id: str` | Purges stored checkpoints for a session. |
| `discover_llms` | `url: str, force_refresh: bool` | Discovers and parses `/llms.txt` specification for a website. |
| `parse_llms` | `markdown: str, base_url: str` | Parses raw Markdown string into structured catalog. |
| `get_cached_llms` | `hostname: str` | Retrieves stored `llms.txt` discovery cache record. |
| `select_navigation_strategy` | `url: str` | Returns decision engine strategy (`DIRECT_FETCH`, `PLAYWRIGHT`, `HYBRID`). |
| `fetch_documentation` | `url: str` | Downloads HTML directly without Playwright and returns compressed DOM context. |
| `invalidate_llms_cache` | `hostname: str` | Invalidates stored `llms.txt` cache entry. |
| `start_macro_recording` | `session_id: str` | Begins recording browser actions for skill macro creation. |
| `save_macro` | `name: str, page_type: str, parameters_map: dict, session_id: str` | Stops recording and saves parameterized skill macro. |
| `list_skills` | `page_type: str` | Lists recorded skill macros. |
| `suggest_skill` | `page_type: str` | Recommends highest confidence macro and routing strategy. |
| `replay_skill` | `macro_id: int, parameters: dict, expected_url: str, expected_page_type: str, session_id: str, replay_handle: str` | Replays recorded macro with MRTR stateless handle resumption. |
| `watch_page` | `url: str, interval_seconds: int, session_id: str` | Starts background WebSocket poller streaming live DOM diffs. |
| `stop_watch_page` | `session_id: str` | Stops background WebSocket page watching task. |
| `get_session_replay` | `session_id: str` | Retrieves append-only action log for a session. |
| `get_metrics` | None | Returns real-time token savings, cost estimates, cache ratios, and discovery stats. |
| `open_dashboard` | None | Launches Mission Control live dashboard in user's default browser. |

---

## 5. Configuration Reference (`Settings`)

Configured via environment variables in `.env`:

| Setting | Default | Description |
| :--- | :--- | :--- |
| `LOG_LEVEL` | `"INFO"` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `HEADLESS` | `True` | Run Chromium in headless mode |
| `CACHE_ENABLED` | `True` | Enable persistent SQLite semantic caching |
| `CACHE_TTL` | `300` | Semantic cache entry TTL in seconds |
| `CACHE_MAX_SIZE` | `100` | Max entries in cache |
| `BROWSER_TIMEOUT` | `30000` | Default Playwright page timeout in ms |
| `SIMILARITY_THRESHOLD` | `0.90` | Cosine similarity threshold for semantic cache hits |
| `CLASSIFICATION_THRESHOLD` | `0.65` | Confidence threshold for page classifier |
| `WEBSOCKET_HOST` | `"localhost"` | Host for WebSocket push server |
| `WEBSOCKET_PORT` | `8765` | Port for WebSocket push server |
| `DASHBOARD_PORT` | `8050` | Port for Mission Control HTTP dashboard |
| `AUTO_OPEN_DASHBOARD` | `True` | Automatically open dashboard in browser |
| `VISUAL_FALLBACK_THRESHOLD` | `3` | Minimum interactive elements before triggering VLM |
| `GROQ_VISION_MODEL` | `"llama-3.2-11b-vision-preview"` | Vision model for screenshot fallback |
| `ENABLE_CHECKPOINTING` | `True` | Enable DOM Checkpointing & Recovery |
| `MAX_CHECKPOINTS` | `20` | Maximum stored checkpoints per session |
| `CHECKPOINT_INTERVAL` | `1000` | Checkpoint interval in ms |
| `CHECKPOINT_RETENTION_DAYS` | `7` | Days to keep checkpoints |
| `MINIMUM_RESUME_CONFIDENCE` | `0.70` | Confidence score required for auto-resume |
| `ASYNC_CHECKPOINTING` | `True` | Save checkpoints asynchronously |
| `ENABLE_LLMS_DISCOVERY` | `True` | Enable `/llms.txt` discovery subsystem |
| `LLMS_CACHE_TTL` | `86400` | Discovery cache TTL in seconds (24 hours) |
| `ENABLE_DIRECT_FETCH` | `True` | Enable Playwright-bypassing direct fetch |
| `FALLBACK_TO_BROWSER` | `True` | Fallback to Playwright if direct fetch fails |
| `ALLOW_HYBRID_NAVIGATION` | `True` | Allow hybrid navigation for interactive docs |
| `MAX_LLMS_SIZE` | `1048576` | Max size for `llms.txt` files (1MB) |
