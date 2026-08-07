from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class UIElement(BaseModel):
    tag: str
    text: str
    id: Optional[str] = None
    name: Optional[str] = None
    placeholder: Optional[str] = None
    type: Optional[str] = None
    href: Optional[str] = None

class CompressedContext(BaseModel):
    ui: List[UIElement]
    ax_tree: Optional[Any] = None
    url: str
    title: str
    text_content: str
    raw_html_length: int
    compressed_length: int
    compression_ratio: float

class ClassificationResult(BaseModel):
    page_type: str
    scores: Dict[str, float]

class PageDiff(BaseModel):
    url: str
    added: List[UIElement] = Field(default_factory=list)
    removed: List[UIElement] = Field(default_factory=list)
    changed: List[Dict[str, Any]] = Field(default_factory=list)

class ActionRequest(BaseModel):
    action: str  # click, type, select, wait, scroll, navigate
    selector: Optional[str] = None
    value: Optional[str] = None

class ActionResult(BaseModel):
    success: bool
    message: str
    url: Optional[str] = None

class CacheEntry(BaseModel):
    url: str
    compressed_context: Dict[str, Any]
    timestamp: float


# ─────────────────────────────────────────────────────────────
# MCP 2026-07-28 Protocol Models
# ─────────────────────────────────────────────────────────────

class MCPResultMeta(BaseModel):
    """Metadata block injected into every MCP tool result under the `_meta` key."""
    resultType: str = "complete"  # "complete" | "input_required"
    ttlMs: Optional[int] = None
    cacheScope: Optional[str] = None  # "public" | "private"


class InputRequiredQuestion(BaseModel):
    """A single question the server asks the client during an MRTR flow."""
    id: str
    description: str
    type: str = "confirmation"  # "confirmation" | "text" | "choice"
    options: Optional[List[str]] = None


class ReplayHandlePayload(BaseModel):
    """
    Encoded into an opaque replay_handle token for stateless MRTR replay resumption.
    The client passes this handle back to replay_skill to resume from the correct step.
    """
    macro_id: int
    next_step_index: int
    parameters: Dict[str, str]
    session_id: str = "default"


# ─────────────────────────────────────────────────────────────
# DOM Checkpointing & Recovery Models
# ─────────────────────────────────────────────────────────────

class DOMCheckpoint(BaseModel):
    """
    Strongly typed DOM Checkpoint model capturing page state, compressed DOM,
    scroll position, viewport metrics, and element focus.
    """
    checkpoint_id: Optional[int] = None
    session_id: str = "default"
    timestamp: float
    url: str
    page_title: str
    compressed_dom: Dict[str, Any]
    dom_hash: str
    scroll_x: int = 0
    scroll_y: int = 0
    viewport_width: int = 1280
    viewport_height: int = 720
    focused_element: Optional[str] = None
    browser_context_id: Optional[str] = None
    page_identifier: Optional[str] = None
    checkpoint_version: str = "1.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryConfidenceResult(BaseModel):
    """
    Validation breakdown and confidence scoring produced during page state recovery.
    """
    confidence: float  # 0.0 to 1.0 (0 to 100%)
    status: str        # "EXACT_MATCH" | "HIGH_CONFIDENCE" | "PARTIAL_MATCH" | "MISMATCH"
    reason: str
    can_auto_resume: bool
    differences: Dict[str, Any] = Field(default_factory=dict)
    breakdown: Dict[str, float] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# LLM-Aware Discovery (llms.txt) Models
# ─────────────────────────────────────────────────────────────

class LLMSSectionItem(BaseModel):
    title: str
    url: str
    description: Optional[str] = None


class LLMSDiscoveryResult(BaseModel):
    supported: bool = False
    version: Optional[str] = None
    documentation: List[LLMSSectionItem] = Field(default_factory=list)
    api_reference: List[LLMSSectionItem] = Field(default_factory=list)
    guides: List[LLMSSectionItem] = Field(default_factory=list)
    tutorials: List[LLMSSectionItem] = Field(default_factory=list)
    examples: List[LLMSSectionItem] = Field(default_factory=list)
    openapi: List[LLMSSectionItem] = Field(default_factory=list)
    changelog: List[LLMSSectionItem] = Field(default_factory=list)
    repository: Optional[str] = None
    sitemap: Optional[str] = None
    raw_markdown: str = ""
    discovered_urls: List[str] = Field(default_factory=list)


class NavigationStrategyResult(BaseModel):
    strategy: str  # "DIRECT_FETCH" | "PLAYWRIGHT" | "HYBRID"
    reason: str
    confidence: float

