import numpy as np
import pytest
from browser_optimizer.cache.embedding import StructuralEmbedding
from browser_optimizer.cache.cache import SemanticCache
from browser_optimizer.cache.db import init_db
from browser_optimizer.schemas.schemas import CompressedContext, UIElement


@pytest.fixture
def test_cache_db(tmp_path):
    db_file = tmp_path / "test_cache_part4.db"
    init_db(str(db_file))
    return str(db_file)


def test_structural_embedding_dimensions_and_normalization():
    sample_html = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <div id="container" class="main flex p-4">
                <h1>Title</h1>
                <p>Hello world paragraph</p>
                <form action="/submit">
                    <input type="text" name="username" placeholder="Username" />
                    <input type="password" name="password" placeholder="Password" />
                    <button type="submit" class="btn btn-primary">Login</button>
                </form>
            </div>
        </body>
    </html>
    """
    vector = StructuralEmbedding.generate(sample_html)
    
    # 1. Dimensions check: 30 (tag vocab) + 32 (CSS hash buckets) + 2 (DOM depth) + 4 (attributes) = 68
    assert isinstance(vector, np.ndarray)
    assert len(vector) == 68
    
    # 2. L2 Normalization check: ||vector||_2 == 1.0
    norm = np.linalg.norm(vector)
    assert pytest.approx(norm, 1e-5) == 1.0


def test_cosine_similarity():
    sample_html_1 = "<html><body><div><p>Test</p><button id='btn1'>Submit</button></div></body></html>"
    sample_html_2 = "<html><body><div><p>Another Test</p><button id='btn2'>Submit Form</button></div></body></html>"
    sample_html_3 = "<html><body><table><tr><td>Data 1</td><td>Data 2</td></tr></table></body></html>"
    
    v1 = StructuralEmbedding.generate(sample_html_1)
    v2 = StructuralEmbedding.generate(sample_html_2)
    v3 = StructuralEmbedding.generate(sample_html_3)
    
    # Identical vector similarity should be 1.0
    sim_self = StructuralEmbedding.cosine_similarity(v1, v1)
    assert pytest.approx(sim_self, 1e-5) == 1.0
    
    # Structurally similar pages (v1 and v2) should have high similarity
    sim_similar = StructuralEmbedding.cosine_similarity(v1, v2)
    assert sim_similar >= 0.80
    
    # Structurally distinct pages (v1 vs v3) should have lower similarity
    sim_different = StructuralEmbedding.cosine_similarity(v1, v3)
    assert sim_similar > sim_different


def test_semantic_cache_tier1_exact_match(test_cache_db):
    cache = SemanticCache(test_cache_db)
    
    sample_html = "<html><body><button id='b1'>Click</button></body></html>"
    url = "https://example.com/test"
    
    ui_item = UIElement(tag="button", text="Click", id="b1", selector="#b1")
    context = CompressedContext(
        ui=[ui_item],
        url=url,
        title="Test",
        raw_html_length=len(sample_html),
        compressed_length=50,
        compression_ratio=50.0
    )
    
    # Set cache entry
    key = cache.set(url, sample_html, context, page_type="TEST", confidence=1.0)
    assert key != ""
    
    # Tier 1 Exact Lookup
    hit_context, is_semantic, confidence = cache.get(url, sample_html)
    assert hit_context is not None
    assert is_semantic is False  # Tier 1 Exact Match
    assert confidence == 1.0
    assert hit_context.url == url
    assert len(hit_context.ui) == 1
    assert hit_context.ui[0].id == "b1"


def test_semantic_cache_tier2_semantic_match(test_cache_db):
    cache = SemanticCache(test_cache_db)
    
    # Cached Page Layout A
    html_cached = """
    <html><body>
        <div class="login-box">
            <input type="text" name="user" placeholder="Enter user" />
            <input type="password" name="pass" placeholder="Enter pass" />
            <button id="submit">Login</button>
        </div>
    </body></html>
    """
    url_cached = "https://app.example.com/login"
    
    context_cached = CompressedContext(
        ui=[UIElement(tag="button", text="Login", id="submit")],
        url=url_cached,
        title="Login Page",
        raw_html_length=len(html_cached),
        compressed_length=100,
        compression_ratio=80.0
    )
    
    cache.set(url_cached, html_cached, context_cached, page_type="LOGIN", confidence=1.0)
    
    # Query Page Layout B (Structurally identical template with minor text diffs)
    html_query = """
    <html><body>
        <div class="login-box">
            <input type="text" name="user" placeholder="Username" />
            <input type="password" name="pass" placeholder="Password" />
            <button id="submit">Sign In</button>
        </div>
    </body></html>
    """
    url_query = "https://app.example.com/login?ref=123"
    
    # Query Tier 2 Match
    hit_context, is_semantic, similarity = cache.get(url_query, html_query)
    assert hit_context is not None
    assert is_semantic is True  # Tier 2 Semantic Match
    assert similarity >= 0.90
    assert hit_context.title == "Login Page"


def test_semantic_cache_confidence_decay_and_penalty(test_cache_db):
    cache = SemanticCache(test_cache_db)
    
    sample_html = "<html><body><button id='b1'>Action</button></body></html>"
    url = "https://example.com/action"
    
    context = CompressedContext(
        ui=[UIElement(tag="button", text="Action", id="b1")],
        url=url,
        raw_html_length=100,
        compressed_length=20,
        compression_ratio=80.0
    )
    
    cache.set(url, sample_html, context, confidence=0.50)
    
    # Reward (+0.05)
    new_conf = cache.update_confidence(sample_html, success=True)
    assert new_conf == 0.55
    
    # Penalty (-0.30)
    new_conf = cache.update_confidence(sample_html, success=False)
    assert new_conf == 0.25
    
    # Confidence < 0.30 should cause cache.get to skip/miss entry
    hit_context, is_semantic, conf = cache.get(url, sample_html)
    assert hit_context is None
