
import json
import os
import logging
from datetime import datetime
from collections import Counter
try:
    from shell_safe_executor import god_tier_tool as function_tool
except Exception:
    try:
        from livekit.agents import function_tool
    except Exception:
        def function_tool(func):
            return func

logger = logging.getLogger("PREDICTIVE_ENGINE")
HISTORY_FILE = "brain/data/user_history.json"

class PredictiveEngine:
    """
    The Prophet: Learns user habits and predicts needs.
    """
    def __init__(self):
        self._ensure_file()
        self.history = self._load_history()

    def _ensure_file(self):
        if not os.path.exists("brain/data"):
            os.makedirs("brain/data")
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w") as f:
                json.dump([], f)

    def _load_history(self):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def log_action(self, user_input: str, tool_used: str = None):
        """Logs a user interaction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "hour": datetime.now().hour,
            "input": user_input,
            "tool": tool_used
        }
        self.history.append(entry)
        # Keep last 1000 entries
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
            
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)

    def get_suggestion(self) -> str:
        """Analyzes history to suggest next action."""
        if not self.history:
            return "boss, I am ready to learn. Give me commands."
            
        current_hour = datetime.now().hour
        
        # Simple Frequency Analysis for current hour
        relevant_actions = [
            h["input"] for h in self.history 
            if h.get("hour") == current_hour
        ]
        
        if not relevant_actions:
            # Fallback to general frequent actions
            relevant_actions = [h["input"] for h in self.history]
            
        if relevant_actions:
            common = Counter(relevant_actions).most_common(1)
            action, count = common[0]
            if count > 2:
                return f"It is {current_hour}:00. Usually you ask to: '{action}'. Shall I proceed?"
        
        return "System Idle. Ready for instructions."

predictor = PredictiveEngine()

@function_tool
async def log_user_action_tool(user_input: str, tool_used: str = "unknown") -> str:
    """Logs user action for predictive learning."""
    predictor.log_action(user_input, tool_used)
    return "Action Logged."

@function_tool
async def get_proactive_suggestion_tool() -> str:
    """Gets a suggestion based on past habits."""
    return predictor.get_suggestion()
