#!/usr/bin/env python3
"""
Shell JSON Tools — Format, Validate, Query, Convert & Merge JSON
"""
import os
import json
import csv
import copy
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_json_tools")


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: FORMAT / PRETTY-PRINT JSON
# ═══════════════════════════════════════════════════════════════

@function_tool
async def json_format_tool(json_string: str) -> str:
    """
    Pretty-print / format a JSON string with proper indentation.
    Args:
        json_string: Raw JSON string to format.
    """
    try:
        data = json.loads(json_string)
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        return f"Formatted JSON:\n{formatted}"
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"
    except Exception as e:
        return f"JSON formatting failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: VALIDATE JSON
# ═══════════════════════════════════════════════════════════════

@function_tool
async def json_validate_tool(json_string: str) -> str:
    """
    Validate if a string is valid JSON and report its structure.
    Args:
        json_string: The string to validate as JSON.
    """
    try:
        data = json.loads(json_string)
        type_name = type(data).__name__
        info_parts = [f"Valid JSON: Yes", f"Root type: {type_name}"]
        if isinstance(data, dict):
            info_parts.append(f"Keys ({len(data)}): {', '.join(list(data.keys())[:20])}")
            if len(data) > 20:
                info_parts[-1] += f" ... and {len(data) - 20} more"
        elif isinstance(data, list):
            info_parts.append(f"Items: {len(data)}")
            if data:
                info_parts.append(f"First item type: {type(data[0]).__name__}")
        info_parts.append(f"Size: {len(json_string)} chars")
        return "\n".join(info_parts)
    except json.JSONDecodeError as e:
        return (
            f"Valid JSON: No\n"
            f"Error: {e.msg}\n"
            f"Line: {e.lineno}, Column: {e.colno}\n"
            f"Position: {e.pos}"
        )


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: QUERY JSON FILE (DOT NOTATION)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def json_query_tool(filepath: str, key_path: str) -> str:
    """
    Query a JSON file using dot notation path.
    Supports nested keys and array indices (e.g., 'users.0.name', 'config.database.host').
    Args:
        filepath: Path to the JSON file.
        key_path: Dot-separated path to the value (e.g., 'users.0.name').
    """
    if not os.path.isfile(filepath):
        return f"File not found: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Navigate the path
        current = data
        parts = key_path.split(".")
        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    return f"Key '{part}' not found at path '{key_path}'.\nAvailable keys: {', '.join(current.keys())}"
                current = current[part]
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    return f"Invalid index '{part}' for array of length {len(current)} at path '{key_path}'."
            else:
                return f"Cannot navigate into {type(current).__name__} at '{part}' in path '{key_path}'."
        result = json.dumps(current, indent=2, ensure_ascii=False) if isinstance(current, (dict, list)) else str(current)
        return f"Query: {key_path}\nResult:\n{result}"
    except json.JSONDecodeError as e:
        return f"Invalid JSON in file: {e}"
    except Exception as e:
        return f"JSON query failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: CONVERT JSON ARRAY TO CSV
# ═══════════════════════════════════════════════════════════════

@function_tool
async def json_to_csv_tool(filepath: str, output: str) -> str:
    """
    Convert a JSON file containing an array of objects to CSV format.
    Args:
        filepath: Path to the JSON file (must contain an array of objects).
        output: Output CSV file path.
    """
    if not os.path.isfile(filepath):
        return f"File not found: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return "Error: JSON root must be an array of objects for CSV conversion."
        if not data:
            return "Error: JSON array is empty."
        if not isinstance(data[0], dict):
            return "Error: JSON array items must be objects (dicts) for CSV conversion."
        # Gather all unique keys across all objects
        all_keys = []
        seen = set()
        for item in data:
            if isinstance(item, dict):
                for key in item.keys():
                    if key not in seen:
                        all_keys.append(key)
                        seen.add(key)
        if not output.lower().endswith(".csv"):
            output += ".csv"
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            for item in data:
                if isinstance(item, dict):
                    # Flatten nested values to string
                    row = {}
                    for k in all_keys:
                        v = item.get(k, "")
                        row[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                    writer.writerow(row)
        return (
            f"JSON to CSV conversion successful.\n"
            f"Input: {filepath}\n"
            f"Output: {output}\n"
            f"Rows: {len(data)}\n"
            f"Columns: {len(all_keys)}\n"
            f"Headers: {', '.join(all_keys[:15])}"
            + (f" ... +{len(all_keys) - 15} more" if len(all_keys) > 15 else "")
        )
    except json.JSONDecodeError as e:
        return f"Invalid JSON in file: {e}"
    except Exception as e:
        return f"JSON to CSV conversion failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 5: DEEP MERGE TWO JSON FILES
# ═══════════════════════════════════════════════════════════════

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values win for conflicts."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = copy.deepcopy(value)
    return result


@function_tool
async def json_merge_tool(file1: str, file2: str, output: str) -> str:
    """
    Deep merge two JSON files into one.
    Dicts are recursively merged, lists are concatenated, and file2 values override file1 for conflicts.
    Args:
        file1: Path to the base JSON file.
        file2: Path to the override JSON file.
        output: Output path for the merged JSON file.
    """
    for path, label in [(file1, "File 1"), (file2, "File 2")]:
        if not os.path.isfile(path):
            return f"{label} not found: {path}"
    try:
        with open(file1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        with open(file2, "r", encoding="utf-8") as f:
            data2 = json.load(f)
        if isinstance(data1, dict) and isinstance(data2, dict):
            merged = _deep_merge(data1, data2)
        elif isinstance(data1, list) and isinstance(data2, list):
            merged = data1 + data2
        else:
            return (
                f"Cannot deep merge: file1 is {type(data1).__name__}, "
                f"file2 is {type(data2).__name__}. Both must be dicts or both lists."
            )
        if not output.lower().endswith(".json"):
            output += ".json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        return (
            f"JSON merge successful.\n"
            f"File 1: {file1}\n"
            f"File 2: {file2}\n"
            f"Output: {output}\n"
            f"Result type: {type(merged).__name__}\n"
            f"Result size: {os.path.getsize(output)} bytes"
        )
    except json.JSONDecodeError as e:
        return f"Invalid JSON in one of the files: {e}"
    except Exception as e:
        return f"JSON merge failed: {e}"
