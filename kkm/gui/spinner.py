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

"""A small indeterminate circular spinner.

Drop-in replacement for ``ttk.Progressbar(mode="indeterminate")``: it exposes the
same ``start(interval)`` / ``stop()`` interface and packs like any widget, so the
existing call sites (main window, action dialogs) stay unchanged. A faint full
ring (the *track*) is always drawn; while running, a brighter arc rotates on top.
Colours follow the active light/dark palette (:mod:`kkm.gui.theme`).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from kkm.gui import theme

#: Winkel-Schritt je Tick (Grad). Mit dem ueblichen Intervall von 12 ms ergibt das
#: eine ruhige, fluessige Drehung von gut einer Umdrehung pro Sekunde.
_STEP = 6
#: Laenge des hellen, laufenden Bogens (Grad).
_ARC_EXTENT = 90


class CircularSpinner(tk.Canvas):
    """Indeterminate circular busy indicator with a Progressbar-like API."""

    def __init__(self, parent, size: int = 22, width: int = 3, **kw):
        bg = self._theme_bg(parent)
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         bd=0, bg=bg, **kw)
        self._size = size
        self._line = width
        self._interval = 12
        self._angle = 90          # Startwinkel (12-Uhr-Position)
        self._job = None          # after()-Id, None = angehalten
        pad = width / 2 + 1
        self._bbox = (pad, pad, size - pad, size - pad)
        # Ruhender Track (voller Ring) + laufender Bogen (anfangs verborgen).
        self._track = self.create_arc(*self._bbox, start=0, extent=359.9,
                                      style=tk.ARC, width=width,
                                      outline=theme.CURRENT["track"])
        self._arc = self.create_arc(*self._bbox, start=self._angle,
                                    extent=_ARC_EXTENT, style=tk.ARC, width=width,
                                    outline=theme.CURRENT["accent"], state="hidden")

    # -- Farben -------------------------------------------------------------
    @staticmethod
    def _theme_bg(parent) -> str:
        """Hintergrund des umgebenden ttk-Containers, damit der Canvas nahtlos
        einfuegt (ttk-Themes faerben den Canvas nicht selbst)."""
        try:
            bg = ttk.Style(parent).lookup("TFrame", "background")
            if bg:
                return bg
        except tk.TclError:
            pass
        try:
            return parent.winfo_toplevel()["background"]
        except tk.TclError:
            return theme.CURRENT.get("text_bg", "#ffffff")

    def _refresh_colors(self):
        """Farben an die aktuelle Palette angleichen (nach Theme-Wechsel)."""
        try:
            self.configure(bg=self._theme_bg(self.master))
            self.itemconfigure(self._track, outline=theme.CURRENT["track"])
            self.itemconfigure(self._arc, outline=theme.CURRENT["accent"])
        except tk.TclError:
            pass

    # -- Progressbar-kompatible API ----------------------------------------
    def start(self, interval: int | None = None):
        """Animation starten. ``interval`` ist das Tick-Intervall in ms (wie bei
        ``ttk.Progressbar.start``); ohne Angabe bleibt der letzte Wert."""
        if interval:
            self._interval = max(1, int(interval))
        self._refresh_colors()
        try:
            self.itemconfigure(self._arc, state="normal")
        except tk.TclError:
            return
        if self._job is None:           # kein doppelter after()-Lauf
            self._tick()

    def _tick(self):
        self._angle = (self._angle - _STEP) % 360   # im Uhrzeigersinn
        try:
            self.itemconfigure(self._arc, start=self._angle)
        except tk.TclError:
            self._job = None
            return
        self._job = self.after(self._interval, self._tick)

    def stop(self):
        """Animation anhalten; nur der ruhende Track bleibt sichtbar."""
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        try:
            self.itemconfigure(self._arc, state="hidden")
        except tk.TclError:
            pass
