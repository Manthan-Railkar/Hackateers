from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UIElement(BaseModel):
    """
    Structured representation of a interactive UI control element.
    """
    tag: str = Field(..., description="HTML tag name (e.g. button, input, a, select)")
    text: Optional[str] = Field(None, description="Visible text content or aria-label")
    id: Optional[str] = Field(None, description="DOM element id")
    name: Optional[str] = Field(None, description="Form input element name")
    placeholder: Optional[str] = Field(None, description="Input placeholder text")
    type: Optional[str] = Field(None, description="Input element type (e.g. text, submit, password)")
    href: Optional[str] = Field(None, description="Anchor link target URL")
    selector: Optional[str] = Field(None, description="Unique CSS or XPath selector")
    is_visible: bool = Field(True, description="Whether element is visible in viewport")
    attributes: Dict[str, str] = Field(default_factory=dict, description="Additional custom attributes")


class CompressedContext(BaseModel):
    """
    Compressed DOM context payload delivered to LLM Agent.
    """
    ui: List[UIElement] = Field(default_factory=list, description="Extracted interactive UI controls")
    ax_tree: Optional[str] = Field(None, description="Semantic ARIA snapshot tree")
    url: str = Field(..., description="Target webpage URL")
    title: Optional[str] = Field(None, description="Webpage title")
    text_content: Optional[str] = Field(None, description="Cleaned body text content (max 2000 chars)")
    raw_html_length: int = Field(0, description="Length of uncompressed raw HTML string in bytes")
    compressed_length: int = Field(0, description="Length of compressed JSON context string in bytes")
    compression_ratio: float = Field(0.0, description="Percentage of tokens/bytes saved (0.0 to 100.0)")


class ClassificationResult(BaseModel):
    """
    Page classification output produced by ML model or heuristics.
    """
    page_type: str = Field(..., description="Categorized page type (e.g. LOGIN, SEARCH, CHECKOUT)")
    scores: Dict[str, float] = Field(default_factory=dict, description="Confidence scores per category")
    confidence: float = Field(0.0, description="Top predicted class confidence score (0.0 to 1.0)")
    is_heuristic_fallback: bool = Field(False, description="Whether rule-based heuristic fallback was used")


class PageDiff(BaseModel):
    """
    Delta state difference between consecutive page observations.
    """
    url: str = Field(..., description="Page URL where diff was observed")
    added: List[UIElement] = Field(default_factory=list, description="Newly appeared UI elements")
    removed: List[UIElement] = Field(default_factory=list, description="Disappeared UI elements")
    changed: List[Dict[str, Any]] = Field(default_factory=list, description="Modified UI element attributes")


class ActionRequest(BaseModel):
    """
    Browser interaction request payload.
    """
    action: str = Field(..., description="Action type (click, fill, select, scroll, navigate)")
    selector: Optional[str] = Field(None, description="Target DOM selector for action")
    value: Optional[str] = Field(None, description="Text value to fill or option to select")
    session_id: str = Field("default", description="Browser session context identifier")


class ActionResult(BaseModel):
    """
    Execution outcome payload for a browser action.
    """
    success: bool = Field(..., description="Whether action executed successfully")
    message: str = Field(..., description="Status message or summary of action")
    error: Optional[str] = Field(None, description="Error detail if action failed")
    session_id: str = Field("default", description="Session identifier")
    state_diff: Optional[PageDiff] = Field(None, description="State diff observed after action")


class MacroStep(BaseModel):
    """
    Single step execution model within a macro skill pipeline.
    """
    action: str = Field(..., description="Interaction type (click, fill, select)")
    selector: str = Field(..., description="Target element selector")
    value: Optional[str] = Field(None, description="Value or parameter placeholder")
    verification_selector: Optional[str] = Field(None, description="DOM element to check post-action")
    verification_type: Optional[str] = Field(None, description="Verification rule (exists, visible, text_matches)")


class MacroSkill(BaseModel):
    """
    Recorded dynamic macro skill automation sequence.
    """
    macro_id: str = Field(..., description="Unique macro identifier")
    name: str = Field(..., description="Human-readable macro name")
    steps: List[MacroStep] = Field(default_factory=list, description="Ordered sequence of macro steps")
    parameters: List[str] = Field(default_factory=list, description="Parametrized variable keys")
    created_at: str = Field(..., description="ISO creation timestamp")
    confidence_score: float = Field(1.0, description="Dynamic confidence score (0.0 to 1.0)")
