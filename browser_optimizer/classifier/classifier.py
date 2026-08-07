from typing import Dict, Tuple
import numpy as np
from bs4 import BeautifulSoup
from browser_optimizer.classifier.feature_extractor import FeatureExtractor
from browser_optimizer.classifier.predict import PageClassifierPredictor
from browser_optimizer.utils.logger import logger

class TaskClassifier:
    def __init__(self):
        self.predictor = PageClassifierPredictor()
        
    def classify(self, html: str, url: str) -> Tuple[str, Dict[str, float]]:
        features = FeatureExtractor.extract_features(html, url)
        page_type, scores = self.predictor.predict(features)
        
        if page_type == "unknown":
            logger.debug("ML classification unknown/failed. Falling back to rule-based heuristic scoring.")
            page_type = self._heuristic_fallback(html, url)
            
        return page_type, scores
        
    def _heuristic_fallback(self, html: str, url: str) -> str:
        url_lower = url.lower()
        soup = BeautifulSoup(html, "lxml")
        
        if "login" in url_lower or "signin" in url_lower:
            return "LOGIN"
        
        password_inputs = len(soup.find_all("input", type="password"))
        if password_inputs > 0:
            return "LOGIN"
            
        if "checkout" in url_lower or "cart" in url_lower:
            return "CHECKOUT"
            
        search_inputs = len(soup.find_all("input", type="search"))
        if search_inputs > 0 or "search" in url_lower:
            return "SEARCH"
            
        if "dashboard" in url_lower or "admin" in url_lower:
            return "DASHBOARD"
            
        return "UNKNOWN"
