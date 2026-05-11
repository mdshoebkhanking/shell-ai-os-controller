
from brain.learning.core import learning_core
from datetime import datetime, timedelta

class FuturePredictorLite:
    """
    Zero-Dependency Future Predictor.
    Uses basic trend analysis on interaction history.
    """
    def predict_productivity(self) -> str:
        """Forecasts activity for the next week based on history."""
        history = learning_core.history
        if not history: return "Not enough data to predict future trends."
        
        # Basic count per day
        daily_counts = {}
        for h in history:
            # timestamp "2023-10-10 10:10:10..."
            date = h.get("timestamp", "").split(" ")[0]
            daily_counts[date] = daily_counts.get(date, 0) + 1
            
        if not daily_counts: return "Insufficient data."

        # Simple average
        avg_activity = sum(daily_counts.values()) / len(daily_counts)
        
        # Trend
        sorted_dates = sorted(daily_counts.keys())
        last_3_days = sorted_dates[-3:]
        recent_avg = sum([daily_counts[d] for d in last_3_days]) / len(last_3_days) if last_3_days else avg_activity
        
        trend = "Stable"
        if recent_avg > avg_activity * 1.2: trend = "Increasing 📈"
        elif recent_avg < avg_activity * 0.8: trend = "Decreasing 📉"
        
        return f"🔮 Future Forecast:\n- Productivity Trend: {trend}\n- Expected Actions/Day: {int(recent_avg)}\n- Advice: Keep consistent!"

future_lite = FuturePredictorLite()
