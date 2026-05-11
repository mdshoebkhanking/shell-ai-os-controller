"""Enterprise configuration contracts for Shell AI.

This package is additive. Legacy callers can keep using ``shell_config`` while
new runtime code can consume profile-aware, redacted, validation-friendly
configuration snapshots from here.
"""

from .profiles import (
    ConfigIssue,
    ConfigIssueLevel,
    ConfigProfile,
    EnterpriseConfig,
    ValidationReport,
    build_effective_config,
    profile_defaults,
    redact_value,
    validate_environment,
)

__all__ = [
    "ConfigIssue",
    "ConfigIssueLevel",
    "ConfigProfile",
    "EnterpriseConfig",
    "ValidationReport",
    "build_effective_config",
    "profile_defaults",
    "redact_value",
    "validate_environment",
]
