"""
Shell Evolution Engine.

This module exposes Shell's improvement workflow: proposal, validation,
history, module analysis, gated writes, gated hotpatches, and rollback.
Actual source mutation remains protected by shell_safety_gate so evolution is
observable and recoverable instead of unrestricted self-modification.
"""

import os
import logging
import ast
import re
import sys
import shutil
import time
import json
import hashlib
import textwrap
from datetime import datetime
from typing import Dict, List, Optional
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_evolution")

# --- Constants ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
EVOLUTION_LOG_FILE = os.path.join(PROJECT_ROOT, ".evolution_history.json")
EVOLUTION_BACKUP_DIR = os.path.join(PROJECT_ROOT, "brain", "evolution_backups")
EVOLUTION_PROPOSALS_FILE = os.path.join(PROJECT_ROOT, ".shell_runtime", "evolution", "proposals.json")


def _governor():
    from core.evolution import EvolutionGovernor

    return EvolutionGovernor(os.environ.get("SHELL_EVOLUTION_PROPOSALS_PATH") or EVOLUTION_PROPOSALS_FILE)


@function_tool
async def evolution_governor_status_tool() -> str:
    """
    Shows the governed evolution status: pending proposals, safety flags,
    production mode, and the exact write policy.
    """
    try:
        status = _governor().status()
        counts = status.get("proposal_counts", {})
        lines = [
            "--- SHELL EVOLUTION GOVERNOR ---",
            f"Pending proposals: {counts.get('pending_approval', 0)}",
            f"Approved proposals: {counts.get('approved', 0)}",
            f"Validated proposals: {counts.get('validated', 0)}",
            f"Code write enabled: {status.get('code_write_enabled')}",
            f"Agent patch enabled: {status.get('agent_patch_enabled')}",
            f"Production mode: {status.get('production_mode')}",
            f"Auto apply enabled: {status.get('auto_apply_enabled')}",
            "",
            "Policy: proposal -> validation -> explicit approval -> gated write tool -> tests -> rollback if needed",
            "Unrestricted self-modification stays disabled so Shell can evolve without corrupting itself.",
        ]
        return "\n".join(lines)
    except Exception as exc:
        return f"Evolution governor status error: {exc}"


@function_tool
async def propose_evolution_tool(request: str, target_scope: str = "new_tool", notes: str = "") -> str:
    """
    Creates an evolution proposal without writing source code.
    target_scope: new_tool, tool_fix, ui_fix, docs, tests, refactor,
    agent_patch, core_patch, or runtime_patch.
    """
    try:
        proposal = _governor().propose(request, target_scope=target_scope, notes=notes)
        decision = proposal.governance
        reasons = decision.get("reasons") or []
        return (
            "--- EVOLUTION PROPOSAL CREATED ---\n"
            f"Proposal ID: {proposal.proposal_id}\n"
            f"Scope: {proposal.target_scope}\n"
            f"Status: {proposal.status}\n"
            f"Governance allowed now: {decision.get('allowed')}\n"
            f"Requires approval: {decision.get('requires_approval')}\n"
            f"Security class: {decision.get('security_class')}\n"
            f"Reasons: {', '.join(reasons) if reasons else 'none'}\n\n"
            "Next: validate generated code with validate_evolution_patch_tool, then ask the user to approve before applying."
        )
    except Exception as exc:
        return f"Evolution proposal error: {exc}"


@function_tool
async def approve_evolution_proposal_tool(proposal_id: str, approved_by: str = "user", note: str = "") -> str:
    """
    Marks a proposal as approved. This does not write source code; the actual
    write/hotpatch step is still handled by gated evolution tools.
    """
    try:
        proposal = _governor().approve(proposal_id, approved_by=approved_by, note=note)
        return (
            "--- EVOLUTION PROPOSAL APPROVED ---\n"
            f"Proposal ID: {proposal.proposal_id}\n"
            f"Scope: {proposal.target_scope}\n"
            f"Approved By: {proposal.approved_by}\n"
            "Status: approved\n\n"
            "Next: use create_capability_tool only if SHELL_ALLOW_CODE_WRITE=1, and hotpatch only if SHELL_ALLOW_AGENT_PATCH=1."
        )
    except Exception as exc:
        return f"Evolution approval error: {exc}"


@function_tool
async def validate_evolution_patch_tool(filename: str, python_code: str, proposal_id: str = "") -> str:
    """
    Validates generated evolution code without writing it to disk.
    Optionally records the result against an existing proposal_id.
    """
    try:
        gov = _governor()
        validation = gov.validate_patch(filename, python_code)
        if proposal_id:
            gov.record_validation(proposal_id, validation)
        status = "PASS" if validation.ok else "FAIL"
        lines = [
            "--- EVOLUTION PATCH VALIDATION ---",
            f"File: {validation.filename}",
            f"Status: {status}",
            f"Functions: {', '.join(validation.functions) if validation.functions else 'none'}",
            f"Imports: {', '.join(validation.imports) if validation.imports else 'none'}",
        ]
        if validation.blockers:
            lines.append("\nBlockers:")
            lines.extend(f"- {item}" for item in validation.blockers)
        if validation.warnings:
            lines.append("\nWarnings:")
            lines.extend(f"- {item}" for item in validation.warnings)
        if validation.ok:
            lines.append("\nPatch is syntactically safe enough for manual review. It has not been written to disk.")
        return "\n".join(lines)
    except Exception as exc:
        return f"Evolution validation error: {exc}"

# --- Evolution History Manager ---
def _load_evolution_log() -> list:
    """Loads evolution history from JSON."""
    if os.path.isfile(EVOLUTION_LOG_FILE):
        try:
            with open(EVOLUTION_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_evolution_log(log: list):
    """Saves evolution history to JSON."""
    with open(EVOLUTION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

def _log_evolution_event(event_type: str, details: dict):
    """Adds an event to evolution history."""
    log = _load_evolution_log()
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event_type,
        **details
    }
    log.append(entry)
    # Keep last 500 entries
    if len(log) > 500:
        log = log[-500:]
    _save_evolution_log(log)

def _get_file_hash(filepath: str) -> str:
    """Returns MD5 hash of a file."""
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return "unknown"

def _count_tools_in_code(code: str) -> list:
    """Finds all @function_tool decorated function names in code."""
    matches = re.findall(r'@function_tool\s*\nasync\s+def\s+(\w+)\s*\(', code)
    if not matches:
        matches = re.findall(r'def\s+([a-zA-Z0-9_]+_tool)\s*\(', code)
    return list(dict.fromkeys(matches))

def _analyze_imports(code: str) -> dict:
    """Analyzes imports in code and checks if they're available."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"error": "SyntaxError in code"}

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"module": alias.name, "type": "import"})
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append({"module": node.module, "type": "from", "names": [a.name for a in node.names]})

    # Check availability
    results = []
    for imp in imports:
        mod = imp["module"].split(".")[0]
        available = mod in sys.modules
        if not available:
            try:
                __import__(mod)
                available = True
            except ImportError:
                available = False
        results.append({**imp, "available": available})

    return {"imports": results, "total": len(results), "missing": [r for r in results if not r["available"]]}

@function_tool
async def create_capability_tool(tool_name: str, python_code: str) -> str:
    """
     Darwin Protocol: Creates a NEW system capability (Python file).
     Naya tool/module banata hai, syntax check karta hai, version track karta hai.
     Args:
         tool_name: Name of the feature (e.g., 'crypto_tracker'). File will be 'shell_{tool_name}.py'.
         python_code: The complete Python code for the module. MUST generally contain a @function_tool.

     SAFETY: Requires SHELL_ALLOW_CODE_WRITE=1 (see shell_safety_gate). Disabled by default
     so an unvetted LLM response cannot silently install a backdoor.
    """
    try:
        # 0. Safety gate — refuse if code writing has not been explicitly permitted.
        try:
            from shell_safety_gate import check_code_write, audit_write
        except Exception:
            return "Evolution Error: shell_safety_gate module unavailable; refusing to write."
        ok, reason = check_code_write(origin="create_capability_tool")
        if not ok:
            return f"EVOLUTION BLOCKED:\n{reason}"

        # 0.5. Validate tool_name — lowercase, starts with letter, 2-40 chars,
        # alphanumeric + underscore only. Blocks path separators, unicode
        # homoglyphs, and empty strings before they reach the filesystem.
        if not tool_name or not re.match(r"^[a-z][a-z0-9_]{1,39}$", tool_name or ""):
            return (
                "EVOLUTION BLOCKED: tool_name must match ^[a-z][a-z0-9_]{1,39}$ "
                "(lowercase letter start, 2-40 chars, only a-z 0-9 _). "
                f"Got: {tool_name!r}"
            )

        # 1. Auto safe-executor wrapping
        if "from shell_safe_executor import god_tier_tool as function_tool" not in python_code:
            python_code = re.sub(r"from livekit\.agents(\.llm)? import function_tool\n?", "", python_code)
            python_code = "from shell_safe_executor import god_tier_tool as function_tool\n" + python_code

        # 2. Syntax Validation
        try:
            ast.parse(python_code)
        except SyntaxError as e:
            return f"EVOLUTION BLOCKED: SyntaxError on line {e.lineno}: {e.msg}. Fix the code before genesis."

        # 3. Dependency Check
        dep_analysis = _analyze_imports(python_code)
        missing = dep_analysis.get("missing", [])
        missing_warning = ""
        if missing:
            missing_names = [m["module"] for m in missing]
            missing_warning = f"\n--- DEPENDENCY WARNING ---\nMissing modules: {', '.join(missing_names)}\nInstall karke restart karo warna tool crash karega.\n"

        # 4. Check if file already exists (backup old version)
        filename = f"shell_{tool_name}.py"
        filepath = os.path.join(PROJECT_ROOT, filename)
        overwrite = False

        if os.path.exists(filepath):
            overwrite = True
            os.makedirs(EVOLUTION_BACKUP_DIR, exist_ok=True)
            ts = int(time.time())
            backup_path = os.path.join(EVOLUTION_BACKUP_DIR, f"{filename}.v{ts}.bak")
            shutil.copy(filepath, backup_path)

        # 5. Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(python_code)
        audit_write("create_capability_tool", filepath, f"tool={tool_name} lines={len(python_code.splitlines())}")

        # 6. Count tools in new code
        tools_found = _count_tools_in_code(python_code)
        lines_count = len(python_code.splitlines())
        file_hash = _get_file_hash(filepath)

        # 7. Log evolution event
        _log_evolution_event("CREATE", {
            "file": filename,
            "tools": tools_found,
            "lines": lines_count,
            "hash": file_hash,
            "overwrite": overwrite,
        })

        action = "OVERWRITTEN (backup saved)" if overwrite else "CREATED"
        return (
            f"--- DARWIN GENESIS REPORT ---\n"
            f"File: {filename} [{action}]\n"
            f"Lines: {lines_count}\n"
            f"Tools Found: {len(tools_found)} -> {', '.join(tools_found) if tools_found else 'None'}\n"
            f"Hash: {file_hash}\n"
            f"Syntax: VALID\n"
            f"Safe Executor Wrapper: APPLIED\n"
            f"{missing_warning}"
            f"Boss, '{filename}' ban gaya hai! Ab 'hotpatch_agent_tool' se activate karo."
        )
    except Exception as e:
        return f"Evolution Error: {e}"

@function_tool
async def hotpatch_agent_tool(tool_name: str, function_name: str, target_file: str = "agent.py") -> str:
    """
     Darwin Protocol: Injects a new capability into the CORE NERVOUS SYSTEM (agent.py).
     Args:
         tool_name: The feature name used in 'create_capability_tool' (e.g., 'crypto_tracker').
         function_name: The actual function name inside that file (e.g., 'get_bitcoin_price_tool').
         target_file: (Optional) File to patch. Defaults to 'agent.py'.

     SAFETY: Requires SHELL_ALLOW_AGENT_PATCH=1. Disabled by default because a
     bad patch can break the entire agent. Backups are always created first.
    """
    try:
        try:
            from shell_safety_gate import check_agent_patch, audit_write
        except Exception:
            return "Mutation Error: shell_safety_gate module unavailable; refusing to patch."
        ok, reason = check_agent_patch(origin="hotpatch_agent_tool")
        if not ok:
            return f"HOTPATCH BLOCKED:\n{reason}"

        agent_path = os.path.join(os.getcwd(), target_file)

        with open(agent_path, "r", encoding="utf-8") as f:
            original_code = f.read()

        lines = original_code.splitlines(True)

        # 1. Duplicate Shield
        if f"from shell_{tool_name} import" in original_code and function_name in original_code:
            return f"Duplicate Shield Activated: '{function_name}' is already patched into the Core Nervous System."

        # 2. Inject Import (Find the last 'from shell_' or 'import' line)
        import_line = f"from shell_{tool_name} import {function_name}\n"
        import_idx = -1

        for i, line in enumerate(lines):
            if line.startswith("from shell_") or line.startswith("import "):
                import_idx = i

        # Insert import after the last import we found, or at top
        if import_idx != -1:
            lines.insert(import_idx + 1, import_line)
        else:
            lines.insert(0, import_line)

        # 3. Inject Tool into list
        tool_list_start = -1
        for i, line in enumerate(lines):
            if "tools_list = [" in line:
                tool_list_start = i
                break

        if tool_list_start == -1:
            return "Critical Error: Could not find 'tools_list = [' in agent.py. Mutation failed."

        lines.insert(tool_list_start + 1, f"            {function_name},\n")

        new_code = "".join(lines)

        # 4. Brain Rollback Feature — parse the COMPLETE assembled code,
        # not just the injected fragment. A fragment may pass ast.parse
        # in isolation while still breaking agent.py (unbalanced brackets
        # from bad insertion indexes). Parsing new_code catches both.
        try:
            ast.parse(new_code)
        except SyntaxError as e:
            return f"ROLLBACK ACTIVATED: Injecting this capability would have corrupted agent.py (SyntaxError line {e.lineno}: {e.msg}). The system has defended itself."

        # Write back if healthy
        # Backup agent.py before patching
        os.makedirs(EVOLUTION_BACKUP_DIR, exist_ok=True)
        ts = int(time.time())
        backup_path = os.path.join(EVOLUTION_BACKUP_DIR, f"agent.py.pre_hotpatch_{ts}.bak")
        shutil.copy(agent_path, backup_path)

        with open(agent_path, "w", encoding="utf-8") as f:
            f.write(new_code)
        audit_write("hotpatch_agent_tool", agent_path, f"tool={tool_name} fn={function_name}")

        # Log evolution event
        _log_evolution_event("HOTPATCH", {
            "module": f"shell_{tool_name}",
            "function": function_name,
            "target": target_file,
            "backup": backup_path,
        })

        return (
            f"--- DARWIN HOTPATCH REPORT ---\n"
            f"Module: shell_{tool_name}\n"
            f"Function: {function_name}\n"
            f"Target: {target_file}\n"
            f"Backup: {backup_path}\n"
            f"Status: INJECTION SUCCESSFUL\n"
            f"Boss, '{function_name}' ab Core Nervous System mein active hai. RESTART karo effect ke liye."
        )

    except Exception as e:
        return f"Mutation Error: {e}"

@function_tool
async def list_core_modules_tool() -> str:
    """
    Lists all active 'shell_' modules with deep neuro-mapping.
    Shows: tool coordinates, line count, file size, total tools, and category grouping.
    Poora system ka X-ray report deta hai ye tool.
    """
    try:
        files = [f for f in os.listdir() if f.startswith("shell_") and f.endswith(".py")]

        # Category detection from filenames
        category_keywords = {
            "Web/API": ["web", "api", "http", "scrape", "browser", "search"],
            "Social/Media": ["social", "insta", "youtube", "twitter", "telegram", "whatsapp", "media", "tts", "stt", "voice"],
            "System/Core": ["config", "logger", "safe", "executor", "brain", "memory", "agent", "core"],
            "Security/Sentinel": ["sentinel", "guard", "auth", "secure", "encrypt"],
            "Evolution/Meta": ["evolution", "darwin", "hotpatch", "self"],
            "Utility/Tools": [],  # default fallback
        }

        def detect_category(filename: str) -> str:
            fname_lower = filename.lower().replace("shell_", "").replace(".py", "")
            for cat, keywords in category_keywords.items():
                for kw in keywords:
                    if kw in fname_lower:
                        return cat
            return "Utility/Tools"

        # Group files by category
        categorized: dict[str, list] = {}
        total_tools = 0
        total_lines = 0
        total_size = 0

        for file in sorted(files):
            filepath = os.path.join(os.getcwd(), file)
            file_size = os.path.getsize(filepath)
            total_size += file_size

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            line_count = len(content.splitlines())
            total_lines += line_count

            # Find tool functions
            matches = re.findall(r'def\s+([a-zA-Z0-9_]+_tool)\(', content)
            unique_matches = list(dict.fromkeys(matches)) if matches else []
            total_tools += len(unique_matches)

            category = detect_category(file)
            if category not in categorized:
                categorized[category] = []

            categorized[category].append({
                "file": file,
                "size": file_size,
                "lines": line_count,
                "tools": unique_matches,
            })

        # Build report
        report = [
            "--- SHELL MODULE MAP ---",
            f"Total Modules: {len(files)}",
            f"Total Operational Tools: {total_tools}",
            f"Total Lines of Code: {total_lines}",
            f"Total Size: {total_size} bytes ({round(total_size / 1024, 2)} KB)",
        ]

        for cat in sorted(categorized.keys()):
            modules = categorized[cat]
            cat_tool_count = sum(len(m["tools"]) for m in modules)
            report.append(f"\n[{cat}] ({cat_tool_count} tools)")

            for mod in modules:
                size_kb = round(mod["size"] / 1024, 2)
                report.append(f"  {mod['file']}  |  {mod['lines']} lines  |  {size_kb} KB")
                if mod["tools"]:
                    for func in mod["tools"]:
                        report.append(f"    -> {func}")
                else:
                    report.append(f"    -> (No tool definitions)")

        report.append(
            "\nBoss, ye poore system ka neuro-map hai. Saare modules aur tools ka full scan."
        )

        return "\n".join(report)
    except Exception as e:
        return f"Mapping Error: {e}"


@function_tool
async def rollback_evolution_tool(filename: str) -> str:
    """
    Rolls back an evolution by removing a shell_*.py module's import and tool entry from agent.py.
    Creates a backup of agent.py before making changes.
    Args:
        filename: The shell module file to rollback (e.g., 'shell_crypto_tracker.py').
    Boss ko koi evolved module hatana ho toh ye use karo. Safe rollback with backup.

    SAFETY: Requires SHELL_ALLOW_AGENT_PATCH=1 since this mutates agent.py.
    """
    try:
        try:
            from shell_safety_gate import check_agent_patch, audit_write
        except Exception:
            return "Rollback Error: shell_safety_gate module unavailable; refusing to patch."
        ok, reason = check_agent_patch(origin="rollback_evolution_tool")
        if not ok:
            return f"ROLLBACK BLOCKED:\n{reason}"

        target_file = "agent.py"
        agent_path = os.path.join(os.getcwd(), target_file)

        # Validate filename format
        if not filename.startswith("shell_") or not filename.endswith(".py"):
            return (
                f"--- EVOLUTION ROLLBACK REPORT ---\n"
                f"File: {filename}\n"
                f"Status: INVALID FILENAME\n"
                f"Boss, sirf 'shell_*.py' files rollback ho sakti hain. Format check karo."
            )

        if not os.path.exists(agent_path):
            return (
                f"--- EVOLUTION ROLLBACK REPORT ---\n"
                f"Status: agent.py NOT FOUND\n"
                f"Boss, agent.py nahi mili. Kuch gadbad hai directory mein."
            )

        # Read agent.py
        with open(agent_path, "r", encoding="utf-8") as f:
            original_code = f.read()

        # Derive module name (shell_crypto_tracker.py -> shell_crypto_tracker)
        module_name = filename.replace(".py", "")

        # Check if this module is actually imported in agent.py
        import_pattern = re.compile(rf'^from\s+{re.escape(module_name)}\s+import\s+(.+)$', re.MULTILINE)
        import_matches = import_pattern.findall(original_code)

        if not import_matches:
            return (
                f"--- EVOLUTION ROLLBACK REPORT ---\n"
                f"File: {filename}\n"
                f"Status: NOT FOUND IN AGENT.PY\n"
                f"Boss, '{module_name}' ka koi import agent.py mein nahi mila. "
                f"Ye module patched nahi hai ya pehle se hata diya gaya hai."
            )

        # Extract function names that were imported
        imported_functions = []
        for match in import_matches:
            funcs = [f.strip() for f in match.split(",")]
            imported_functions.extend(funcs)

        # Create backup of agent.py before modifying
        backup_dir = "brain/sentinel_backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = int(time.time())
        backup_path = os.path.join(backup_dir, f"agent.py.rollback_{timestamp}.bak")
        shutil.copy(agent_path, backup_path)

        lines = original_code.splitlines(True)
        new_lines = []
        removed_imports = 0
        removed_tools = 0

        for line in lines:
            stripped = line.strip()

            # Remove import lines for this module
            if re.match(rf'^from\s+{re.escape(module_name)}\s+import\s+', stripped):
                removed_imports += 1
                continue

            # Remove tool list entries for imported functions
            skip_line = False
            for func in imported_functions:
                # Match lines like "            function_name," in tools_list
                if stripped == f"{func}," or stripped == func:
                    removed_tools += 1
                    skip_line = True
                    break
            if skip_line:
                continue

            new_lines.append(line)

        new_code = "".join(new_lines)

        # Validate syntax before writing
        try:
            ast.parse(new_code)
        except SyntaxError as e:
            return (
                f"--- EVOLUTION ROLLBACK REPORT ---\n"
                f"File: {filename}\n"
                f"Status: ROLLBACK ABORTED - SyntaxError\n"
                f"Error: Line {e.lineno}: {e.msg}\n"
                f"Backup: {backup_path}\n"
                f"Boss, rollback karne se agent.py ka syntax toot jaata. Abort kar diya."
            )

        # Write modified agent.py
        with open(agent_path, "w", encoding="utf-8") as f:
            f.write(new_code)
        audit_write("rollback_evolution_tool", agent_path, f"removed={module_name} imports={removed_imports} tools={removed_tools}")

        return (
            f"--- EVOLUTION ROLLBACK REPORT ---\n"
            f"Module: {filename}\n"
            f"Status: ROLLBACK SUCCESSFUL\n"
            f"Import Lines Removed: {removed_imports}\n"
            f"Tool Entries Removed: {removed_tools}\n"
            f"Functions Removed: {', '.join(imported_functions)}\n"
            f"Backup: {backup_path}\n"
            f"Boss, '{module_name}' ka evolution rollback ho gaya. agent.py se import aur tool entry "
            f"hata diye. Backup rakha hai agar wapas chahiye toh. RESTART karo effect ke liye."
        )

    except Exception as e:
        return (
            f"--- EVOLUTION ROLLBACK REPORT ---\n"
            f"Status: ERROR\n"
            f"Error: {e}\n"
            f"Boss, rollback mein error aa gaya. Manually check karo."
        )


# =============================================================================
# NEW MEGA TOOLS — DARWIN LEVEL 999999
# =============================================================================

@function_tool
async def analyze_module_tool(filename: str) -> str:
    """
    Deep code analysis of any shell_*.py module.
    Shows: line count, tool count, complexity, imports, security score, code smells, dependencies.
    Kisi bhi module ka pura X-ray report deta hai.
    Args:
        filename: File to analyze (e.g., 'shell_browser_CTRL.py')
    """
    try:
        filepath = os.path.join(PROJECT_ROOT, filename)
        if not os.path.exists(filepath):
            return f"--- MODULE ANALYSIS REPORT ---\nFile: {filename}\nStatus: FILE NOT FOUND\nBoss, '{filename}' exist nahi karta."

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        lines = code.splitlines()
        total_lines = len(lines)
        code_lines = sum(1 for l in lines if l.strip() and not l.strip().startswith('#'))
        comment_lines = sum(1 for l in lines if l.strip().startswith('#'))
        blank_lines = sum(1 for l in lines if not l.strip())
        file_size = os.path.getsize(filepath)

        # Tools found
        tools = _count_tools_in_code(code)

        # Classes found
        classes = re.findall(r'class\s+(\w+)', code)

        # Import analysis
        dep_result = _analyze_imports(code)
        total_imports = dep_result.get("total", 0)
        missing_deps = dep_result.get("missing", [])

        # Complexity: count if/for/while/try/except/with
        complexity_keywords = ['if ', 'elif ', 'for ', 'while ', 'try:', 'except ', 'with ']
        complexity_score = sum(
            sum(1 for l in lines if kw in l)
            for kw in complexity_keywords
        )

        # Security quick scan
        security_issues = []
        dangerous = [('eval(', 'CRITICAL'), ('exec(', 'CRITICAL'), ('os.system(', 'HIGH'),
                     ('subprocess.call', 'MEDIUM'), ('pickle.load', 'HIGH')]
        for pattern, severity in dangerous:
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    security_issues.append(f"  Line {i}: {severity} - {pattern}")

        security_score = max(0, 100 - len(security_issues) * 15)

        # Async ratio
        async_funcs = len(re.findall(r'async\s+def\s+', code))
        sync_funcs = len(re.findall(r'(?<!async\s)def\s+\w+', code))
        total_funcs = async_funcs + sync_funcs

        # Longest function
        func_lengths = []
        current_func = None
        current_start = 0
        for i, line in enumerate(lines):
            if re.match(r'\s*(?:async\s+)?def\s+\w+', line):
                if current_func:
                    func_lengths.append((current_func, i - current_start))
                current_func = re.findall(r'def\s+(\w+)', line)[0]
                current_start = i
        if current_func:
            func_lengths.append((current_func, total_lines - current_start))
        func_lengths.sort(key=lambda x: -x[1])

        # File hash
        file_hash = _get_file_hash(filepath)
        modified = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M:%S")

        # Build report
        report = [
            f"--- DARWIN MODULE ANALYSIS ---",
            f"File: {filename}",
            f"Size: {file_size} bytes ({round(file_size/1024, 1)} KB)",
            f"Hash: {file_hash}",
            f"Last Modified: {modified}",
            f"",
            f"[CODE METRICS]",
            f"  Total Lines: {total_lines}",
            f"  Code Lines: {code_lines}",
            f"  Comments: {comment_lines}",
            f"  Blank Lines: {blank_lines}",
            f"  Comment Ratio: {round(comment_lines/max(total_lines,1)*100, 1)}%",
            f"",
            f"[STRUCTURE]",
            f"  Functions: {total_funcs} (async: {async_funcs}, sync: {sync_funcs})",
            f"  Classes: {len(classes)} -> {', '.join(classes) if classes else 'None'}",
            f"  Tools (@function_tool): {len(tools)} -> {', '.join(tools) if tools else 'None'}",
            f"  Imports: {total_imports}",
            f"  Complexity Score: {complexity_score}",
            f"",
            f"[SECURITY]",
            f"  Score: {security_score}/100",
        ]

        if security_issues:
            report.append(f"  Issues ({len(security_issues)}):")
            for issue in security_issues[:5]:
                report.append(issue)
        else:
            report.append("  No security issues found")

        if missing_deps:
            report.append(f"\n[MISSING DEPENDENCIES]")
            for dep in missing_deps:
                report.append(f"  - {dep['module']}")

        if func_lengths:
            report.append(f"\n[TOP 5 LONGEST FUNCTIONS]")
            for name, length in func_lengths[:5]:
                report.append(f"  {name}: {length} lines")

        report.append(f"\nBoss, ye '{filename}' ka complete analysis hai. Deep scan done.")

        return "\n".join(report)

    except Exception as e:
        return f"--- MODULE ANALYSIS REPORT ---\nStatus: ERROR\nError: {e}"


@function_tool
async def evolution_history_tool(limit: int = 20) -> str:
    """
    Shows complete evolution history — har create, hotpatch, rollback ka record.
    Saari evolution events time ke saath dikhata hai.
    Args:
        limit: How many recent events to show (default 20)
    """
    try:
        log = _load_evolution_log()
        if not log:
            return (
                "--- DARWIN EVOLUTION HISTORY ---\n"
                "Status: NO HISTORY\n"
                "Boss, abhi tak koi evolution event recorded nahi hai. Pehle koi tool create karo."
            )

        total = len(log)
        recent = log[-limit:]
        recent.reverse()  # newest first

        report = [
            f"--- DARWIN EVOLUTION HISTORY ---",
            f"Total Events: {total}",
            f"Showing: Last {len(recent)}",
            f"{'=' * 50}",
        ]

        # Count by event type
        event_counts = {}
        for entry in log:
            evt = entry.get("event", "UNKNOWN")
            event_counts[evt] = event_counts.get(evt, 0) + 1

        report.append("\n[EVENT SUMMARY]")
        for evt, count in sorted(event_counts.items()):
            emoji = {"CREATE": "🧬", "HOTPATCH": "💉", "ROLLBACK": "⏪", "ANALYZE": "🔬"}.get(evt, "📋")
            report.append(f"  {emoji} {evt}: {count}")

        report.append(f"\n[RECENT EVENTS]")
        for i, entry in enumerate(recent, 1):
            ts = entry.get("timestamp", "?")
            evt = entry.get("event", "?")
            emoji = {"CREATE": "🧬", "HOTPATCH": "💉", "ROLLBACK": "⏪"}.get(evt, "📋")
            file_info = entry.get("file", entry.get("module", "?"))
            tools = entry.get("tools", [])
            tools_str = f" ({len(tools)} tools)" if tools else ""
            report.append(f"  {i}. [{ts}] {emoji} {evt}: {file_info}{tools_str}")

        report.append(f"\nBoss, ye poori evolution timeline hai. Shell kaise evolve hua, sab recorded hai.")

        return "\n".join(report)

    except Exception as e:
        return f"--- EVOLUTION HISTORY ---\nStatus: ERROR\nError: {e}"


@function_tool
async def validate_module_tool(filename: str) -> str:
    """
    Validates a shell module — syntax check, import check, tool detection, dependency verification.
    Kisi bhi module ko deploy karne se pehle validate karo is tool se.
    Args:
        filename: File to validate (e.g., 'shell_crypto.py')
    """
    try:
        filepath = os.path.join(PROJECT_ROOT, filename)
        if not os.path.exists(filepath):
            return f"--- VALIDATION REPORT ---\nFile: {filename}\nStatus: FILE NOT FOUND"

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        checks = []
        all_passed = True

        # 1. Syntax Check
        try:
            ast.parse(code)
            checks.append("  [PASS] Syntax Valid")
        except SyntaxError as e:
            checks.append(f"  [FAIL] SyntaxError line {e.lineno}: {e.msg}")
            all_passed = False

        # 2. Safe executor wrapper check
        if "from shell_safe_executor import god_tier_tool as function_tool" in code:
            checks.append("  [PASS] Safe Executor Wrapper Present")
        elif "from livekit" in code:
            checks.append("  [WARN] Uses livekit import instead of god_tier_tool")
        else:
            checks.append("  [WARN] No function_tool import found")

        # 3. Tool Detection
        tools = _count_tools_in_code(code)
        if tools:
            checks.append(f"  [PASS] {len(tools)} tools found: {', '.join(tools)}")
        else:
            checks.append("  [WARN] No @function_tool decorated functions found")

        # 4. Async Check
        async_defs = re.findall(r'async\s+def\s+(\w+)', code)
        non_async_tools = [t for t in tools if t not in [a for a in async_defs]]
        if non_async_tools:
            checks.append(f"  [WARN] Non-async tools: {', '.join(non_async_tools)} (should be async)")
        else:
            checks.append("  [PASS] All tools are async")

        # 5. Return Type Check
        for tool in tools:
            pattern = rf'def\s+{re.escape(tool)}\s*\([^)]*\)\s*->\s*str'
            if not re.search(pattern, code):
                checks.append(f"  [WARN] {tool} missing -> str return type")

        # 6. Dependency Check
        dep_analysis = _analyze_imports(code)
        missing = dep_analysis.get("missing", [])
        if missing:
            missing_names = [m["module"] for m in missing]
            checks.append(f"  [FAIL] Missing dependencies: {', '.join(missing_names)}")
            all_passed = False
        else:
            checks.append(f"  [PASS] All {dep_analysis.get('total', 0)} dependencies available")

        # 7. File Size Check
        size = os.path.getsize(filepath)
        if size > 100 * 1024:  # 100KB
            checks.append(f"  [WARN] File is large ({round(size/1024, 1)} KB) — consider splitting")
        else:
            checks.append(f"  [PASS] File size OK ({round(size/1024, 1)} KB)")

        overall = "ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED"
        return (
            f"--- DARWIN VALIDATION REPORT ---\n"
            f"File: {filename}\n"
            f"Status: {overall}\n"
            f"{'=' * 40}\n"
            + "\n".join(checks)
            + f"\n\nBoss, validation complete. {'Sab theek hai, deploy karo!' if all_passed else 'Issues fix karo pehle.'}"
        )

    except Exception as e:
        return f"--- VALIDATION REPORT ---\nStatus: ERROR\nError: {e}"


@function_tool
async def compare_modules_tool(file1: str, file2: str) -> str:
    """
    Compares two shell modules side-by-side — size, tools, complexity, imports.
    Do modules ka comparison report deta hai.
    Args:
        file1: First file (e.g., 'shell_browser_CTRL.py')
        file2: Second file (e.g., 'shell_window_CTRL.py')
    """
    try:
        def _get_stats(filename: str) -> dict:
            filepath = os.path.join(PROJECT_ROOT, filename)
            if not os.path.exists(filepath):
                return {"error": f"{filename} not found"}
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
            lines = code.splitlines()
            tools = _count_tools_in_code(code)
            classes = re.findall(r'class\s+(\w+)', code)
            funcs = re.findall(r'def\s+(\w+)', code)
            return {
                "file": filename,
                "size": os.path.getsize(filepath),
                "lines": len(lines),
                "code_lines": sum(1 for l in lines if l.strip() and not l.strip().startswith('#')),
                "tools": tools,
                "tool_count": len(tools),
                "classes": len(classes),
                "functions": len(funcs),
                "imports": len(re.findall(r'^(?:import|from)\s+', code, re.MULTILINE)),
            }

        s1 = _get_stats(file1)
        s2 = _get_stats(file2)

        if "error" in s1:
            return s1["error"]
        if "error" in s2:
            return s2["error"]

        def _compare_val(label, v1, v2, unit=""):
            winner = ""
            if v1 > v2:
                winner = f" <- {file1} wins"
            elif v2 > v1:
                winner = f" <- {file2} wins"
            return f"  {label}: {v1}{unit} vs {v2}{unit}{winner}"

        report = [
            f"--- DARWIN MODULE COMPARISON ---",
            f"File A: {file1}",
            f"File B: {file2}",
            f"{'=' * 45}",
            _compare_val("Size", round(s1['size']/1024,1), round(s2['size']/1024,1), " KB"),
            _compare_val("Lines", s1['lines'], s2['lines']),
            _compare_val("Code Lines", s1['code_lines'], s2['code_lines']),
            _compare_val("Tools", s1['tool_count'], s2['tool_count']),
            _compare_val("Functions", s1['functions'], s2['functions']),
            _compare_val("Classes", s1['classes'], s2['classes']),
            _compare_val("Imports", s1['imports'], s2['imports']),
            f"\n[FILE A TOOLS] {', '.join(s1['tools']) if s1['tools'] else 'None'}",
            f"[FILE B TOOLS] {', '.join(s2['tools']) if s2['tools'] else 'None'}",
            f"\nBoss, comparison done. Dono modules ka full comparison upar hai.",
        ]

        return "\n".join(report)

    except Exception as e:
        return f"--- COMPARISON REPORT ---\nStatus: ERROR\nError: {e}"


@function_tool
async def generate_test_tool(filename: str) -> str:
    """
    Auto-generates a basic test file for any shell module.
    Module ke tools ke liye import test aur basic call test generate karta hai.
    Args:
        filename: Module to generate tests for (e.g., 'shell_games.py')
    """
    try:
        filepath = os.path.join(PROJECT_ROOT, filename)
        if not os.path.exists(filepath):
            return f"--- TEST GENERATION ---\nFile: {filename}\nStatus: FILE NOT FOUND"

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        module_name = filename.replace(".py", "")
        tools = _count_tools_in_code(code)

        if not tools:
            return f"--- TEST GENERATION ---\nFile: {filename}\nStatus: No @function_tool functions found to test."

        # Generate test code
        test_lines = [
            f'"""Auto-generated tests for {filename}"""',
            f'import asyncio',
            f'import sys',
            f'import os',
            f'',
            f'# Add project root to path',
            f'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))',
            f'',
            f'async def run_tests():',
            f'    results = []',
            f'    print(f"Testing {filename}...")',
            f'    print("=" * 50)',
            f'',
            f'    # Test 1: Import Check',
            f'    try:',
            f'        from {module_name} import {", ".join(tools)}',
            f'        results.append(("Import Check", True, "All imports successful"))',
            f'        print("[PASS] Import Check")',
            f'    except ImportError as e:',
            f'        results.append(("Import Check", False, str(e)))',
            f'        print(f"[FAIL] Import Check: {{e}}")',
            f'        return results',
            f'',
        ]

        # Generate call tests for each tool
        for i, tool in enumerate(tools, 2):
            test_lines.extend([
                f'    # Test {i}: {tool} callable check',
                f'    try:',
                f'        assert callable({tool}), "{tool} is not callable"',
                f'        results.append(("{tool} callable", True, "OK"))',
                f'        print("[PASS] {tool} callable")',
                f'    except Exception as e:',
                f'        results.append(("{tool} callable", False, str(e)))',
                f'        print(f"[FAIL] {tool}: {{e}}")',
                f'',
            ])

        test_lines.extend([
            f'    # Summary',
            f'    passed = sum(1 for _, p, _ in results if p)',
            f'    total = len(results)',
            f'    print(f"\\nResults: {{passed}}/{{total}} passed")',
            f'    return results',
            f'',
            f'if __name__ == "__main__":',
            f'    asyncio.run(run_tests())',
        ])

        test_code = "\n".join(test_lines)

        # Save test file
        tests_dir = os.path.join(PROJECT_ROOT, "tests")
        os.makedirs(tests_dir, exist_ok=True)
        test_filename = f"test_{module_name}.py"
        test_filepath = os.path.join(tests_dir, test_filename)

        with open(test_filepath, "w", encoding="utf-8") as f:
            f.write(test_code)

        return (
            f"--- DARWIN TEST GENERATION ---\n"
            f"Module: {filename}\n"
            f"Test File: tests/{test_filename}\n"
            f"Tests Generated: {len(tools) + 1}\n"
            f"  - 1x Import Check\n"
            f"  - {len(tools)}x Callable Checks ({', '.join(tools)})\n"
            f"\nBoss, test file ban gaya hai! Run karo: python tests/{test_filename}"
        )

    except Exception as e:
        return f"--- TEST GENERATION ---\nStatus: ERROR\nError: {e}"


@function_tool
async def evolution_stats_tool() -> str:
    """
    Complete Darwin Evolution Engine statistics.
    Total modules, tools, lines of code, evolution events, backup count, system health.
    Poore evolution system ka comprehensive dashboard.
    """
    try:
        # Count all modules
        all_files = [f for f in os.listdir(PROJECT_ROOT) if f.startswith("shell_") and f.endswith(".py")]
        total_tools = 0
        total_lines = 0
        total_size = 0
        largest_file = ("", 0)
        most_tools_file = ("", 0)

        for f in all_files:
            fp = os.path.join(PROJECT_ROOT, f)
            size = os.path.getsize(fp)
            total_size += size
            if size > largest_file[1]:
                largest_file = (f, size)

            with open(fp, "r", encoding="utf-8") as fh:
                code = fh.read()
            lines = len(code.splitlines())
            total_lines += lines
            tools = _count_tools_in_code(code)
            total_tools += len(tools)
            if len(tools) > most_tools_file[1]:
                most_tools_file = (f, len(tools))

        # Evolution log stats
        log = _load_evolution_log()
        total_events = len(log)
        create_events = sum(1 for e in log if e.get("event") == "CREATE")
        hotpatch_events = sum(1 for e in log if e.get("event") == "HOTPATCH")
        rollback_events = sum(1 for e in log if e.get("event") == "ROLLBACK")

        # Backup stats
        backup_count = 0
        backup_size = 0
        if os.path.isdir(EVOLUTION_BACKUP_DIR):
            for bf in os.listdir(EVOLUTION_BACKUP_DIR):
                bfp = os.path.join(EVOLUTION_BACKUP_DIR, bf)
                if os.path.isfile(bfp):
                    backup_count += 1
                    backup_size += os.path.getsize(bfp)

        # Agent.py registered tools
        agent_path = os.path.join(PROJECT_ROOT, "agent.py")
        registered = 0
        if os.path.exists(agent_path):
            with open(agent_path, "r", encoding="utf-8") as f:
                agent_code = f.read()
            registered = agent_code.count("tools_list.append(") + agent_code.count("tools_list.extend(")

        report = [
            f"--- DARWIN EVOLUTION ENGINE STATS ---",
            f"{'=' * 45}",
            f"",
            f"[SYSTEM OVERVIEW]",
            f"  Total Modules: {len(all_files)}",
            f"  Total Tools: {total_tools}",
            f"  Total Lines of Code: {total_lines:,}",
            f"  Total Codebase Size: {round(total_size/1024, 1)} KB ({round(total_size/(1024*1024), 2)} MB)",
            f"  Largest Module: {largest_file[0]} ({round(largest_file[1]/1024, 1)} KB)",
            f"  Most Tools: {most_tools_file[0]} ({most_tools_file[1]} tools)",
            f"  Agent.py Tool Registrations: {registered}",
            f"",
            f"[EVOLUTION HISTORY]",
            f"  Total Events: {total_events}",
            f"  Creations: {create_events}",
            f"  Hotpatches: {hotpatch_events}",
            f"  Rollbacks: {rollback_events}",
            f"",
            f"[BACKUPS]",
            f"  Evolution Backups: {backup_count}",
            f"  Backup Size: {round(backup_size/1024, 1)} KB",
            f"",
            f"[ENGINE STATUS]",
            f"  Darwin Engine: LEVEL 999999",
            f"  Auto Safe-Executor Wrapping: ACTIVE",
            f"  Syntax Shield: ACTIVE",
            f"  Dependency Checker: ACTIVE",
            f"  Evolution Logging: ACTIVE",
            f"  Backup System: ACTIVE",
            f"",
            f"Boss, ye poore Darwin Evolution Engine ka full stats report hai. System fully operational!",
        ]

        return "\n".join(report)

    except Exception as e:
        return f"--- EVOLUTION STATS ---\nStatus: ERROR\nError: {e}"


@function_tool
async def find_unused_tools_tool() -> str:
    """
    Finds tools that exist in modules but are NOT registered in agent.py.
    Jo tools banaye hain lekin agent mein activate nahi kiye — unko dhundhta hai.
    Bohot useful for finding missing registrations.
    """
    try:
        agent_path = os.path.join(PROJECT_ROOT, "agent.py")
        if not os.path.exists(agent_path):
            return "--- UNUSED TOOLS REPORT ---\nStatus: agent.py NOT FOUND"

        with open(agent_path, "r", encoding="utf-8") as f:
            agent_code = f.read()

        all_files = [f for f in os.listdir(PROJECT_ROOT) if f.startswith("shell_") and f.endswith(".py")]

        registered_tools = []
        unregistered_tools = []
        module_tool_map = {}

        for filename in sorted(all_files):
            filepath = os.path.join(PROJECT_ROOT, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()

            tools = _count_tools_in_code(code)
            module_tool_map[filename] = tools

            for tool in tools:
                if tool in agent_code:
                    registered_tools.append((filename, tool))
                else:
                    unregistered_tools.append((filename, tool))

        report = [
            f"--- DARWIN UNUSED TOOLS REPORT ---",
            f"{'=' * 45}",
            f"Total Tools Found: {len(registered_tools) + len(unregistered_tools)}",
            f"Registered in agent.py: {len(registered_tools)}",
            f"NOT Registered: {len(unregistered_tools)}",
            f"",
        ]

        if unregistered_tools:
            report.append(f"[UNREGISTERED TOOLS] ({len(unregistered_tools)})")
            current_file = ""
            for filename, tool in unregistered_tools:
                if filename != current_file:
                    current_file = filename
                    report.append(f"\n  {filename}:")
                report.append(f"    -> {tool}")

            report.append(
                f"\nBoss, ye {len(unregistered_tools)} tools banaye hain lekin agent.py mein register nahi hain. "
                f"'hotpatch_agent_tool' se activate karo ya manually add karo."
            )
        else:
            report.append("Sab tools registered hain! Koi unused tool nahi mila.")

        return "\n".join(report)

    except Exception as e:
        return f"--- UNUSED TOOLS REPORT ---\nStatus: ERROR\nError: {e}"


@function_tool
async def dependency_check_tool(filename: str) -> str:
    """
    Checks all dependencies/imports of a module and reports which are available and which are missing.
    Module deploy karne se pehle dependency check karo — koi missing package toh nahi.
    Args:
        filename: File to check (e.g., 'shell_image_ai.py')
    """
    try:
        filepath = os.path.join(PROJECT_ROOT, filename)
        if not os.path.exists(filepath):
            return f"--- DEPENDENCY REPORT ---\nFile: {filename}\nStatus: FILE NOT FOUND"

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        result = _analyze_imports(code)
        if "error" in result:
            return f"--- DEPENDENCY REPORT ---\nFile: {filename}\nStatus: {result['error']}"

        imports = result.get("imports", [])
        missing = result.get("missing", [])

        report = [
            f"--- DARWIN DEPENDENCY REPORT ---",
            f"File: {filename}",
            f"Total Imports: {len(imports)}",
            f"Available: {len(imports) - len(missing)}",
            f"Missing: {len(missing)}",
            f"{'=' * 40}",
        ]

        for imp in imports:
            status = "AVAILABLE" if imp["available"] else "MISSING"
            icon = "  [OK]  " if imp["available"] else "  [MISS]"
            if imp["type"] == "from":
                names = ", ".join(imp.get("names", []))
                report.append(f"{icon} from {imp['module']} import {names}")
            else:
                report.append(f"{icon} import {imp['module']}")

        if missing:
            missing_names = list(set(m["module"].split(".")[0] for m in missing))
            report.append(f"\nInstall command:")
            report.append(f"  pip install {' '.join(missing_names)}")
            report.append(f"\nBoss, {len(missing)} dependencies missing hain. Upar install command hai.")
        else:
            report.append(f"\nBoss, sab dependencies available hain! Module safe hai deploy karne ke liye.")

        return "\n".join(report)

    except Exception as e:
        return f"--- DEPENDENCY REPORT ---\nStatus: ERROR\nError: {e}"


@function_tool
async def clone_module_tool(source: str, new_name: str) -> str:
    """
    Clones an existing module with a new name — perfect for creating variations.
    Ek module ka copy banata hai naye naam se — template ki tarah use karo.
    Args:
        source: Source file (e.g., 'shell_games.py')
        new_name: New module name without shell_ prefix (e.g., 'games_v2')
    """
    try:
        source_path = os.path.join(PROJECT_ROOT, source)
        if not os.path.exists(source_path):
            return f"--- CLONE REPORT ---\nSource: {source}\nStatus: FILE NOT FOUND"

        new_filename = f"shell_{new_name}.py"
        new_path = os.path.join(PROJECT_ROOT, new_filename)

        if os.path.exists(new_path):
            return (
                f"--- CLONE REPORT ---\n"
                f"Target: {new_filename}\n"
                f"Status: FILE ALREADY EXISTS\n"
                f"Boss, '{new_filename}' pehle se exist karta hai. Dusra naam do."
            )

        shutil.copy(source_path, new_path)

        source_size = os.path.getsize(source_path)
        with open(source_path, "r", encoding="utf-8") as f:
            tools = _count_tools_in_code(f.read())

        _log_evolution_event("CLONE", {
            "source": source,
            "target": new_filename,
            "tools": tools,
        })

        return (
            f"--- DARWIN CLONE REPORT ---\n"
            f"Source: {source}\n"
            f"Clone: {new_filename}\n"
            f"Size: {round(source_size/1024, 1)} KB\n"
            f"Tools Cloned: {len(tools)} -> {', '.join(tools)}\n"
            f"Status: CLONE SUCCESSFUL\n"
            f"\nBoss, '{source}' ka clone '{new_filename}' ban gaya. "
            f"Ab modify karo aur hotpatch se activate karo."
        )

    except Exception as e:
        return f"--- CLONE REPORT ---\nStatus: ERROR\nError: {e}"


@function_tool
async def search_in_modules_tool(query: str) -> str:
    """
    Searches for a string/pattern across ALL shell modules.
    Poore codebase mein kuch search karna ho toh ye use karo.
    Args:
        query: Search string or pattern (e.g., 'pyautogui', 'async def', 'psutil')
    """
    try:
        all_files = [f for f in os.listdir(PROJECT_ROOT) if f.startswith("shell_") and f.endswith(".py")]
        query_lower = query.lower()
        results = []

        for filename in sorted(all_files):
            filepath = os.path.join(PROJECT_ROOT, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            file_matches = []
            for i, line in enumerate(lines, 1):
                if query_lower in line.lower():
                    file_matches.append((i, line.strip()[:80]))

            if file_matches:
                results.append((filename, file_matches))

        if not results:
            return (
                f"--- DARWIN SEARCH ---\n"
                f"Query: '{query}'\n"
                f"Status: NO MATCHES\n"
                f"Boss, '{query}' kisi bhi shell module mein nahi mila."
            )

        total_matches = sum(len(m) for _, m in results)
        report = [
            f"--- DARWIN CODE SEARCH ---",
            f"Query: '{query}'",
            f"Files Matched: {len(results)}/{len(all_files)}",
            f"Total Matches: {total_matches}",
            f"{'=' * 45}",
        ]

        for filename, matches in results:
            report.append(f"\n  {filename} ({len(matches)} matches):")
            for line_no, line_text in matches[:5]:
                report.append(f"    L{line_no}: {line_text}")
            if len(matches) > 5:
                report.append(f"    ... aur {len(matches) - 5} matches")

        report.append(f"\nBoss, '{query}' ke {total_matches} matches mile {len(results)} files mein.")

        return "\n".join(report)

    except Exception as e:
        return f"--- SEARCH REPORT ---\nStatus: ERROR\nError: {e}"
