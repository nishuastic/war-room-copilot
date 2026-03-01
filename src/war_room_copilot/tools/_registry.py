"""Auto-generate OpenAI tool schemas from LiveKit FunctionTool metadata."""

from __future__ import annotations

import inspect
import re
from typing import Any, get_type_hints


def _python_type_to_json(annotation: Any) -> str:
    """Map a Python type annotation to a JSON Schema type string."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return "string"
    origin = getattr(annotation, "__origin__", None)
    # Handle Optional[X] (Union[X, None])
    if origin is type(None):
        return "string"
    name = getattr(annotation, "__name__", str(annotation))
    if name in ("int", "integer"):
        return "integer"
    if name in ("float", "number"):
        return "number"
    if name in ("bool", "boolean"):
        return "boolean"
    return "string"


def _parse_args_section(docstring: str) -> dict[str, str]:
    """Extract param descriptions from a Google-style ``Args:`` docstring section."""
    descriptions: dict[str, str] = {}
    match = re.search(r"Args:\s*\n((?:\s+\S.*\n?)+)", docstring)
    if not match:
        return descriptions
    block = match.group(1)
    for line_match in re.finditer(r"^\s+(\w+):\s*(.+?)$", block, re.MULTILINE):
        descriptions[line_match.group(1)] = line_match.group(2).strip()
    return descriptions


def tool_to_openai_schema(ft: Any) -> dict[str, Any]:
    """Convert a LiveKit ``FunctionTool`` to an OpenAI-compatible tool schema dict."""
    # Get the underlying function — LiveKit stores it as _func
    raw_fn = getattr(ft, "_func", None) or getattr(ft, "__wrapped__", ft)

    sig = inspect.signature(raw_fn)
    try:
        hints = get_type_hints(raw_fn)
    except Exception:
        hints = {}

    tool_name: str = ft.info.name
    docstring = inspect.getdoc(raw_fn) or ""
    # First line of docstring is the description
    description = docstring.split("\n")[0].strip() if docstring else tool_name

    arg_descriptions = _parse_args_section(docstring)

    properties: dict[str, dict[str, str]] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        json_type = _python_type_to_json(hints.get(param_name, param.annotation))
        prop: dict[str, str] = {"type": json_type}
        if param_name in arg_descriptions:
            prop["description"] = arg_descriptions[param_name]
        properties[param_name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def get_openai_schemas(tools: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate OpenAI tool schemas for a dict of name -> FunctionTool."""
    return [tool_to_openai_schema(ft) for ft in tools.values()]
