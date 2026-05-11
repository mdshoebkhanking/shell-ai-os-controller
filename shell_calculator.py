"""
Shell Calculator Tools v1.0
------------------------------
Safe math calculation tools for Shell AI.
Expression evaluation, unit conversion, percentages, statistics, and base conversion.

All tools use Python stdlib only (math, statistics, ast). No eval() is used.

Usage:
    from shell_safe_executor import god_tier_tool as function_tool
"""

import ast
import math
import operator
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_calculator")


# Safe math expression evaluator using AST
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "radians": math.radians,
    "degrees": math.degrees,
    "pow": pow,
    "hypot": math.hypot,
}

_SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}


def _safe_eval_node(node):
    """Recursively evaluate an AST node safely."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        # Prevent extremely large exponents
        if op_type == ast.Pow and isinstance(right, (int, float)) and abs(right) > 1000:
            raise ValueError("Exponent too large (max 1000).")
        return _SAFE_OPERATORS[op_type](left, right)

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval_node(node.operand)
        return _SAFE_OPERATORS[op_type](operand)

    elif isinstance(node, ast.Name):
        name = node.id.lower()
        if name in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[name]
        raise ValueError(
            f"Unknown variable: '{node.id}'. "
            f"Available constants: {', '.join(_SAFE_CONSTANTS.keys())}"
        )

    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are supported.")
        func_name = node.func.id.lower()
        if func_name not in _SAFE_FUNCTIONS:
            raise ValueError(
                f"Unknown function: '{node.func.id}'. "
                f"Available: {', '.join(sorted(_SAFE_FUNCTIONS.keys()))}"
            )
        args = [_safe_eval_node(arg) for arg in node.args]
        return _SAFE_FUNCTIONS[func_name](*args)

    else:
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def _safe_calculate(expression: str):
    """Safely evaluate a math expression using AST parsing."""
    # Normalize common patterns
    expr = expression.strip()
    expr = expr.replace("^", "**")  # caret to power
    expr = expr.replace("x", "*").replace("X", "*")  # x as multiply (only lowercase)

    tree = ast.parse(expr, mode="eval")
    return _safe_eval_node(tree)


# Unit conversion tables
_UNIT_CONVERSIONS = {
    # Length
    ("km", "miles"): lambda v: v * 0.621371,
    ("miles", "km"): lambda v: v * 1.60934,
    ("m", "ft"): lambda v: v * 3.28084,
    ("ft", "m"): lambda v: v * 0.3048,
    ("cm", "in"): lambda v: v * 0.393701,
    ("in", "cm"): lambda v: v * 2.54,
    ("m", "cm"): lambda v: v * 100,
    ("cm", "m"): lambda v: v / 100,
    ("m", "km"): lambda v: v / 1000,
    ("km", "m"): lambda v: v * 1000,
    ("miles", "ft"): lambda v: v * 5280,
    ("ft", "miles"): lambda v: v / 5280,
    ("yard", "m"): lambda v: v * 0.9144,
    ("m", "yard"): lambda v: v * 1.09361,
    ("mm", "in"): lambda v: v * 0.0393701,
    ("in", "mm"): lambda v: v * 25.4,

    # Weight
    ("kg", "lbs"): lambda v: v * 2.20462,
    ("lbs", "kg"): lambda v: v * 0.453592,
    ("g", "oz"): lambda v: v * 0.035274,
    ("oz", "g"): lambda v: v * 28.3495,
    ("kg", "g"): lambda v: v * 1000,
    ("g", "kg"): lambda v: v / 1000,
    ("lbs", "oz"): lambda v: v * 16,
    ("oz", "lbs"): lambda v: v / 16,
    ("ton", "kg"): lambda v: v * 907.185,
    ("kg", "ton"): lambda v: v / 907.185,

    # Temperature
    ("c", "f"): lambda v: (v * 9 / 5) + 32,
    ("f", "c"): lambda v: (v - 32) * 5 / 9,
    ("c", "k"): lambda v: v + 273.15,
    ("k", "c"): lambda v: v - 273.15,
    ("f", "k"): lambda v: (v - 32) * 5 / 9 + 273.15,
    ("k", "f"): lambda v: (v - 273.15) * 9 / 5 + 32,

    # Volume
    ("l", "gal"): lambda v: v * 0.264172,
    ("gal", "l"): lambda v: v * 3.78541,
    ("ml", "oz_fl"): lambda v: v * 0.033814,
    ("oz_fl", "ml"): lambda v: v * 29.5735,
    ("l", "ml"): lambda v: v * 1000,
    ("ml", "l"): lambda v: v / 1000,

    # Speed
    ("kmh", "mph"): lambda v: v * 0.621371,
    ("mph", "kmh"): lambda v: v * 1.60934,
    ("ms", "kmh"): lambda v: v * 3.6,
    ("kmh", "ms"): lambda v: v / 3.6,

    # Data
    ("kb", "mb"): lambda v: v / 1024,
    ("mb", "kb"): lambda v: v * 1024,
    ("mb", "gb"): lambda v: v / 1024,
    ("gb", "mb"): lambda v: v * 1024,
    ("gb", "tb"): lambda v: v / 1024,
    ("tb", "gb"): lambda v: v * 1024,

    # Time
    ("min", "sec"): lambda v: v * 60,
    ("sec", "min"): lambda v: v / 60,
    ("hr", "min"): lambda v: v * 60,
    ("min", "hr"): lambda v: v / 60,
    ("hr", "sec"): lambda v: v * 3600,
    ("sec", "hr"): lambda v: v / 3600,
    ("day", "hr"): lambda v: v * 24,
    ("hr", "day"): lambda v: v / 24,
}


# ================================================================
#  TOOL 1: CALCULATE EXPRESSION
# ================================================================

@function_tool
async def calculate_tool(expression: str) -> str:
    """
    Safely evaluate a mathematical expression. Supports +, -, *, /, //, %, **,
    and functions like sqrt, sin, cos, tan, log, abs, round, factorial, etc.
    Constants: pi, e, tau. Uses a safe AST parser (NO eval).
    Args:
        expression: Math expression to evaluate (e.g., '2 + 3 * 4', 'sqrt(144)', 'sin(pi/2)').
    """
    if not expression or not expression.strip():
        return "Error: No expression provided."

    try:
        result = _safe_calculate(expression)

        # Format result nicely
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                formatted = str(int(result))
            else:
                formatted = f"{result:.10g}"
        else:
            formatted = str(result)

        return (
            f"Expression: {expression.strip()}\n"
            f"Result: {formatted}"
        )
    except ZeroDivisionError:
        return "Error: Division by zero."
    except ValueError as e:
        return f"Error: {e}"
    except SyntaxError:
        return (
            f"Error: Invalid expression syntax: '{expression}'.\n"
            "Examples: '2 + 3 * 4', 'sqrt(144)', 'sin(pi / 2)', '2 ** 10'"
        )
    except Exception as e:
        return f"Error evaluating expression: {e}"


# ================================================================
#  TOOL 2: UNIT CONVERSION
# ================================================================

@function_tool
async def unit_convert_tool(value: float, from_unit: str, to_unit: str) -> str:
    """
    Convert between common units of measurement.
    Supports: length (km, miles, m, ft, cm, in), weight (kg, lbs, g, oz),
    temperature (C, F, K), volume (L, gal, ml), speed (kmh, mph),
    data (KB, MB, GB, TB), time (sec, min, hr, day).
    Args:
        value: The numeric value to convert.
        from_unit: Source unit (e.g., 'km', 'lbs', 'C').
        to_unit: Target unit (e.g., 'miles', 'kg', 'F').
    """
    from_u = from_unit.strip().lower()
    to_u = to_unit.strip().lower()

    key = (from_u, to_u)

    if key not in _UNIT_CONVERSIONS:
        # List available conversions for this from_unit
        available = [
            f"{f} -> {t}"
            for f, t in _UNIT_CONVERSIONS.keys()
            if f == from_u or t == from_u
        ]
        if available:
            return (
                f"Error: Cannot convert '{from_unit}' to '{to_unit}'.\n"
                f"Available conversions for '{from_unit}':\n" +
                "\n".join(f"  - {a}" for a in available)
            )
        else:
            all_units = sorted(set(
                u for pair in _UNIT_CONVERSIONS.keys() for u in pair
            ))
            return (
                f"Error: Unknown unit '{from_unit}'.\n"
                f"Available units: {', '.join(all_units)}"
            )

    try:
        result = _UNIT_CONVERSIONS[key](value)

        if isinstance(result, float):
            formatted = f"{result:.6g}"
        else:
            formatted = str(result)

        return (
            f"Unit Conversion:\n"
            f"  {value} {from_unit} = {formatted} {to_unit}"
        )
    except Exception as e:
        return f"Error converting units: {e}"


# ================================================================
#  TOOL 3: PERCENTAGE CALCULATOR
# ================================================================

@function_tool
async def percentage_tool(value: float, percentage: float) -> str:
    """
    Calculate percentage of a value and related percentage operations.
    Args:
        value: The base number.
        percentage: The percentage to calculate.
    Returns:
        Multiple percentage calculations for the given inputs.
    """
    try:
        pct_of_value = value * (percentage / 100)
        value_plus_pct = value + pct_of_value
        value_minus_pct = value - pct_of_value
        what_pct = (percentage / value * 100) if value != 0 else float("inf")

        return (
            f"Percentage Calculations:\n"
            f"{'=' * 40}\n"
            f"  {percentage}% of {value} = {pct_of_value:.6g}\n"
            f"  {value} + {percentage}% = {value_plus_pct:.6g}\n"
            f"  {value} - {percentage}% = {value_minus_pct:.6g}\n"
            f"  {percentage} is {what_pct:.4g}% of {value}"
        )
    except Exception as e:
        return f"Error calculating percentage: {e}"


# ================================================================
#  TOOL 4: STATISTICS
# ================================================================

@function_tool
async def statistics_tool(numbers: str) -> str:
    """
    Calculate statistical measures from a list of numbers.
    Returns mean, median, mode, standard deviation, variance, min, max, sum, and count.
    Args:
        numbers: Comma-separated list of numbers (e.g., '1, 2, 3, 4, 5').
    """
    import statistics as stats_module

    if not numbers or not numbers.strip():
        return "Error: No numbers provided. Use comma-separated values like '1, 2, 3, 4, 5'."

    try:
        # Parse numbers
        num_list = []
        for part in numbers.split(","):
            part = part.strip()
            if part:
                num_list.append(float(part))

        if not num_list:
            return "Error: Could not parse any numbers from input."

        if len(num_list) < 2:
            return "Error: Need at least 2 numbers for statistics."

        n = len(num_list)
        mean = stats_module.mean(num_list)
        median = stats_module.median(num_list)
        stdev = stats_module.stdev(num_list)
        variance = stats_module.variance(num_list)
        total = sum(num_list)
        minimum = min(num_list)
        maximum = max(num_list)
        data_range = maximum - minimum

        # Mode (may have multiple or no mode)
        try:
            mode = stats_module.mode(num_list)
            mode_str = f"{mode:.6g}"
        except stats_module.StatisticsError:
            mode_str = "No unique mode"

        # Quartiles
        sorted_nums = sorted(num_list)
        q1_idx = n // 4
        q3_idx = (3 * n) // 4

        lines = [
            f"Statistics for {n} numbers:",
            f"{'=' * 40}",
            f"  Count    : {n}",
            f"  Sum      : {total:.6g}",
            f"  Mean     : {mean:.6g}",
            f"  Median   : {median:.6g}",
            f"  Mode     : {mode_str}",
            f"  Std Dev  : {stdev:.6g}",
            f"  Variance : {variance:.6g}",
            f"  Min      : {minimum:.6g}",
            f"  Max      : {maximum:.6g}",
            f"  Range    : {data_range:.6g}",
        ]

        return "\n".join(lines)
    except ValueError as e:
        return f"Error: Invalid number in input. {e}"
    except Exception as e:
        return f"Error calculating statistics: {e}"


# ================================================================
#  TOOL 5: BASE CONVERSION
# ================================================================

@function_tool
async def base_convert_tool(number: str, from_base: int, to_base: int) -> str:
    """
    Convert a number between bases (binary, octal, decimal, hexadecimal, etc.).
    Supports bases 2 through 36.
    Args:
        number: The number to convert as a string (e.g., '1010', 'FF', '42').
        from_base: Source base (2-36). Common: 2=binary, 8=octal, 10=decimal, 16=hex.
        to_base: Target base (2-36).
    """
    if from_base < 2 or from_base > 36:
        return f"Error: from_base must be between 2 and 36, got {from_base}."
    if to_base < 2 or to_base > 36:
        return f"Error: to_base must be between 2 and 36, got {to_base}."

    number = number.strip()

    # Remove common prefixes
    clean_number = number
    if from_base == 16 and clean_number.lower().startswith("0x"):
        clean_number = clean_number[2:]
    elif from_base == 2 and clean_number.lower().startswith("0b"):
        clean_number = clean_number[2:]
    elif from_base == 8 and clean_number.lower().startswith("0o"):
        clean_number = clean_number[2:]

    try:
        # Convert from source base to decimal
        decimal_value = int(clean_number, from_base)
    except ValueError:
        return f"Error: '{number}' is not a valid base-{from_base} number."

    # Convert from decimal to target base
    try:
        if to_base == 10:
            result = str(decimal_value)
        elif to_base == 2:
            result = bin(decimal_value)[2:]
        elif to_base == 8:
            result = oct(decimal_value)[2:]
        elif to_base == 16:
            result = hex(decimal_value)[2:].upper()
        else:
            # General base conversion
            if decimal_value == 0:
                result = "0"
            else:
                digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                parts = []
                n = abs(decimal_value)
                while n > 0:
                    parts.append(digits[n % to_base])
                    n //= to_base
                if decimal_value < 0:
                    parts.append("-")
                result = "".join(reversed(parts))

        base_names = {2: "Binary", 8: "Octal", 10: "Decimal", 16: "Hexadecimal"}
        from_name = base_names.get(from_base, f"Base-{from_base}")
        to_name = base_names.get(to_base, f"Base-{to_base}")

        return (
            f"Base Conversion:\n"
            f"  {from_name} (base {from_base}): {number}\n"
            f"  {to_name} (base {to_base}): {result}\n"
            f"  Decimal value: {decimal_value}"
        )
    except Exception as e:
        return f"Error converting base: {e}"
