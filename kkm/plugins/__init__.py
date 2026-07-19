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
their default enabled state. The enabled/disabled state is then overridden from
persisted settings by the GUI's plugin manager.

Two kinds live here: manufacturer plugins (Axis) and the generic ONVIF plugin, which
speaks the standard and therefore works with *any* compliant camera — including the
Axis ones, where it can simply do less. It is therefore **off by default**: whoever
owns only Axis cameras gains nothing from it, and it is enabled in the plugin manager
when a third-party camera turns up.
"""

from kkm.core.plugins import PluginRegistry
from .axis import AxisPlugin
from .onvif import OnvifPlugin
from .hikvision import HikvisionPlugin

#: Plugins, die ohne gespeicherte Auswahl ausgeschaltet bleiben (generisches ONVIF
#: sowie noch nicht an Hardware verifizierte, experimentelle Hersteller-Plugins).
DEFAULT_OFF = {OnvifPlugin.id, HikvisionPlugin.id}


def build_registry(enabled_ids: list[str] | None = None) -> PluginRegistry:
    registry = PluginRegistry()
    available = [AxisPlugin(), HikvisionPlugin(), OnvifPlugin()]
    for plugin in available:
        if enabled_ids is None:
            default_on = plugin.id not in DEFAULT_OFF
        else:
            default_on = plugin.id in enabled_ids
        registry.register(plugin, enabled=default_on)
    return registry


__all__ = ["build_registry", "AxisPlugin", "OnvifPlugin", "HikvisionPlugin"]
