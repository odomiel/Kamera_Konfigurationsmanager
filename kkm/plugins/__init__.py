# Kamera_Konfigurationsmanager - Plugin-basierter Konfigurationsmanager fuer Netzwerkkameras.
# Copyright (C) 2026 Mirik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
