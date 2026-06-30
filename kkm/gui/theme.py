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

"""Modernes Erscheinungsbild über das Sun-Valley-ttk-Theme (Windows-11-Look).

Setzt das ttk-Theme via ``sv_ttk`` (gebündeltes Wheel) und ergänzt passende Farben
für die klassischen tk-Widgets (Text/Listbox/Menu), die ttk-Themes nicht abdecken.
``CURRENT`` hält die aktive Palette, damit Status-/Warnfarben themen-passend
gewählt werden können. Fehlt ``sv_ttk`` (z. B. nicht gebündelt), bleibt das
System-ttk-Theme aktiv — die App läuft trotzdem.
"""

from __future__ import annotations

_DARK = {
    "name": "dark",
    "online": "#51cf66", "offline": "#ff6b6b", "warn": "#ff6b6b",
    "text_bg": "#1c1c1c", "text_fg": "#fafafa", "sel": "#2f5d8a",
}
_LIGHT = {
    "name": "light",
    "online": "#2f9e44", "offline": "#e03131", "warn": "#c0392b",
    "text_bg": "#ffffff", "text_fg": "#1a1a1a", "sel": "#cfe3ff",
}

CURRENT = _LIGHT


def palette(mode: str) -> dict:
    return _DARK if mode == "dark" else _LIGHT


def apply_theme(root, mode: str) -> dict:
    """Aktiviert Hell/Dunkel; gibt die aktive Palette zurück."""
    global CURRENT
    CURRENT = palette(mode)
    try:
        import sv_ttk
        sv_ttk.set_theme("dark" if mode == "dark" else "light")
    except Exception:
        pass  # kein sv_ttk -> System-Theme, App läuft weiter

    p = CURRENT
    # Defaults für neu erzeugte klassische tk-Widgets (ttk-Themes erfassen sie nicht).
    for cls in ("Text", "Listbox"):
        root.option_add(f"*{cls}.background", p["text_bg"])
        root.option_add(f"*{cls}.foreground", p["text_fg"])
        root.option_add(f"*{cls}.insertBackground", p["text_fg"])
        root.option_add(f"*{cls}.selectBackground", p["sel"])
    root.option_add("*Menu.background", p["text_bg"])
    root.option_add("*Menu.foreground", p["text_fg"])
    return p
