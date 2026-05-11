
import os
import json
import logging
from collections import Counter
from datetime import datetime

logger = logging.getLogger("shell_learning")

DATA_DIR = "brain/data"
HISTORY_FILE = f"{DATA_DIR}/interaction_history.json"
PATTERNS_FILE = f"{DATA_DIR}/habits.json"

class LearningCore:
    """
    Self-Learning Module.
    Tracks user actions and mines simple association rules.
    """
    def __init__(self):
        self._ensure_dir()
        self.history = self._load_json(HISTORY_FILE, [])
        self.patterns = self._load_json(PATTERNS_FILE, {})

    def _ensure_dir(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r') as f: return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")
        return default

    def _save_json(self, path, data):
        try:
            with open(path, 'w') as f: json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save {path}: {e}")

    def log_interaction(self, action_type: str, detail: str, context: str = ""):
        """Logs user command/tool usage."""
        entry = {
            "timestamp": str(datetime.now()),
            "hour": datetime.now().hour,
            "action": action_type,
            "detail": detail,
            "context": context
        }
        self.history.append(entry)
        # Keep history manageable (last 1000)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
            
        self._save_json(HISTORY_FILE, self.history)
        
        # Trigger rudimentary learning
        if len(self.history) % 5 == 0:
            self._mine_patterns()

    def _mine_patterns(self):
        """Simple frequent pattern mining."""
        # Pattern 1: Hour -> Likely Action
        hour_actions = {}
        for h in self.history:
            hr = h.get("hour")
            act = h.get("action")
            if hr not in hour_actions: hour_actions[hr] = []
            hour_actions[hr].append(act)
            
        # Determine dominant action per hour
        hourly_habits = {}
        for hr, acts in hour_actions.items():
            counts = Counter(acts)
            most_common = counts.most_common(1)
            if most_common:
                action, count = most_common[0]
                if count > 3: # Threshold
                    hourly_habits[str(hr)] = action
                    
        self.patterns["hourly_habits"] = hourly_habits
        self._save_json(PATTERNS_FILE, self.patterns)
        logger.info(f"🧬 Mined Patterns: {len(hourly_habits)} hourly habits found.")

learning_core = LearningCore()
