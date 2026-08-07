from browser_optimizer.schemas.schemas import (
    UIElement,
    CompressedContext,
    ClassificationResult,
    PageDiff,
    ActionRequest,
    ActionResult,
    MacroStep,
    MacroSkill,
)


def test_ui_element_schema():
    element = UIElement(
        tag="button",
        text="Submit Form",
        id="btn-submit",
        type="submit",
        selector="#btn-submit"
    )
    assert element.tag == "button"
    assert element.text == "Submit Form"
    assert element.id == "btn-submit"
    assert element.is_visible is True


def test_compressed_context_schema():
    ui_item = UIElement(tag="input", text="Search", id="search-input")
    context = CompressedContext(
        ui=[ui_item],
        ax_tree="button 'Search'",
        url="https://example.com",
        title="Example",
        text_content="Clean body text",
        raw_html_length=1000,
        compressed_length=100,
        compression_ratio=90.0
    )
    assert context.url == "https://example.com"
    assert len(context.ui) == 1
    assert context.compression_ratio == 90.0


def test_classification_result_schema():
    result = ClassificationResult(
        page_type="LOGIN",
        confidence=0.95,
        scores={"LOGIN": 0.95, "DASHBOARD": 0.05},
        is_heuristic_fallback=False
    )
    assert result.page_type == "LOGIN"
    assert result.confidence == 0.95


def test_page_diff_schema():
    added_el = UIElement(tag="div", text="New Notification")
    removed_el = UIElement(tag="button", text="Old Button")
    diff = PageDiff(
        url="https://example.com",
        added=[added_el],
        removed=[removed_el]
    )
    assert len(diff.added) == 1
    assert len(diff.removed) == 1


def test_action_request_and_result():
    req = ActionRequest(action="click", selector="#btn", session_id="user_1")
    assert req.action == "click"
    assert req.session_id == "user_1"

    res = ActionResult(success=True, message="Clicked button", session_id="user_1")
    assert res.success is True
    assert res.error is None


def test_macro_schemas():
    step = MacroStep(
        action="click",
        selector="#login-btn",
        verification_selector="#dashboard",
        verification_type="visible"
    )
    macro = MacroSkill(
        macro_id="macro_001",
        name="Login Flow",
        steps=[step],
        parameters=["username", "password"],
        created_at="2026-08-07T12:00:00Z",
        confidence_score=1.0
    )
    assert macro.macro_id == "macro_001"
    assert len(macro.steps) == 1
    assert macro.steps[0].action == "click"
