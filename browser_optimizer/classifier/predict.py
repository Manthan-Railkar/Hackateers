import os
import pickle
import numpy as np
from typing import Dict, Tuple
from browser_optimizer.config.settings import get_settings
from browser_optimizer.utils.logger import logger

class PageClassifierPredictor:
    def __init__(self, models_dir: str = "models"):
        self.settings = get_settings()
        self.models_dir = models_dir
        self.model = None
        self.label_encoder = None
        self.feature_names = None
        self._load_models()
        
    def _load_models(self):
        try:
            model_path = os.path.join(self.models_dir, "page_classifier.pkl")
            le_path = os.path.join(self.models_dir, "label_encoder.pkl")
            
            if os.path.exists(model_path) and os.path.exists(le_path):
                with open(model_path, "rb") as f:
                    self.model = pickle.load(f)
                with open(le_path, "rb") as f:
                    self.label_encoder = pickle.load(f)
                logger.info("Loaded LightGBM models successfully.")
            else:
                logger.warning("LightGBM models not found. Will fallback to heuristic scoring.")
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            
    def predict(self, features: np.ndarray) -> Tuple[str, Dict[str, float]]:
        if self.model is None or self.label_encoder is None:
            return "unknown", {}
            
        try:
            probs = self.model.predict_proba([features])[0]
            max_prob = np.max(probs)
            pred_class = self.label_encoder.inverse_transform([np.argmax(probs)])[0]
            
            scores = {self.label_encoder.inverse_transform([i])[0]: float(p) for i, p in enumerate(probs)}
            
            if max_prob >= self.settings.CLASSIFICATION_THRESHOLD:
                return pred_class, scores
            return "unknown", scores
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return "unknown", {}
