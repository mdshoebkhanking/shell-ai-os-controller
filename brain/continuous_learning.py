"""
Shell AI — Continuous Learning Module
CorrectionLearner, BehaviorPatterns, SkillTracker, FeedbackLoop
All data persisted to brain/data/ as JSON.
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional
from collections import Counter

logger = logging.getLogger("shell_learning")

DATA_DIR = "brain/data"


# =============================================
# CorrectionLearner
# =============================================

class CorrectionLearner:
    """Detects when the user corrects Shell, records the correction,
    and provides past-correction context to avoid repeating mistakes."""

    CORRECTION_PATTERNS = [
        "no, i meant", "actually", "that's wrong", "not that", "incorrect",
        "wrong", "no no", "i said", "not what i asked", "try again",
        "that's not", "you misunderstood", "nahi", "galat", "sahi nahi"
    ]

    def __init__(self):
        self._corrections: List[Dict] = []
        self._data_path = os.path.join(DATA_DIR, "corrections.json")
        self._load()

    def _load(self):
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path, 'r', encoding='utf-8') as f:
                    self._corrections = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load corrections: {e}")
                self._corrections = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
            with open(self._data_path, 'w', encoding='utf-8') as f:
                json.dump(self._corrections, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save corrections: {e}")

    def detect_correction(self, user_msg: str, prev_assistant_msg: str = "") -> bool:
        """Returns True if the user message looks like a correction."""
        msg_lower = user_msg.lower()
        return any(p in msg_lower for p in self.CORRECTION_PATTERNS)

    def record_correction(self, original_response: str, correction: str, context: str = ""):
        """Record a correction event for future reference."""
        self._corrections.append({
            "original": original_response[:500],
            "correction": correction[:500],
            "context": context[:200],
            "timestamp": time.time()
        })
        if len(self._corrections) > 200:
            self._corrections = self._corrections[-200:]
        self._save()

    def get_correction_context(self, query: str) -> str:
        """Search past corrections for similar queries and return avoidance hint."""
        if not self._corrections:
            return ""
        query_words = set(query.lower().split())
        best_match = None
        best_score = 0
        for corr in self._corrections:
            context_words = set(corr.get("context", "").lower().split())
            orig_words = set(corr.get("original", "").lower().split())
            overlap = len(query_words & (context_words | orig_words))
            if overlap > best_score:
                best_score = overlap
                best_match = corr
        if best_match and best_score >= 2:
            return (
                f"Note: Previously you said '{best_match['original'][:100]}' "
                f"but the correct answer was '{best_match['correction'][:100]}'. "
                f"Avoid the same mistake."
            )
        return ""

    def get_stats(self) -> Dict:
        """Return correction statistics."""
        return {
            "total_corrections": len(self._corrections),
            "recent_5": self._corrections[-5:] if self._corrections else []
        }


# =============================================
# BehaviorPatterns
# =============================================

class BehaviorPatterns:
    """Tracks sequences of user actions and mines frequent n-gram patterns
    to predict what the user might do next."""

    def __init__(self):
        self._sequences: List[Dict] = []
        self._data_path = os.path.join(DATA_DIR, "behavior_patterns.json")
        self._patterns: Dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._sequences = data.get("sequences", [])
                    self._patterns = data.get("patterns", {})
            except Exception as e:
                logger.warning(f"Failed to load behavior patterns: {e}")
                self._sequences = []
                self._patterns = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
            with open(self._data_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "sequences": self._sequences,
                    "patterns": self._patterns
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save behavior patterns: {e}")

    def log_action(self, action_type: str, detail: str = ""):
        """Log a user action. Auto-mines patterns every 10 actions."""
        self._sequences.append({
            "type": action_type,
            "detail": detail,
            "timestamp": time.time()
        })
        if len(self._sequences) > 500:
            self._sequences = self._sequences[-500:]
        # Auto-mine every 10 actions
        if len(self._sequences) % 10 == 0:
            self._mine_ngrams()
            self._save()

    def _mine_ngrams(self):
        """Find frequent bigrams and trigrams in action sequences."""
        types = [s["type"] for s in self._sequences]
        bigrams: Counter = Counter()
        trigrams: Counter = Counter()
        for i in range(len(types) - 1):
            bigrams[f"{types[i]} -> {types[i+1]}"] += 1
        for i in range(len(types) - 2):
            trigrams[f"{types[i]} -> {types[i+1]} -> {types[i+2]}"] += 1
        self._patterns = {
            "top_bigrams": dict(bigrams.most_common(10)),
            "top_trigrams": dict(trigrams.most_common(5)),
            "total_actions": len(types)
        }

    def predict_next_action(self) -> Optional[str]:
        """Predict the most likely next action based on the last action."""
        if len(self._sequences) < 2:
            return None
        last_action = self._sequences[-1]["type"]
        # Find most common action after this one
        types = [s["type"] for s in self._sequences]
        followers: Counter = Counter()
        for i in range(len(types) - 1):
            if types[i] == last_action:
                followers[types[i + 1]] += 1
        if followers:
            return followers.most_common(1)[0][0]
        return None

    def get_patterns(self) -> Dict:
        """Return the mined patterns."""
        return self._patterns


# =============================================
# SkillTracker
# =============================================

class SkillTracker:
    """Tracks Shell's performance across different skill categories
    and identifies strengths and weaknesses."""

    SKILLS = [
        "CODING", "RESEARCH", "CREATIVE", "SYSTEM",
        "DATA", "SECURITY", "COMMUNICATION", "AUTOMATION"
    ]

    def __init__(self):
        self._skills: Dict[str, Dict] = {}
        self._data_path = os.path.join(DATA_DIR, "skill_tracker.json")
        self._load()

    def _load(self):
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path, 'r', encoding='utf-8') as f:
                    self._skills = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load skill tracker: {e}")
                self._skills = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
            with open(self._data_path, 'w', encoding='utf-8') as f:
                json.dump(self._skills, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save skill tracker: {e}")

    def record_attempt(self, skill: str, quality_score: float, success: bool):
        """Record a skill attempt with quality score (0.0-1.0) and success flag."""
        if skill not in self._skills:
            self._skills[skill] = {"attempts": 0, "successes": 0, "total_quality": 0.0}
        s = self._skills[skill]
        s["attempts"] += 1
        if success:
            s["successes"] += 1
        s["total_quality"] += quality_score
        s["avg_quality"] = round(s["total_quality"] / s["attempts"], 3)
        self._save()

    def get_weak_skills(self) -> List[str]:
        """Return skills with average quality below 0.5."""
        return [k for k, v in self._skills.items() if v.get("avg_quality", 1.0) < 0.5]

    def get_strong_skills(self) -> List[str]:
        """Return skills with average quality above 0.7."""
        return [k for k, v in self._skills.items() if v.get("avg_quality", 0) > 0.7]

    def get_improvement_report(self) -> str:
        """Generate a human-readable skill improvement report."""
        if not self._skills:
            return "No skill data yet."
        lines = ["Skill Improvement Report", "=" * 40]
        for skill, data in sorted(self._skills.items(), key=lambda x: -x[1].get("avg_quality", 0)):
            rate = data["successes"] / max(1, data["attempts"]) * 100
            lines.append(
                f"  {skill}: Quality={data.get('avg_quality', 0):.2f} "
                f"| Success={rate:.0f}% | Attempts={data['attempts']}"
            )
        return "\n".join(lines)

    def get_stats(self) -> Dict:
        """Return raw skill data."""
        return dict(self._skills)


# =============================================
# FeedbackLoop
# =============================================

class FeedbackLoop:
    """Collects and analyzes feedback on Shell's responses,
    tracking ratings per provider for quality optimization."""

    def __init__(self):
        self._feedback: List[Dict] = []
        self._data_path = os.path.join(DATA_DIR, "feedback.json")
        self._load()

    def _load(self):
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path, 'r', encoding='utf-8') as f:
                    self._feedback = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load feedback: {e}")
                self._feedback = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
            with open(self._data_path, 'w', encoding='utf-8') as f:
                json.dump(self._feedback, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")

    def process_feedback(self, response_id: str, rating: int, comment: str = "", provider: str = ""):
        """Record feedback for a response. Rating 1-5."""
        self._feedback.append({
            "response_id": response_id,
            "rating": rating,
            "comment": comment,
            "provider": provider,
            "timestamp": time.time()
        })
        if len(self._feedback) > 500:
            self._feedback = self._feedback[-500:]
        self._save()

    def get_provider_ratings(self) -> Dict[str, float]:
        """Average rating per provider."""
        ratings: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for f in self._feedback:
            p = f.get("provider", "unknown")
            ratings[p] = ratings.get(p, 0) + f.get("rating", 3)
            counts[p] = counts.get(p, 0) + 1
        return {p: round(ratings[p] / counts[p], 2) for p in ratings if counts[p] > 0}

    def get_feedback_stats(self) -> Dict:
        """Return aggregated feedback statistics."""
        if not self._feedback:
            return {"total": 0}
        all_ratings = [f["rating"] for f in self._feedback]
        return {
            "total": len(self._feedback),
            "avg_rating": round(sum(all_ratings) / len(all_ratings), 2),
            "positive": sum(1 for r in all_ratings if r >= 4),
            "negative": sum(1 for r in all_ratings if r <= 2)
        }


# =============================================
# ContinuousLearning Wrapper
# =============================================

class ContinuousLearning:
    """Unified access point for all learning subsystems."""

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.corrections = CorrectionLearner()
        self.behavior = BehaviorPatterns()
        self.skills = SkillTracker()
        self.feedback = FeedbackLoop()


continuous_learning = ContinuousLearning()
