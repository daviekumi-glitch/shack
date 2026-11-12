"""Tool packs for SHACK. Import `build_registry` to get everything wired up."""

from __future__ import annotations

from .registry import Tool, ToolContext, ToolError, ToolRegistry
from . import knowledge, shell, system, utility, web

__all__ = [
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolRegistry",
    "build_registry",
]


def build_registry(with_shell: bool = True) -> ToolRegistry:
    registry = ToolRegistry()
    system.register(registry)
    web.register(registry)
    utility.register(registry)
    knowledge.register(registry)
    if with_shell:
        shell.register(registry)
    return registry
