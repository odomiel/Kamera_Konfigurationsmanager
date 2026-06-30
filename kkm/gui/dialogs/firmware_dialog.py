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

"""Firmware action: update several cameras of *different* models at once.

The project requirement is explicitly to upgrade multiple cameras of different
types simultaneously — so a single firmware file (as in the Discovery tool) is not
enough: firmware must match the model. This dialog therefore groups the selected
cameras by model and lets the user assign one ``.bin`` per distinct model. The
update then runs over all cameras in parallel (background thread + per-camera log);
cameras whose model has no file assigned are skipped and reported.

Firmware uploads are slow and the device reboots afterwards, so a long per-camera
timeout is forced regardless of the credentials timeout. The vendor work goes
through :meth:`AxisPlugin.upgrade_firmware` (modern vs. legacy endpoint handled in
VAPIX).
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from kkm.core import Capability
from .base import ActionDialog

FIRMWARE_TIMEOUT = 600   # seconds; upload + flash takes far longer than a probe


def _model_of(camera: dict) -> str:
    return camera.get("_model") or camera.get("Name") or "?"


class FirmwareDialog(ActionDialog):
    title_text = "Firmware aktualisieren"
    capability = Capability.FIRMWARE

    def build_body(self, parent):
        # model -> assigned firmware path
        self._fw_by_model: dict[str, str] = {}
        # model -> list of cameras
        self._by_model: dict[str, list[dict]] = {}
        for cam in self.cameras:
            self._by_model.setdefault(_model_of(cam), []).append(cam)

        ttk.Label(
            parent,
            text="Pro Modell eine passende Firmware-Datei zuweisen. "
                 "Es werden alle ausgewählten Kameras gleichzeitig aktualisiert.",
            wraplength=560, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 6))

        cols = ("count", "file")
        self.tree = ttk.Treeview(parent, columns=cols, show="tree headings", height=8,
                                 selectmode="browse")
        self.tree.heading("#0", text="Modell")
        self.tree.heading("count", text="Kameras")
        self.tree.heading("file", text="Firmware-Datei")
        self.tree.column("#0", width=180)
        self.tree.column("count", width=70, anchor=tk.CENTER)
        self.tree.column("file", width=320)
        self.tree.pack(fill=tk.X)
        for model, cams in sorted(self._by_model.items()):
            self.tree.insert("", "end", iid=model, text=model,
                             values=(len(cams), "—"))

        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=6)
        ttk.Button(row, text="Firmware-Datei für Modell wählen…",
                   command=self._choose_for_model).pack(side=tk.LEFT)
        ttk.Button(row, text="Zuweisung entfernen",
                   command=self._clear_for_model).pack(side=tk.LEFT, padx=6)

        self._factory = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            parent, text="Werkseinstellungen beim Update (factory default)",
            variable=self._factory).pack(anchor=tk.W)

        from kkm.gui import theme
        ttk.Label(
            parent,
            text="Achtung: Die Firmware MUSS zum jeweiligen Modell passen. "
                 "Die Kameras starten nach dem Update neu.",
            foreground=theme.CURRENT["warn"], wraplength=560, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 6))

        ttk.Button(parent, text="Firmware aufspielen",
                   command=self._do_upgrade).pack(anchor=tk.W)

    # --------------------------------------------------------------- assignment
    def _selected_model(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _choose_for_model(self):
        model = self._selected_model()
        if not model:
            messagebox.showinfo(self.title_text, "Bitte zuerst ein Modell auswählen.")
            return
        path = filedialog.askopenfilename(
            parent=self, title=f"Firmware für {model}",
            filetypes=[("Firmware", "*.bin"), ("Alle Dateien", "*.*")])
        if not path:
            return
        self._fw_by_model[model] = path
        self.tree.set(model, "file", os.path.basename(path))

    def _clear_for_model(self):
        model = self._selected_model()
        if model and model in self._fw_by_model:
            del self._fw_by_model[model]
            self.tree.set(model, "file", "—")

    # ------------------------------------------------------------------ upgrade
    def _do_upgrade(self):
        if not self._fw_by_model:
            messagebox.showinfo(self.title_text,
                                "Bitte mindestens einem Modell eine Firmware zuweisen.")
            return
        assigned = sum(len(self._by_model[m]) for m in self._fw_by_model)
        skipped = len(self.cameras) - assigned
        lines = [f"• {m}: {os.path.basename(p)} ({len(self._by_model[m])} Kamera(s))"
                 for m, p in sorted(self._fw_by_model.items())]
        msg = ("Firmware-Update für:\n" + "\n".join(lines))
        if skipped:
            msg += f"\n\n{skipped} Kamera(s) ohne Zuweisung werden übersprungen."
        if self._factory.get():
            msg += "\n\nMit Werkseinstellungen (factory default)."
        msg += "\n\nDer Vorgang dauert einige Minuten. Fortfahren?"
        if not messagebox.askyesno(self.title_text, msg, parent=self):
            return

        fw_by_model = dict(self._fw_by_model)
        factory = self._factory.get()

        def op(plugin, camera, creds):
            model = _model_of(camera)
            path = fw_by_model.get(model)
            if not path:
                raise RuntimeError("übersprungen (keine Firmware für dieses Modell)")
            creds.timeout = max(creds.timeout, FIRMWARE_TIMEOUT)
            plugin.upgrade_firmware(camera, creds, path, factory_default=factory)
            return f"Firmware {os.path.basename(path)} aufgespielt"

        self.run_per_camera(op, done_msg="Firmware-Update abgeschlossen.")
