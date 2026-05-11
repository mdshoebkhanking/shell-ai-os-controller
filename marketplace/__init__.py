"""Sandboxed plugin marketplace primitives."""

from .automation_templates import AutomationTemplate, AutomationTemplateStep, AutomationTemplateValidator
from .registry import MarketplaceRegistry, PluginInstallRecord, VerificationResult

__all__ = [
    "AutomationTemplate",
    "AutomationTemplateStep",
    "AutomationTemplateValidator",
    "MarketplaceRegistry",
    "PluginInstallRecord",
    "VerificationResult",
]
