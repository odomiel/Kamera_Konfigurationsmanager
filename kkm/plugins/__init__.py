"""Vendor plugins.

``build_registry()`` is the single place that wires up which plugins exist and
their default enabled state. Currently only Axis; future manufacturers register
here. The enabled/disabled state is then overridden from persisted settings by
the GUI's plugin manager.
"""

from kkm.core.plugins import PluginRegistry
from .axis import AxisPlugin


def build_registry(enabled_ids: list[str] | None = None) -> PluginRegistry:
    registry = PluginRegistry()
    available = [AxisPlugin()]
    for plugin in available:
        default_on = enabled_ids is None or plugin.id in enabled_ids
        registry.register(plugin, enabled=default_on)
    return registry


__all__ = ["build_registry", "AxisPlugin"]
