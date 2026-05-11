
from brain.learning.core import learning_core
from datetime import datetime

class PredictionEngine:
    """
    Predicts next user action based on learned patterns.
    """
    def predict_next_action(self) -> str:
        current_hour = str(datetime.now().hour)
        patterns = learning_core.patterns.get("hourly_habits", {})
        
        # 1. Check Hourly Habit
        if current_hour in patterns:
            likely_action = patterns[current_hour]
            return f"🔮 **Omni-Prediction:** boss, meri calculation ke hisaab se abhi aap '{likely_action}' karne wale hain. Kya main isey aapke liye auto-execute kar doon?"
            
        return "🔮 **Omni-Prediction:** boss, abhi mere neural cortex mein is waqt ke liye koi exact pattern set nahi hai. Par main aapke har command se seekh raha hoon!"

predictor = PredictionEngine()
