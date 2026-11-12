"""Small precision tools: arithmetic, unit conversion, text stats."""

from __future__ import annotations

import ast
import math
import operator

from .registry import ToolContext, ToolError, ToolRegistry

_OPS = {
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

_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "floor": math.floor,
    "ceil": math.ceil, "factorial": math.factorial, "degrees": math.degrees,
    "radians": math.radians,
}

_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}

_UNITS = {
    "km": {"km": 1, "m": 1000, "mi": 0.621371, "ft": 3280.84},
    "kg": {"kg": 1, "g": 1000, "lb": 2.20462, "oz": 35.274},
    "c": {"c": 1, "f": None, "k": None},
    "litre": {"litre": 1, "ml": 1000, "gallon": 0.264172, "cup": 4.22675},
    "mb": {"mb": 1, "kb": 1024, "gb": 1 / 1024, "tb": 1 / 1024**2},
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ToolError("only numbers are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise ToolError(f"unknown name '{node.id}'")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise ToolError("that function is not allowed")
        if node.keywords:
            raise ToolError("keyword arguments are not allowed")
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(elt) for elt in node.elts]  # type: ignore[return-value]
    raise ToolError("unsupported expression")


def calculate(ctx: ToolContext, expression: str) -> str:
    expression = (expression or "").strip().replace("^", "**").replace("×", "*")
    expression = expression.replace("÷", "/").replace(",", "")
    if not expression:
        raise ToolError("nothing to calculate")
    if len(expression) > 300:
        raise ToolError("expression too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"could not read that expression ({exc.msg})") from exc
    try:
        value = _eval(tree)
    except ZeroDivisionError as exc:
        raise ToolError("division by zero") from exc
    except OverflowError as exc:
        raise ToolError("the number is too large") from exc
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return f"{expression} = {int(value)}"
    if isinstance(value, float):
        return f"{expression} = {value:.10g}"
    return f"{expression} = {value}"


def convert_units(ctx: ToolContext, value: float, from_unit: str, to_unit: str) -> str:
    f = (from_unit or "").lower().strip()
    t = (to_unit or "").lower().strip()
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ToolError("value must be a number") from exc

    if {f, t} <= {"c", "f", "k"}:
        celsius = {"c": value, "f": (value - 32) * 5 / 9, "k": value - 273.15}[f]
        result = {"c": celsius, "f": celsius * 9 / 5 + 32, "k": celsius + 273.15}[t]
        return f"{value:g}{f.upper()} = {result:.2f}{t.upper()}"

    for table in _UNITS.values():
        if f in table and t in table and table[f] and table[t]:
            base = value / table[f]
            return f"{value:g} {f} = {base * table[t]:.4g} {t}"
    raise ToolError(f"I cannot convert {from_unit} to {to_unit}")


def text_stats(ctx: ToolContext, text: str) -> str:
    words = [w for w in (text or "").split() if w]
    return (
        f"{len(text or '')} characters, {len(words)} words, "
        f"{len((text or '').splitlines()) or 1} lines"
    )


def register(registry: ToolRegistry) -> None:
    registry.add(
        "calculate",
        "Evaluate arithmetic exactly. Supports + - * / ** % parentheses and "
        "functions like sqrt, log, sin, cos, factorial. Use it instead of "
        "guessing at maths.",
        {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. (1200*0.35)+45"}},
            "required": ["expression"],
        },
        calculate,
        group="utility",
    )
    registry.add(
        "convert_units",
        "Convert between units: km/m/mi/ft, kg/g/lb/oz, celsius/fahrenheit/kelvin, "
        "litres/gallons/cups, MB/GB/TB.",
        {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "from_unit": {"type": "string"},
                "to_unit": {"type": "string"},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
        convert_units,
        group="utility",
    )
    registry.add(
        "text_stats",
        "Count characters, words and lines in a piece of text.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        text_stats,
        group="utility",
    )
