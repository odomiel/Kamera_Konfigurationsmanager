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

"""Re-authentication prompt shown mid-action when a camera rejects the credentials.

When an action fails with HTTP 401 (typically because the password was changed
*outside* the program and the vault entry is now stale), the action dialog collects
the affected cameras and asks once for a fresh password; the action is then retried
for those cameras. The choice is returned in :attr:`result` as
``(action, username, password, store)`` with action ``"apply"`` / ``"cancel"``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from kkm.core import get_first_ip, t


class ReauthPromptDialog(tk.Toplevel):
    def __init__(self, parent, cameras, default_user="admin", can_store=False):
        super().__init__(parent)
        self.title(t("Passwort erneut eingeben"))
        self.transient(parent)
        self.grab_set()
        self.result = None

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        n = len(cameras)
        if n == 1:
            cam = cameras[0]
            head = t("Zugangsdaten abgelehnt für: {name} ({ip})",
                     name=cam.get("Name", "?"), ip=get_first_ip(cam) or "—")
        else:
            head = t("Zugangsdaten bei {n} Kamera(s) abgelehnt.", n=n)
        ttk.Label(frame, text=head, font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(frame, wraplength=380, justify=tk.LEFT,
                  text=t("Das gespeicherte Passwort stimmt nicht mehr (evtl. außerhalb des "
                         "Programms geändert). Bitte das aktuelle Passwort eingeben — die "
                         "Aktion wird damit erneut versucht.")).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 8))

        self.user = tk.StringVar(value=default_user or "admin")
        self.pw = tk.StringVar()
        self.store = tk.BooleanVar(value=can_store)

        ttk.Label(frame, text=t("Benutzer:")).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame, textvariable=self.user, width=24).grid(
            row=2, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(frame, text=t("Passwort:")).grid(row=3, column=0, sticky=tk.W, pady=2)
        pw_entry = ttk.Entry(frame, textvariable=self.pw, width=24, show="*")
        pw_entry.grid(row=3, column=1, sticky=tk.W, padx=4, pady=2)

        # Nur anbieten, wenn der Tresor entsperrt ist — sonst bringt Speichern nichts.
        chk = ttk.Checkbutton(
            frame, variable=self.store,
            text=t("Neues Passwort im Tresor aktualisieren"))
        chk.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(8, 4))
        if not can_store:
            chk.state(["disabled"])

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(8, 0))
        ttk.Button(btns, text=t("Erneut versuchen"), command=self._apply).pack(side=tk.RIGHT)
        ttk.Button(btns, text=t("Abbrechen"), command=self._cancel).pack(side=tk.RIGHT, padx=6)

        pw_entry.focus_set()
        self.bind("<Return>", lambda _e: self._apply())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _apply(self):
        self.result = ("apply", self.user.get().strip() or "admin",
                       self.pw.get(), bool(self.store.get()))
        self.destroy()

    def _cancel(self):
        self.result = ("cancel", None, None, False)
        self.destroy()
