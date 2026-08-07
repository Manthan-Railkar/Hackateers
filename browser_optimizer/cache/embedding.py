import numpy as np
import xxhash
from bs4 import BeautifulSoup
from typing import List, Optional

class StructuralEmbedding:
    """
    Generates a 68-dimensional numerical feature vector from a DOM structure.
    1. Tag Vocabulary Histogram (30 dimensions)
    2. CSS Class Fingerprints (32 dimensions)
    3. DOM Depth Statistics (2 dimensions)
    4. Attribute Pattern Counts (4 dimensions)
    """

    COMMON_TAGS = [
        "div", "span", "p", "a", "button", "input", "form", "ul", "li", "ol",
        "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "td", "th",
        "select", "option", "textarea", "label", "img", "nav", "main", "header",
        "footer", "section"
    ]

    @classmethod
    def generate(cls, html: str) -> np.ndarray:
        soup = BeautifulSoup(html, "lxml")
        
        # 1. Tag Vocabulary Histogram (30 dims)
        tag_counts = np.zeros(30)
        for i, tag in enumerate(cls.COMMON_TAGS):
            tag_counts[i] = len(soup.find_all(tag))
            
        # 2. CSS Class Fingerprints (32 dims)
        class_buckets = np.zeros(32)
        for tag in soup.find_all(True):
            classes = tag.get("class", [])
            for c in classes:
                h = xxhash.xxh32(c.encode("utf-8")).intdigest() % 32
                class_buckets[h] += 1
                
        # 3. DOM Depth Statistics (2 dims)
        def get_depth(element, current_depth=0):
            if not hasattr(element, "children"):
                return current_depth
            children = [c for c in getattr(element, "children", []) if c.name is not None]
            if not children:
                return current_depth
            return max(get_depth(c, current_depth + 1) for c in children)

        max_depth = get_depth(soup)
        
        def sum_depth(element, current_depth=0):
            if not hasattr(element, "children"):
                return current_depth, 1
            children = [c for c in getattr(element, "children", []) if c.name is not None]
            if not children:
                return current_depth, 1
            total_d = current_depth
            total_n = 1
            for c in children:
                d, n = sum_depth(c, current_depth + 1)
                total_d += d
                total_n += n
            return total_d, total_n
            
        total_d, total_n = sum_depth(soup)
        mean_depth = total_d / max(total_n, 1)
        depth_stats = np.array([max_depth, mean_depth])

        # 4. Attribute Pattern Counts (4 dims)
        id_count = len(soup.find_all(id=True))
        name_count = len(soup.find_all(attrs={"name": True}))
        type_count = len(soup.find_all(attrs={"type": True}))
        placeholder_count = len(soup.find_all(attrs={"placeholder": True}))
        attr_counts = np.array([id_count, name_count, type_count, placeholder_count])

        # Concatenate features (30 + 32 + 2 + 4 = 68 dims)
        vector = np.concatenate([tag_counts, class_buckets, depth_stats, attr_counts])

        # 5. L2 Normalization
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
            
        return vector

    @staticmethod
    def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        if v1 is None or v2 is None:
            return 0.0
        return float(np.dot(v1, v2))
