#!/usr/bin/env python3
# =============================================================================
# Shell self-healing engine.
# =============================================================================
# Phoenix records failures, creates backups, can propose fixes, and can run
# verification before any patch is kept. Automatic source mutation remains
# disabled by default and must pass the same safety gates as evolution tools.
# =============================================================================

import os
import sys
import math
import importlib
import importlib.util
import logging
import traceback
import shutil
import json
import re
import time
import hashlib
import gzip
import ast
import inspect
import subprocess
import tempfile
import threading
import asyncio
import random
import statistics
import base64
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Callable, Union, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from contextlib import contextmanager, asynccontextmanager
from functools import wraps, lru_cache, cached_property
import urllib.request
import urllib.error
import urllib.parse
import socket
import platform
import psutil

# Optional: Advanced code analysis
try:
    import astor
    ASTOR_AVAILABLE = True
except ImportError:
    ASTOR_AVAILABLE = False

# Optional: Code quality
try:
    import pylint.epylint as pylint
    PYLINT_AVAILABLE = True
except ImportError:
    PYLINT_AVAILABLE = False

# Optional: Visualization
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Optional: ML for prediction
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Optional: Git integration
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

# Function tool
try:
    from shell_safe_executor import god_tier_tool as function_tool
    FUNCTION_TOOL_AVAILABLE = True
except ImportError:
    FUNCTION_TOOL_AVAILABLE = False
    def function_tool(func):
        return func

# =============================================================================
# 📊 ULTRA CONFIGURATION
# =============================================================================

class Config:
    """Ultra self-heal configuration."""
    
    # Paths
    PROJECT_ROOT = Path(__file__).parent
    BACKUP_DIR = PROJECT_ROOT / ".phoenix_backups"
    CLOUD_BACKUP_DIR = PROJECT_ROOT / ".phoenix_cloud_backups"
    FIX_HISTORY_FILE = PROJECT_ROOT / ".phoenix_history.json"
    ERROR_LOG_FILE = PROJECT_ROOT / ".phoenix_errors.json"
    ANALYTICS_FILE = PROJECT_ROOT / ".phoenix_analytics.json"
    CACHE_DIR = PROJECT_ROOT / ".phoenix_cache"
    PROFILES_DIR = PROJECT_ROOT / ".phoenix_profiles"
    DASHBOARD_FILE = PROJECT_ROOT / "phoenix_dashboard.html"
    
    # Limits (Increased for ultra mode)
    MAX_ERROR_LOG = 2000
    MAX_FIX_HISTORY = 5000
    MAX_BACKUPS_PER_FILE = 20
    MAX_CACHE_SIZE_MB = 500
    MAX_DASHBOARD_HISTORY = 1000
    
    # AI providers. Anthropic is intentionally not listed in public defaults.
    AI_PROVIDERS = [
        "groq",       # Fastest (primary)
        "gemini",     # Best for code
        "gpt4",       # Most accurate
        "perplexity", # Good research
        "deepseek",   # Code specialist
        "ollama",     # Local LLM
        "local",      # Rule-based fallback
    ]
    
    # Provider Priorities (by use case)
    PROVIDER_PRIORITY = {
        "quick_fix": ["groq", "gemini", "gpt4"],
        "complex_fix": ["gpt4", "gemini", "deepseek"],
        "security": ["gpt4", "gemini", "deepseek"],
        "optimization": ["gpt4", "gemini", "deepseek"],
        "offline": ["ollama", "local"],
    }
    
    # Retry Settings
    MAX_FIX_ATTEMPTS = 8  # Increased from 5
    RETRY_DELAY = 0.5
    FIX_TIMEOUT = 90  # Increased timeout
    
    # Testing (Enhanced)
    ENABLE_SYNTAX_CHECK = True
    ENABLE_IMPORT_CHECK = True
    ENABLE_UNIT_TESTS = True
    ENABLE_SECURITY_SCAN = True
    ENABLE_PERFORMANCE_TEST = True
    ENABLE_MEMORY_LEAK_CHECK = True
    
    # Safety (Enhanced)
    MAX_FILE_SIZE_MB = 10
    BACKUP_COMPRESSION = True
    AUTO_ROLLBACK = True
    SANDBOX_TESTING = True
    DRY_RUN_MODE = False  # Test fixes without applying
    
    # Monitoring (Real-time)
    ENABLE_REALTIME_MONITOR = True
    MONITOR_INTERVAL = 10  # seconds (reduced from 30)
    PREDICTIVE_MODE = True
    AUTO_FIX_MODE = False  # Auto-fix without prompt (dangerous)
    NOTIFY_ON_FIX = True
    
    # Performance
    ENABLE_PROFILING = True
    ENABLE_OPTIMIZATION = True
    BOTTLENECK_THRESHOLD_MS = 100
    
    # Git Integration
    ENABLE_GIT_INTEGRATION = True
    AUTO_COMMIT_FIXES = False
    GIT_BRANCH_PREFIX = "phoenix-fix/"
    
    # Cloud Backup
    ENABLE_CLOUD_BACKUP = False  # Enable when credentials set
    CLOUD_PROVIDER = "google_drive"  # google_drive, dropbox
    
    # Dashboard
    ENABLE_DASHBOARD = True
    DASHBOARD_PORT = 8080
    DASHBOARD_REFRESH_SEC = 30
    
    # ML Prediction
    ENABLE_ML_PREDICTION = SKLEARN_AVAILABLE
    PREDICTION_CONFIDENCE_THRESHOLD = 0.7
    
    # Logging
    LOG_LEVEL = logging.INFO
    LOG_FILE = "shell_phoenix.log"
    LOG_TO_CONSOLE = True
    LOG_JSON_FORMAT = True


# =============================================================================
# 🎯 ULTRA DATA CLASSES
# =============================================================================

class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    PREDICTED = "predicted"  # New: Predicted errors


class FixStatus(Enum):
    """Fix attempt status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    PARTIAL = "partial"
    AUTO_FIXED = "auto_fixed"  # New: Auto-fixed
    DRY_RUN = "dry_run"  # New: Dry run mode


class OptimizationType(Enum):
    """Code optimization types."""
    PERFORMANCE = "performance"
    MEMORY = "memory"
    READABILITY = "readability"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"


@dataclass
class ErrorRecord:
    """Enhanced error record."""
    id: str
    timestamp: datetime
    tool_name: str
    error_message: str
    traceback: str
    filepath: str
    line_number: int
    severity: ErrorSeverity
    error_type: str
    fixed: bool = False
    fix_attempts: int = 0
    metadata: Dict = field(default_factory=dict)
    predicted: bool = False  # ML prediction
    prediction_confidence: float = 0.0
    auto_fixed: bool = False
    git_commit: Optional[str] = None
    performance_impact: float = 0.0


@dataclass
class FixAttempt:
    """Enhanced fix attempt."""
    id: str
    error_id: str
    timestamp: datetime
    provider: str
    prompt: str
    response: str
    success: bool
    test_result: str
    duration: float
    backup_path: Optional[str] = None
    git_diff: Optional[str] = None
    performance_before: float = 0.0
    performance_after: float = 0.0
    lines_changed: int = 0
    confidence_score: float = 0.0


@dataclass
class BackupInfo:
    """Enhanced backup metadata."""
    filepath: str
    backup_path: str
    timestamp: datetime
    checksum: str
    size_bytes: int
    compressed: bool
    version: int
    cloud_synced: bool = False
    git_commit: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class HealthMetrics:
    """Enhanced health metrics."""
    total_files: int = 0
    healthy_files: int = 0
    broken_files: int = 0
    total_errors: int = 0
    fixed_errors: int = 0
    predicted_errors: int = 0
    fix_success_rate: float = 0.0
    avg_fix_time: float = 0.0
    total_backups: int = 0
    cloud_backups: int = 0
    uptime_seconds: float = 0.0
    last_check: Optional[datetime] = None
    total_optimizations: int = 0
    performance_improvement: float = 0.0
    security_issues_fixed: int = 0
    ml_predictions: int = 0
    ml_accuracy: float = 0.0


@dataclass
class PerformanceProfile:
    """Performance profile for a module."""
    filepath: str
    avg_execution_time: float = 0.0
    max_execution_time: float = 0.0
    call_count: int = 0
    memory_usage_mb: float = 0.0
    bottlenecks: List[Dict] = field(default_factory=list)
    optimization_suggestions: List[str] = field(default_factory=list)
    last_profiled: Optional[datetime] = None


@dataclass
class MLPrediction:
    """ML-based error prediction."""
    filepath: str
    error_type: str
    probability: float
    confidence: float
    predicted_line: int
    features: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# 🛡️ ULTRA SECURITY SCANNER
# =============================================================================

class UltraSecurityScanner:
    """Advanced security scanner with vulnerability detection."""
    
    # Enhanced dangerous patterns
    DANGEROUS_PATTERNS = [
        # Code execution
        (r'eval\s*\(', 'CRITICAL', 'Code execution via eval()'),
        (r'exec\s*\(', 'CRITICAL', 'Code execution via exec()'),
        (r'compile\s*\(', 'HIGH', 'Dynamic code compilation'),
        # System commands
        (r'os\.system\s*\(', 'CRITICAL', 'System command execution'),
        (r'subprocess\.call.*shell\s*=\s*True', 'CRITICAL', 'Shell injection risk'),
        (r'subprocess\.Popen.*shell\s*=\s*True', 'CRITICAL', 'Shell injection risk'),
        # Unsafe deserialization
        (r'pickle\.load', 'CRITICAL', 'Unsafe deserialization'),
        (r'marshal\.load', 'CRITICAL', 'Unsafe deserialization'),
        (r'yaml\.load\s*\([^)]*\)\s*$', 'HIGH', 'Unsafe YAML loading'),
        # SQL injection
        (r'execute\s*\([^,]+%', 'HIGH', 'SQL injection risk'),
        (r'raw\s*\([^,]+%', 'HIGH', 'SQL injection risk'),
        # Path traversal
        (r'open\s*\([^+]+%', 'MEDIUM', 'Path traversal risk'),
        # Hardcoded secrets
        (r'password\s*=\s*["\'][^"\']+["\']', 'HIGH', 'Hardcoded password'),
        (r'api_key\s*=\s*["\'][^"\']+["\']', 'HIGH', 'Hardcoded API key'),
        (r'secret\s*=\s*["\'][^"\']+["\']', 'HIGH', 'Hardcoded secret'),
        # Insecure random
        (r'random\.(random|randint|choice)\(', 'LOW', 'Insecure random (use secrets)'),
    ]
    
    # Security best practices
    BEST_PRACTICES = [
        (r'import\s+telnetlib', 'CRITICAL', 'Use SSH instead of Telnet'),
        (r'import\s+ftplib', 'HIGH', 'Use SFTP instead of FTP'),
        (r'http://', 'MEDIUM', 'Use HTTPS instead of HTTP'),
        (r'MD5|md5', 'MEDIUM', 'MD5 is cryptographically broken'),
        (r'SHA1|sha1', 'LOW', 'SHA1 is deprecated, use SHA256+'),
    ]
    
    @classmethod
    def scan_code(cls, code: str, filepath: str = "") -> List[Dict]:
        """Comprehensive security scan."""
        issues = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check dangerous patterns
            for pattern, severity, message in cls.DANGEROUS_PATTERNS:
                if re.search(pattern, line):
                    issues.append({
                        "line": i,
                        "severity": severity,
                        "type": "dangerous_pattern",
                        "pattern": pattern,
                        "message": message,
                        "code": line.strip()[:80],
                        "filepath": filepath
                    })
            
            # Check best practices
            for pattern, severity, message in cls.BEST_PRACTICES:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "line": i,
                        "severity": severity,
                        "type": "best_practice",
                        "message": message,
                        "code": line.strip()[:80],
                        "filepath": filepath
                    })
        
        # AST-based analysis
        try:
            tree = ast.parse(code)
            issues.extend(cls._ast_analysis(tree, filepath))
        except Exception:
            pass
        
        return issues
    
    @classmethod
    def _ast_analysis(cls, tree: ast.AST, filepath: str) -> List[Dict]:
        """AST-based security analysis."""
        issues = []
        
        for node in ast.walk(tree):
            # Check for hardcoded strings in sensitive contexts
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if any(s in target.id.lower() for s in ['password', 'secret', 'key', 'token']):
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                issues.append({
                                    "severity": "HIGH",
                                    "type": "hardcoded_secret",
                                    "message": f"Hardcoded value for {target.id}",
                                    "line": node.lineno,
                                    "filepath": filepath
                                })
        
        return issues
    
    @classmethod
    def calculate_security_score(cls, code: str) -> float:
        """Calculates security score (0-100)."""
        issues = cls.scan_code(code)
        
        if not issues:
            return 100.0
        
        # Weight by severity
        severity_weights = {
            "CRITICAL": 25,
            "HIGH": 15,
            "MEDIUM": 8,
            "LOW": 3
        }
        
        total_penalty = sum(
            severity_weights.get(issue["severity"], 5)
            for issue in issues
        )
        
        score = max(0, 100 - total_penalty)
        return score
    
    @classmethod
    def is_safe_fix(cls, original: str, fixed: str) -> Tuple[bool, str, float]:
        """Checks if fix improves or maintains security."""
        original_score = cls.calculate_security_score(original)
        fixed_score = cls.calculate_security_score(fixed)
        
        if fixed_score < original_score:
            return False, f"Security score decreased: {original_score} → {fixed_score}", fixed_score
        
        return True, f"Security score: {fixed_score}/100", fixed_score


# =============================================================================
# 📊 ULTRA CODE ANALYZER
# =============================================================================

class UltraCodeAnalyzer:
    """Advanced code analysis with optimization suggestions."""
    
    @classmethod
    def full_analysis(cls, code: str, filepath: str = "") -> Dict:
        """Comprehensive code analysis."""
        import math
        
        return {
            "metrics": cls.get_metrics(code),
            "complexity": cls.get_complexity(code),
            "smells": cls.find_code_smells(code),
            "optimizations": cls.suggest_optimizations(code),
            "security_score": UltraSecurityScanner.calculate_security_score(code),
            "maintainability_index": cls.calculate_maintainability_index(code)
        }
    
    @classmethod
    def get_metrics(cls, code: str) -> Dict:
        """Gets basic code metrics."""
        lines = code.split('\n')
        
        return {
            "total_lines": len(lines),
            "code_lines": sum(1 for l in lines if l.strip() and not l.strip().startswith('#')),
            "comment_lines": sum(1 for l in lines if l.strip().startswith('#')),
            "blank_lines": sum(1 for l in lines if not l.strip()),
            "functions": code.count('def '),
            "classes": code.count('class '),
            "imports": code.count('import ') + code.count('from '),
            "decorators": code.count('@'),
            "avg_line_length": statistics.mean([len(l) for l in lines]) if lines else 0,
            "max_line_length": max([len(l) for l in lines]) if lines else 0,
        }
    
    @classmethod
    def get_complexity(cls, code: str) -> Dict:
        """Calculates complexity metrics."""
        try:
            tree = ast.parse(code)
            
            functions = []
            total_complexity = 0
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    complexity = cls._calculate_cyclomatic(node)
                    functions.append({
                        "name": node.name,
                        "complexity": complexity,
                        "lines": node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    })
                    total_complexity += complexity
            
            return {
                "total_complexity": total_complexity,
                "avg_complexity": total_complexity / len(functions) if functions else 0,
                "max_complexity": max([f["complexity"] for f in functions]) if functions else 0,
                "functions": functions
            }
        
        except Exception:
            return {"error": "Could not parse"}
    
    @classmethod
    def _calculate_cyclomatic(cls, node: ast.FunctionDef) -> int:
        """Calculates cyclomatic complexity."""
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                 ast.With, ast.Assert, ast.comprehension)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    @classmethod
    def find_code_smells(cls, code: str) -> List[Dict]:
        """Finds code smells."""
        smells = []
        lines = code.split('\n')
        
        # Long lines
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                smells.append({
                    "type": "long_line",
                    "severity": "LOW",
                    "line": i,
                    "message": f"Line too long ({len(line)} chars)",
                    "suggestion": "Break into multiple lines"
                })
        
        # Long functions
        func_start = None
        func_name = None
        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                func_start = i
                func_name = line.strip()
            elif func_start and i - func_start > 50 and line.strip() and not line.startswith(' ' * 4):
                smells.append({
                    "type": "long_function",
                    "severity": "MEDIUM",
                    "line": func_start + 1,
                    "message": f"Function {func_name} too long ({i - func_start} lines)",
                    "suggestion": "Split into smaller functions"
                })
                func_start = None
        
        # Too many parameters
        for match in re.finditer(r'def\s+\w+\s*\(([^)]+)\)', code):
            params = match.group(1).split(',')
            if len(params) > 5:
                smells.append({
                    "type": "too_many_parameters",
                    "severity": "MEDIUM",
                    "line": code[:match.start()].count('\n') + 1,
                    "message": f"Too many parameters ({len(params)})",
                    "suggestion": "Use *args, **kwargs, or parameter object"
                })
        
        # Duplicate code (simple detection)
        line_counts = Counter(lines)
        for line, count in line_counts.items():
            if count > 3 and len(line.strip()) > 20:
                smells.append({
                    "type": "duplicate_code",
                    "severity": "MEDIUM",
                    "message": f"Duplicate code detected ({count} times)",
                    "suggestion": "Extract to function or constant"
                })
        
        return smells
    
    @classmethod
    def suggest_optimizations(cls, code: str) -> List[Dict]:
        """Suggests code optimizations."""
        suggestions = []
        
        # List comprehension vs loop
        if 'for ' in code and '.append(' in code:
            suggestions.append({
                "type": "performance",
                "message": "Consider using list comprehension",
                "example": "[x for x in iterable] instead of loop with append()"
            })
        
        # String concatenation in loop
        if re.search(r'for.*:\s*\n\s*.*\+=.*["\']', code):
            suggestions.append({
                "type": "performance",
                "message": "Use join() for string concatenation in loops",
                "example": "''.join(list) instead of s += str"
            })
        
        # Global lookups
        if code.count('len(') > 5:
            suggestions.append({
                "type": "performance",
                "message": "Cache len() in local variable for tight loops",
                "example": "n = len(items); for i in range(n)"
            })
        
        return suggestions
    
    @classmethod
    def calculate_maintainability_index(cls, code: str) -> float:
        """Calculates maintainability index (0-100)."""
        metrics = cls.get_metrics(code)
        complexity = cls.get_complexity(code)
        
        if "error" in complexity:
            return 50.0
        
        # Simplified maintainability formula
        halstead_volume = metrics['code_lines'] * 2  # Simplified
        avg_complexity = complexity.get('avg_complexity', 1)
        loc = metrics['total_lines']
        
        if loc == 0 or avg_complexity == 0:
            return 50.0
        
        mi = 171 - 5.2 * math.log(halstead_volume) - 0.23 * avg_complexity - 16.2 * math.log(loc)
        return max(0, min(100, mi * 100 / 171))  # Normalize to 0-100


# =============================================================================
# (CONTINUED IN NEXT PART DUE TO SIZE...)
# =============================================================================

# Note: This is Part 1 of the Ultra Mega Upgrade
# The file continues with more advanced features...

logger = logging.getLogger("shell_phoenix")


# =============================================================================
# 🚀 BASIC TOOL WRAPPERS (For Testing)
# =============================================================================

if not FUNCTION_TOOL_AVAILABLE:
    def function_tool(func):
        return func


@function_tool
async def ultra_self_health_check_tool() -> str:
    """
    🏥 ULTRA Health Check - Scans ALL modules with advanced analysis.
    
    Examples:
        - "Ultra health check"
        - "Full system scan"
    """
    try:
        healthy = 0
        broken = 0
        issues = []
        
        # Scan all Python files
        for py_file in Config.PROJECT_ROOT.glob("**/*.py"):
            if 'venv' in str(py_file) or '__pycache__' in str(py_file):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                compile(code, str(py_file), "exec")
                
                # Advanced analysis
                analysis = UltraCodeAnalyzer.full_analysis(code, str(py_file))
                
                if analysis.get('security_score', 100) < 50:
                    issues.append(f"⚠️ `{py_file.name}`: Low security score ({analysis['security_score']})")
                
                healthy += 1
                
            except SyntaxError as e:
                broken += 1
                issues.append(f"❌ `{py_file.name}` line {e.lineno}: {e.msg}")
            except Exception as e:
                broken += 1
                issues.append(f"⚠️ `{py_file.name}`: {e}")
        
        total = healthy + broken
        
        return (
            f"🏥 **ULTRA Health Check**\n\n"
            f"✅ Healthy: {healthy}/{total}\n"
            f"❌ Broken: {broken}\n"
            f"📊 Success Rate: {healthy/total*100:.1f}%\n\n"
            + ("\n".join(issues[:20]) if issues else "All systems operational! ✅")
        )
        
    except Exception as e:
        return f"❌ Error: {e}"


@function_tool
async def get_ultra_phoenix_stats_tool() -> str:
    """
    📊 Ultra Phoenix Statistics with advanced metrics.
    
    Examples:
        - "Ultra Phoenix stats"
        - "Show all metrics"
    """
    return (
        f"📊 **Ultra Phoenix Statistics**\n\n"
        f"🔧 Version: 1000000 (Ultra Mega)\n"
        f"🧠 AI Providers: {len(Config.AI_PROVIDERS)}\n"
        f"📁 Max Backups: {Config.MAX_BACKUPS_PER_FILE}\n"
        f"⏱️ Monitor Interval: {Config.MONITOR_INTERVAL}s\n"
        f"🔒 Security Scanner: {'✅' if Config.ENABLE_SECURITY_SCAN else '❌'}\n"
        f"📈 ML Prediction: {'✅' if Config.ENABLE_ML_PREDICTION else '❌'}\n"
        f"🌐 Cloud Backup: {'✅' if Config.ENABLE_CLOUD_BACKUP else '❌'}\n"
        f"📊 Dashboard: {'✅' if Config.ENABLE_DASHBOARD else '❌'}\n"
    )


# =============================================================================
# NEW MEGA TOOLS — EXPOSING HIDDEN POWER
# =============================================================================

@function_tool
async def security_scan_file_tool(filename: str) -> str:
    """
    Kisi bhi Python file ka deep security scan karta hai.
    Dangerous patterns (eval, exec, os.system), hardcoded secrets, best practice violations detect karta hai.
    Args:
        filename: File to scan (e.g., 'shell_system_god.py', 'agent.py')
    """
    try:
        filepath = Config.PROJECT_ROOT / filename
        if not filepath.exists():
            return f"--- SECURITY SCAN ---\nFile: {filename}\nStatus: FILE NOT FOUND"

        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()

        issues = UltraSecurityScanner.scan_code(code, filename)
        score = UltraSecurityScanner.calculate_security_score(code)

        report = [
            f"--- PHOENIX SECURITY SCAN ---",
            f"File: {filename}",
            f"Security Score: {score}/100",
            f"Issues Found: {len(issues)}",
            f"{'=' * 40}",
        ]

        if issues:
            # Group by severity
            by_severity = {}
            for issue in issues:
                sev = issue.get("severity", "UNKNOWN")
                by_severity.setdefault(sev, []).append(issue)

            severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            for sev in severity_order:
                items = by_severity.get(sev, [])
                if items:
                    emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")
                    report.append(f"\n{emoji} {sev} ({len(items)}):")
                    for item in items[:5]:
                        line = item.get("line", "?")
                        msg = item.get("message", "Unknown issue")
                        code_snippet = item.get("code", "")[:60]
                        report.append(f"  L{line}: {msg}")
                        if code_snippet:
                            report.append(f"       > {code_snippet}")
                    if len(items) > 5:
                        report.append(f"  ... aur {len(items) - 5} issues")
        else:
            report.append("\nNo security issues found! File is clean.")

        grade = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 50 else "D" if score >= 30 else "F"
        report.append(f"\nGrade: {grade}")
        report.append(f"Boss, '{filename}' ka security scan complete. Score: {score}/100 (Grade {grade})")

        return "\n".join(report)

    except Exception as e:
        return f"--- SECURITY SCAN ---\nStatus: ERROR\nError: {e}"


@function_tool
async def code_quality_tool(filename: str) -> str:
    """
    Complete code quality analysis — metrics, complexity, code smells, optimization suggestions, maintainability index.
    Kisi bhi file ki code quality ka full report deta hai.
    Args:
        filename: File to analyze (e.g., 'shell_browser_CTRL.py')
    """
    try:
        filepath = Config.PROJECT_ROOT / filename
        if not filepath.exists():
            return f"--- CODE QUALITY ---\nFile: {filename}\nStatus: FILE NOT FOUND"

        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()

        analysis = UltraCodeAnalyzer.full_analysis(code, filename)

        metrics = analysis.get("metrics", {})
        complexity = analysis.get("complexity", {})
        smells = analysis.get("smells", [])
        optimizations = analysis.get("optimizations", [])
        security_score = analysis.get("security_score", 0)
        maintainability = analysis.get("maintainability_index", 0)

        report = [
            f"--- PHOENIX CODE QUALITY REPORT ---",
            f"File: {filename}",
            f"{'=' * 45}",
            f"",
            f"[CODE METRICS]",
            f"  Total Lines: {metrics.get('total_lines', 0)}",
            f"  Code Lines: {metrics.get('code_lines', 0)}",
            f"  Comments: {metrics.get('comment_lines', 0)}",
            f"  Blank Lines: {metrics.get('blank_lines', 0)}",
            f"  Functions: {metrics.get('functions', 0)}",
            f"  Classes: {metrics.get('classes', 0)}",
            f"  Avg Line Length: {round(metrics.get('avg_line_length', 0), 1)}",
            f"  Max Line Length: {metrics.get('max_line_length', 0)}",
        ]

        if "error" not in complexity:
            report.extend([
                f"",
                f"[COMPLEXITY]",
                f"  Total Cyclomatic: {complexity.get('total_complexity', 0)}",
                f"  Average: {round(complexity.get('avg_complexity', 0), 1)}",
                f"  Max: {complexity.get('max_complexity', 0)}",
            ])
            funcs = complexity.get("functions", [])
            if funcs:
                top_complex = sorted(funcs, key=lambda x: -x["complexity"])[:5]
                report.append(f"  Top Complex Functions:")
                for fc in top_complex:
                    report.append(f"    {fc['name']}: complexity={fc['complexity']}, lines={fc.get('lines', '?')}")

        if smells:
            report.extend([
                f"",
                f"[CODE SMELLS] ({len(smells)})",
            ])
            for smell in smells[:8]:
                stype = smell.get("type", "unknown")
                msg = smell.get("message", "")
                suggestion = smell.get("suggestion", "")
                line = smell.get("line", "")
                line_str = f" (L{line})" if line else ""
                report.append(f"  [{stype.upper()}]{line_str} {msg}")
                if suggestion:
                    report.append(f"    Fix: {suggestion}")

        if optimizations:
            report.extend([
                f"",
                f"[OPTIMIZATION SUGGESTIONS] ({len(optimizations)})",
            ])
            for opt in optimizations:
                report.append(f"  [{opt.get('type', '')}] {opt.get('message', '')}")

        report.extend([
            f"",
            f"[SCORES]",
            f"  Security: {security_score}/100",
            f"  Maintainability: {round(maintainability, 1)}/100",
        ])

        overall = round((security_score + maintainability) / 2, 1)
        grade = "A+" if overall >= 90 else "A" if overall >= 80 else "B" if overall >= 70 else "C" if overall >= 50 else "D"
        report.append(f"  Overall: {overall}/100 (Grade {grade})")
        report.append(f"\nBoss, '{filename}' ka code quality report ready hai. Grade: {grade}")

        return "\n".join(report)

    except Exception as e:
        return f"--- CODE QUALITY ---\nStatus: ERROR\nError: {e}"


@function_tool
async def security_scan_all_tool() -> str:
    """
    Poore project ka security scan — saari Python files ka security score ek saath.
    Full project security audit karta hai ye tool.
    """
    try:
        results = []

        for py_file in sorted(Config.PROJECT_ROOT.glob("*.py")):
            if '__pycache__' in str(py_file):
                continue
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                score = UltraSecurityScanner.calculate_security_score(code)
                issues = UltraSecurityScanner.scan_code(code, py_file.name)
                critical = sum(1 for i in issues if i.get("severity") == "CRITICAL")
                high = sum(1 for i in issues if i.get("severity") == "HIGH")
                results.append((py_file.name, score, len(issues), critical, high))
            except Exception:
                results.append((py_file.name, -1, 0, 0, 0))

        # Sort by score ascending (worst first)
        results.sort(key=lambda x: x[1])

        avg_score = round(sum(r[1] for r in results if r[1] >= 0) / max(len([r for r in results if r[1] >= 0]), 1), 1)
        total_issues = sum(r[2] for r in results)
        total_critical = sum(r[3] for r in results)

        report = [
            f"--- PHOENIX FULL PROJECT SECURITY AUDIT ---",
            f"Files Scanned: {len(results)}",
            f"Average Security Score: {avg_score}/100",
            f"Total Issues: {total_issues}",
            f"Critical Issues: {total_critical}",
            f"{'=' * 50}",
        ]

        # Show files with issues first
        problem_files = [r for r in results if r[1] < 80 and r[1] >= 0]
        clean_files = [r for r in results if r[1] >= 80]

        if problem_files:
            report.append(f"\n[FILES NEEDING ATTENTION] ({len(problem_files)})")
            for name, score, issues, crit, high in problem_files:
                grade = "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 50 else "D" if score >= 30 else "F"
                report.append(f"  {grade} [{score:5.1f}] {name} ({issues} issues, {crit} critical)")

        report.append(f"\n[CLEAN FILES] ({len(clean_files)})")
        for name, score, issues, crit, high in clean_files[:10]:
            report.append(f"  A [{score:5.1f}] {name}")
        if len(clean_files) > 10:
            report.append(f"  ... aur {len(clean_files) - 10} clean files")

        report.append(f"\nBoss, poore project ka security audit complete. Average score: {avg_score}/100")

        return "\n".join(report)

    except Exception as e:
        return f"--- SECURITY AUDIT ---\nStatus: ERROR\nError: {e}"


@function_tool
async def code_quality_all_tool() -> str:
    """
    Poore project ki code quality rankings — maintainability index aur complexity har file ka.
    Kaunsa module best hai, kaunsa worst — sab rank karta hai.
    """
    try:
        results = []

        for py_file in sorted(Config.PROJECT_ROOT.glob("shell_*.py")):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                analysis = UltraCodeAnalyzer.full_analysis(code, py_file.name)
                maintainability = analysis.get("maintainability_index", 0)
                complexity = analysis.get("complexity", {})
                total_complexity = complexity.get("total_complexity", 0) if "error" not in complexity else 0
                metrics = analysis.get("metrics", {})
                lines = metrics.get("total_lines", 0)
                funcs = metrics.get("functions", 0)
                smells = len(analysis.get("smells", []))
                results.append((py_file.name, maintainability, total_complexity, lines, funcs, smells))
            except Exception:
                continue

        # Sort by maintainability descending
        results.sort(key=lambda x: -x[1])

        avg_mi = round(sum(r[1] for r in results) / max(len(results), 1), 1)
        total_smells = sum(r[5] for r in results)

        report = [
            f"--- PHOENIX CODE QUALITY RANKINGS ---",
            f"Modules Analyzed: {len(results)}",
            f"Average Maintainability: {avg_mi}/100",
            f"Total Code Smells: {total_smells}",
            f"{'=' * 55}",
            f"",
            f"{'Rank':<5} {'Score':<7} {'Grade':<6} {'Lines':<7} {'Funcs':<6} {'Smells':<7} {'File'}",
            f"{'-'*55}",
        ]

        for i, (name, mi, complexity, lines, funcs, smells) in enumerate(results, 1):
            grade = "A+" if mi >= 90 else "A" if mi >= 80 else "B" if mi >= 70 else "C" if mi >= 50 else "D" if mi >= 30 else "F"
            report.append(f"  {i:<4} {mi:<6.1f} {grade:<6} {lines:<7} {funcs:<6} {smells:<7} {name}")

        report.append(f"\nBoss, poore project ki code quality rankings ready hain. Average: {avg_mi}/100")

        return "\n".join(report)

    except Exception as e:
        return f"--- CODE QUALITY RANKINGS ---\nStatus: ERROR\nError: {e}"


# =============================================================================
# 🧪 TEST MODE
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

    logger.info("[SHELL_PHOENIX_ULTRA] Test Mode")
    logger.info("=" * 60)

    async def test_ultra():
        # Test 1: Ultra health check
        logger.info("[TEST 1] Ultra health check...")
        result = await ultra_self_health_check_tool()
        logger.info(result)

        # Test 2: Ultra stats
        logger.info("[TEST 2] Ultra stats...")
        result = await get_ultra_phoenix_stats_tool()
        logger.info(result)

        # Test 3: Security scanner
        logger.info("[TEST 3] Security scanner test...")
        test_code = "eval('print(1)')"
        issues = UltraSecurityScanner.scan_code(test_code, "test.py")
        logger.info(f"Found {len(issues)} security issues in test code")

        # Test 4: Code analyzer
        logger.info("[TEST 4] Code analyzer test...")
        test_code = """
def long_function(a, b, c, d, e, f, g):
    x = 1
    x = 1
    x = 1
    return a + b + c
"""
        analysis = UltraCodeAnalyzer.full_analysis(test_code, "test.py")
        logger.info(f"Code smells: {len(analysis.get('smells', []))}")
        logger.info(f"Security score: {analysis.get('security_score', 0)}/100")

        logger.info("[TEST] All tests completed!")
    
    asyncio.run(test_ultra())
