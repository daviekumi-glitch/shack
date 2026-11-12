"""Tool registry: the capabilities SHACK can actually perform."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable


class ToolError(RuntimeError):
    """Raised by a tool when the request cannot be carried out."""


@dataclass
class ToolContext:
    """Everything a tool may need, without importing the agent."""

    config: Any
    memory: Any
    brain: Any
    voice: Any
    confirm: Callable[[str], bool] | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., str]
    risky: bool = False
    group: str = "general"

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def add(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: Callable[..., str],
        risky: bool = False,
        group: str = "general",
    ) -> Tool:
        return self.register(
            Tool(name, description, parameters, func, risky=risky, group=group)
        )

    # ------------------------------------------------------------------ intro
    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def remove(self, name: str) -> None:
        self._tools.pop(name, None)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def by_group(self) -> dict[str, list[Tool]]:
        groups: dict[str, list[Tool]] = {}
        for tool in self._tools.values():
            groups.setdefault(tool.group, []).append(tool)
        return {k: sorted(v, key=lambda t: t.name) for k, v in sorted(groups.items())}

    def specs(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self._tools.values()]

    # ------------------------------------------------------------------- call
    def call(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool '{name}'. Available: {', '.join(self.names())}"
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return "Tool arguments must be a JSON object."

        signature = inspect.signature(tool.func)
        accepts_kwargs = any(
            p.kind is p.VAR_KEYWORD for p in signature.parameters.values()
        )
        allowed = {
            p.name
            for p in signature.parameters.values()
            if p.kind not in (p.VAR_KEYWORD, p.VAR_POSITIONAL)
        } - {"ctx"}

        kwargs = {k: v for k, v in arguments.items() if k in allowed}
        dropped = [k for k in arguments if k not in allowed]
        try:
            result = tool.func(ctx, **kwargs) if accepts_kwargs else tool.func(
                ctx, **kwargs
            )
        except ToolError as exc:
            return f"Tool '{name}' failed: {exc}"
        except TypeError as exc:
            return f"Tool '{name}' got bad arguments: {exc}"
        except Exception as exc:  # noqa: BLE001 - never let a tool kill the agent
            return f"Tool '{name}' crashed: {exc.__class__.__name__}: {exc}"

        text = result if isinstance(result, str) else json.dumps(result, default=str)
        if dropped:
            text += f"\n(ignored unknown arguments: {', '.join(dropped)})"
        return _trim(text)


def _trim(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n… (truncated)"
