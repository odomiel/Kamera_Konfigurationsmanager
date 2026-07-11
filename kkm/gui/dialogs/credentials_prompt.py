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

"""Credential prompt shown after a search for cameras with unknown credentials.

Asks for username/password for one camera and offers a checkbox to try the entered
password on *all* cameras whose credentials are still unknown. Working credentials
are saved by the caller (vault / session). Used modally via ``wait_window``; the
choice is returned in :attr:`result` as ``(action, user, password, try_all)`` with
action ``"apply"`` / ``"skip"`` / ``"cancel"``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class CredentialPromptDialog(tk.Toplevel):
    def __init__(self, parent, camera, remaining):
        super().__init__(parent)
        self.title("Zugangsdaten benötigt")
        self.transient(parent)
        self.grab_set()
        self.result = None

        from kkm.core import get_first_ip
        name = camera.get("Name", "?")
        ip = get_first_ip(camera) or "—"

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Zugangsdaten für: {name} ({ip})",
                  font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(frame, text=f"Noch {remaining} Kamera(s) ohne gespeicherte Zugangsdaten.").grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        self.user = tk.StringVar(value="root")
        self.pw = tk.StringVar()
        self.try_all = tk.BooleanVar(value=True)

        ttk.Label(frame, text="Benutzer:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame, textvariable=self.user, width=24).grid(
            row=2, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(frame, text="Passwort:").grid(row=3, column=0, sticky=tk.W, pady=2)
        pw_entry = ttk.Entry(frame, textvariable=self.pw, width=24, show="*")
        pw_entry.grid(row=3, column=1, sticky=tk.W, padx=4, pady=2)

        ttk.Checkbutton(
            frame,
            text="Dieses Passwort bei allen Kameras mit unbekannten Zugangsdaten ausprobieren",
            variable=self.try_all).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(8, 4))

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(8, 0))
        ttk.Button(btns, text="Anwenden", command=self._apply).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Überspringen", command=self._skip).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Abbrechen", command=self._cancel).pack(side=tk.RIGHT)

        pw_entry.focus_set()
        self.bind("<Return>", lambda _e: self._apply())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _apply(self):
        self.result = ("apply", self.user.get().strip() or "root",
                       self.pw.get(), self.try_all.get())
        self.destroy()

    def _skip(self):
        self.result = ("skip", None, None, False)
        self.destroy()

    def _cancel(self):
        self.result = ("cancel", None, None, False)
        self.destroy()
