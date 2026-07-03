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

"""Datei-Dialoge mit **fester** Fenstergröße.

Unter Linux verwendet Tk den in Tcl implementierten Dateidialog (``tkfbox``). Dessen
Toplevel ``.__tk_filedialog`` passt seine Größe an den aktuellen Ordnerpfad an — das
wirkt beim Öffnen unruhig/springend. Diese dünnen Wrapper um
``tkinter.filedialog`` erzwingen beim Erscheinen des Dialogs eine feste Größe.

Auf Plattformen mit **nativem** Dateidialog (Windows/macOS) existiert das
``.__tk_filedialog``-Fenster nicht; die Wrapper verhalten sich dann exakt wie die
Originalfunktionen (die Größen-Fixierung läuft dann ins Leere).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog

#: Name des (wiederverwendeten) nicht-nativen Tk-Dateidialog-Toplevels.
_DIALOG = ".__tk_filedialog"
#: Feste Standardgröße (Breite x Höhe).
_SIZE = "780x520"
#: Wie oft die Größe nach dem Öffnen kurz nachgesetzt wird (gegen tkfbox-Relayout).
_TICKS = 8
_INTERVAL = 50   # ms


def _pin_size(parent) -> None:
    """Erzwingt kurz nach dem Öffnen eine feste Größe des Tk-Dateidialogs."""
    if parent is None:
        return
    state = {"n": 0}

    def tick():
        state["n"] += 1
        try:
            if parent.tk.call("winfo", "exists", _DIALOG):
                parent.tk.call("wm", "geometry", _DIALOG, _SIZE)
        except tk.TclError:
            return
        if state["n"] < _TICKS:
            try:
                parent.after(_INTERVAL, tick)
            except tk.TclError:
                pass

    try:
        parent.after(20, tick)
    except tk.TclError:
        pass


def askopenfilename(*, parent=None, **kwargs):
    """Wie :func:`tkinter.filedialog.askopenfilename`, aber mit fester Fenstergröße."""
    _pin_size(parent)
    return filedialog.askopenfilename(parent=parent, **kwargs)


def asksaveasfilename(*, parent=None, **kwargs):
    """Wie :func:`tkinter.filedialog.asksaveasfilename`, aber mit fester Fenstergröße."""
    _pin_size(parent)
    return filedialog.asksaveasfilename(parent=parent, **kwargs)
