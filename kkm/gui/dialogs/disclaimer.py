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

"""Haftungshinweis beim Programmstart.

Das Tool spricht Hersteller-APIs (VAPIX, ONVIF, …) an, ist aber kein offizielles
Produkt dieser Hersteller. Beim Start erscheint darum ein Hinweis, bis der Nutzer
ihn per Checkbox dauerhaft bestätigt. Der Text wird auch im ``Über``-Reiter der
Einstellungen angezeigt (Import von :data:`DISCLAIMER_TEXT`).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from kkm.core import t
from kkm.gui import theme

#: Persistenz-Schlüssel in den AppSettings.
SETTINGS_KEY = "disclaimer_accepted"

#: Warntext — zentral, damit Startdialog und "Über"-Reiter identisch bleiben.
DISCLAIMER_TEXT = (
    "Achtung: Dies ist kein offizielles Tool der unterstützten Hersteller. "
    "Nutzung auf eigene Gefahr."
)


def show_if_needed(parent, settings) -> None:
    """Zeigt den Hinweis, solange er nicht dauerhaft bestätigt wurde.

    ``parent`` ist das Hauptfenster, ``settings`` die :class:`AppSettings`. Setzt
    der Nutzer die Checkbox und bestätigt, wird das in den Einstellungen vermerkt
    und der Dialog beim nächsten Start übersprungen.
    """
    if settings.get(SETTINGS_KEY, False):
        return
    DisclaimerDialog(parent, settings)


class DisclaimerDialog(tk.Toplevel):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.title(t("Haftungshinweis"))
        self.transient(parent)
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="⚠", font=("TkDefaultFont", 20)).grid(
            row=0, column=0, sticky=tk.N, padx=(0, 12))
        ttk.Label(frame, text=t(DISCLAIMER_TEXT), wraplength=360, justify=tk.LEFT,
                  foreground=theme.CURRENT.get("warn", "#c0392b"),
                  font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=1, sticky=tk.W)

        self._dont_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text=t("Ich weiß, was ich tue – nicht wieder anzeigen"),
            variable=self._dont_show).grid(row=1, column=1, sticky=tk.W, pady=(14, 0))

        ttk.Button(frame, text=t("OK"), command=self._close).grid(
            row=2, column=1, sticky=tk.E, pady=(16, 0))

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Return>", lambda _e: self._close())
        # Modal: blockiert das Hauptfenster, bis bestätigt wurde.
        self.update_idletasks()
        self._center_on(parent)
        self.grab_set()
        self.wait_window(self)

    def _center_on(self, parent):
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 3}")
        except tk.TclError:
            pass

    def _close(self):
        if self._dont_show.get():
            self.settings.set(SETTINGS_KEY, True)
        self.destroy()
