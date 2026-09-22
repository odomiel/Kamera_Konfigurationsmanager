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

"""Rueckfrage, wenn sich das HTTPS-Zertifikat einer Kamera geaendert hat.

Der Aktionsdialog sammelt die betroffenen Kameras eines Durchlaufs (Verbindung wurde
vor dem Senden von Zugangsdaten abgebrochen, siehe :mod:`kkm.core.certpin`) und
fragt einmal nach. :attr:`result` ist ``True``, wenn die neuen Zertifikate
uebernommen und die Aktion fuer diese Kameras wiederholt werden soll.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from kkm.core import get_first_ip, t
from kkm.core.certpin import short_fp


class CertMismatchDialog(tk.Toplevel):
    def __init__(self, parent, failures):
        """*failures*: Liste von ``(camera, CertMismatch)``."""
        super().__init__(parent)
        self.title(t("Zertifikat geändert"))
        self.transient(parent)
        self.grab_set()
        self.result = False

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        from kkm.gui import theme
        ttk.Label(frame, text=t("⚠ Das HTTPS-Zertifikat hat sich geändert ({n} Kamera(s))",
                                n=len(failures)),
                  font=("TkDefaultFont", 10, "bold"),
                  foreground=theme.CURRENT.get("warn", "#c0392b")).pack(anchor=tk.W)
        ttk.Label(frame, wraplength=520, justify=tk.LEFT,
                  text=t("Das Zertifikat unterscheidet sich von dem beim ersten Kontakt "
                         "gespeicherten. Das ist harmlos, wenn die Kamera außerhalb des "
                         "Programms zurückgesetzt, aktualisiert oder mit einem neuen "
                         "Zertifikat versehen wurde — es kann aber auch auf einen Angriff "
                         "(Man-in-the-Middle) hindeuten. Es wurden keine Zugangsdaten "
                         "gesendet.")).pack(anchor=tk.W, pady=(4, 8))

        tree = ttk.Treeview(frame, columns=("cam", "old", "new"), show="headings",
                            height=min(8, max(2, len(failures))))
        tree.heading("cam", text=t("Kamera"))
        tree.heading("old", text=t("Bisher (SHA-256)"))
        tree.heading("new", text=t("Jetzt (SHA-256)"))
        tree.column("cam", width=200)
        tree.column("old", width=170)
        tree.column("new", width=170)
        for cam, exc in failures:
            label = f"{cam.get('Name', '?')} ({get_first_ip(cam) or '—'})"
            tree.insert("", tk.END, values=(label, short_fp(exc.expected),
                                            short_fp(exc.actual)))
        tree.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(anchor=tk.E, pady=(10, 0))
        ttk.Button(btns, text=t("Neuem Zertifikat vertrauen und wiederholen"),
                   command=self._accept).pack(side=tk.RIGHT)
        ttk.Button(btns, text=t("Abbrechen"), command=self._cancel).pack(
            side=tk.RIGHT, padx=6)
        self.bind("<Escape>", lambda _e: self._cancel())

    def _accept(self):
        self.result = True
        self.destroy()

    def _cancel(self):
        self.result = False
        self.destroy()
