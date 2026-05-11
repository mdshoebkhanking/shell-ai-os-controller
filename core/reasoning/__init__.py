"""Transparent decision summaries and adaptive reasoning profiles."""

from .engine import AdaptiveReasoningEngine, ReasoningDepth, ReasoningProfile
from .explanations import DecisionExplanation, explain_failure, explain_tool_choice

__all__ = [
    "AdaptiveReasoningEngine",
    "DecisionExplanation",
    "ReasoningDepth",
    "ReasoningProfile",
    "explain_failure",
    "explain_tool_choice",
]

