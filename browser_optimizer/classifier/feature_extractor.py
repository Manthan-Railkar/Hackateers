import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import numpy as np

class FeatureExtractor:
    """
    Extracts 33 numerical features from a page context for ML classification.
    """
    
    KEYWORDS = ["login", "register", "search", "cart", "checkout", "payment", "profile", "add_to_cart"]
    
    @classmethod
    def extract_features(cls, html: str, url: str) -> np.ndarray:
        soup = BeautifulSoup(html, "lxml")
        features = []
        
        # 1-8. Tag counts
        features.append(len(soup.find_all("input")))
        features.append(len(soup.find_all("button")))
        features.append(len(soup.find_all("a")))
        features.append(len(soup.find_all("form")))
        features.append(len(soup.find_all("img")))
        features.append(len(soup.find_all(re.compile("^h[1-6]$"))))
        features.append(len(soup.find_all(["ul", "ol"])))
        features.append(len(soup.find_all("table")))
        
        # 9-12. Input types
        features.append(len(soup.find_all("input", type="password")))
        features.append(len(soup.find_all("input", type="email")))
        features.append(len(soup.find_all("input", type="checkbox")))
        features.append(len(soup.find_all("input", type="radio")))
        
        # 13-17. UI Indicators (binary)
        features.append(1.0 if soup.find(attrs={"type": "search"}) or soup.find(id=re.compile("search", re.I)) else 0.0)
        features.append(1.0 if soup.find(["nav"]) or soup.find(class_=re.compile("nav", re.I)) else 0.0)
        features.append(1.0 if soup.find("footer") else 0.0)
        features.append(1.0 if soup.find("aside") or soup.find(class_=re.compile("sidebar", re.I)) else 0.0)
        features.append(1.0 if soup.find(class_=re.compile("modal|dialog", re.I)) else 0.0)
        
        # 18-20. ARIA statistics
        features.append(len(soup.find_all(attrs={"aria-label": True})))
        features.append(len(soup.find_all(attrs={"role": "button"})))
        features.append(len(soup.find_all(attrs={"role": True})))
        
        # 21-28. Keyword frequencies in text
        text = soup.get_text().lower()
        for kw in cls.KEYWORDS:
            features.append(float(text.count(kw)))
            
        # 29-31. Form dimensions
        forms = soup.find_all("form")
        if forms:
            form_sizes = [len(f.find_all("input")) for f in forms]
            features.append(float(np.mean(form_sizes)))
            features.append(float(np.max(form_sizes)))
            features.append(sum(1 for f in forms if f.find(type="submit") or f.find("button")))
        else:
            features.append(0.0)
            features.append(0.0)
            features.append(0.0)
            
        # 32-33. Metadata lengths
        title = soup.title.string if soup.title else ""
        features.append(float(len(title) if title else 0))
        features.append(float(len(text)))
        
        return np.array(features, dtype=np.float32)
