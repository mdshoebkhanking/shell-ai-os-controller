#!/usr/bin/env python3
"""
Shell Regex Tools — Match, Replace, Test & Extract with Regular Expressions
"""
import os
import re
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_regex")


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: REGEX MATCH — Find all matches in text
# ═══════════════════════════════════════════════════════════════

@function_tool
async def regex_match_tool(pattern: str, text: str) -> str:
    """
    Find all matches of a regex pattern in text.
    Args:
        pattern: Regular expression pattern.
        text: The text to search in.
    """
    try:
        compiled = re.compile(pattern)
        matches = compiled.findall(text)
        if not matches:
            return f"No matches found for pattern: {pattern}"
        lines = [f"Pattern: {pattern}", f"Matches found: {len(matches)}", ""]
        for i, match in enumerate(matches[:100], 1):
            if isinstance(match, tuple):
                lines.append(f"  {i}. {' | '.join(match)}")
            else:
                lines.append(f"  {i}. {match}")
        if len(matches) > 100:
            lines.append(f"\n  ... and {len(matches) - 100} more matches")
        return "\n".join(lines)
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    except Exception as e:
        return f"Regex match failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: REGEX REPLACE — Find and replace in text
# ═══════════════════════════════════════════════════════════════

@function_tool
async def regex_replace_tool(pattern: str, replacement: str, text: str) -> str:
    """
    Perform regex find and replace on text.
    Supports backreferences in replacement (e.g., \\1, \\g<name>).
    Args:
        pattern: Regular expression pattern to find.
        replacement: Replacement string (supports backreferences).
        text: The text to perform replacement on.
    """
    try:
        result, count = re.subn(pattern, replacement, text)
        if count == 0:
            return f"No matches found for pattern: {pattern}\nOriginal text returned unchanged."
        return (
            f"Replacements made: {count}\n"
            f"Pattern: {pattern}\n"
            f"Replacement: {replacement}\n"
            f"\nResult:\n{result}"
        )
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    except Exception as e:
        return f"Regex replace failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: REGEX TEST — Test pattern and show groups
# ═══════════════════════════════════════════════════════════════

@function_tool
async def regex_test_tool(pattern: str, test_string: str) -> str:
    """
    Test if a regex pattern matches a string. Shows full match, groups, and named groups.
    Args:
        pattern: Regular expression pattern to test.
        test_string: The string to test against.
    """
    try:
        compiled = re.compile(pattern)
        match = compiled.search(test_string)
        if not match:
            return (
                f"Pattern: {pattern}\n"
                f"String: {test_string}\n"
                f"Result: NO MATCH"
            )
        lines = [
            f"Pattern: {pattern}",
            f"String: {test_string}",
            f"Result: MATCH",
            f"",
            f"Full match: '{match.group(0)}'",
            f"Span: {match.start()} - {match.end()}",
        ]
        # Numbered groups
        if match.groups():
            lines.append(f"\nCapture groups ({len(match.groups())}):")
            for i, group in enumerate(match.groups(), 1):
                lines.append(f"  Group {i}: '{group}'")
        # Named groups
        if match.groupdict():
            lines.append(f"\nNamed groups:")
            for name, value in match.groupdict().items():
                lines.append(f"  {name}: '{value}'")
        # Show all matches
        all_matches = compiled.finditer(test_string)
        match_list = list(all_matches)
        if len(match_list) > 1:
            lines.append(f"\nTotal matches in string: {len(match_list) + 1}")
        return "\n".join(lines)
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    except Exception as e:
        return f"Regex test failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: REGEX EXTRACT — Extract matches from a file
# ═══════════════════════════════════════════════════════════════

@function_tool
async def regex_extract_tool(pattern: str, filepath: str) -> str:
    """
    Extract all regex matches from a file. Reports matches with line numbers.
    Args:
        pattern: Regular expression pattern to search for.
        filepath: Path to the file to search in.
    """
    if not os.path.isfile(filepath):
        return f"File not found: {filepath}"
    try:
        compiled = re.compile(pattern)
        results = []
        total_matches = 0
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                matches = compiled.findall(line)
                if matches:
                    for match in matches:
                        total_matches += 1
                        if isinstance(match, tuple):
                            match_str = " | ".join(match)
                        else:
                            match_str = match
                        results.append(f"  Line {line_num}: {match_str}")
                        if total_matches >= 200:
                            break
                if total_matches >= 200:
                    break
        if not results:
            return (
                f"No matches found.\n"
                f"Pattern: {pattern}\n"
                f"File: {filepath}"
            )
        lines = [
            f"Pattern: {pattern}",
            f"File: {os.path.basename(filepath)}",
            f"Matches found: {total_matches}",
            "",
        ]
        lines.extend(results)
        if total_matches >= 200:
            lines.append("\n  ... output limited to 200 matches")
        return "\n".join(lines)
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    except Exception as e:
        return f"Regex extract failed: {e}"
