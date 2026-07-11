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

"""Shared Tk widget helpers.

Auto-hiding scrollbars were a method of the main window; the action dialogs need the
same thing (a long camera list must scroll instead of pushing the dialog off a small
screen), so they live here now.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def _autohide(bar, row, column, sticky):
    """``set``-Callback, das *bar* nur einblendet, wenn der Inhalt nicht ganz passt."""
    def _set(first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            bar.grid_remove()
        else:
            bar.grid(row=row, column=column, sticky=sticky)
        bar.set(first, last)
    return _set


def add_scrollbars(container, widget):
    """Bettet *widget* per Grid in *container* ein und haengt auto-versteckende
    Scrollbalken an (vertikal rechts, horizontal unten)."""
    vbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=widget.yview)
    hbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=widget.xview)
    widget.configure(
        yscrollcommand=_autohide(vbar, row=0, column=1, sticky="ns"),
        xscrollcommand=_autohide(hbar, row=1, column=0, sticky="ew"),
    )
    widget.grid(row=0, column=0, sticky="nsew")
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
