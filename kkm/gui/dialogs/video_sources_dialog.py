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

"""Video-sources action: import/export a device's list of video sources.

Unlike :class:`ConfigBackupDialog` (an opaque *whole-device* image that reboots the
device and clones its identity), the video sources are just the list of cameras a
device pulls and shows — e.g. the Senstar Thin Client's ``Camera/Export`` /
``import.html`` roundtrip. Importing is additive (merge by source id); nothing reboots.
File type and label come from the plugin (``video_sources_extension`` /
``video_sources_filetype_label``); the dialog only appears for plugins that declare
``Capability.VIDEO_SOURCES`` and implement ``export_video_sources`` /
``import_video_sources``.
"""

from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
from kkm.gui import filedialogs as filedialog

from kkm.core import Capability, get_first_ip, t
from .base import ActionDialog


class VideoSourcesDialog(ActionDialog):
    title_text = "Videoquellen"
    capability = Capability.VIDEO_SOURCES

    def build_body(self, parent):
        self._mode = tk.StringVar(value="export")
        self._path = tk.StringVar()
        plugin0 = self.plugin0()
        self._ext = getattr(plugin0, "video_sources_extension", ".json") or ".json"
        label = getattr(plugin0, "video_sources_filetype_label", "Videoquellen")
        self._filetypes = [(f"{t(label)} (*{self._ext})", f"*{self._ext}"),
                           (t("Alle Dateien"), "*.*")]

        modes = ttk.Frame(parent)
        modes.pack(fill=tk.X)
        ttk.Radiobutton(modes, text=t("Exportieren (Kamera → Datei)"),
                        value="export", variable=self._mode,
                        command=self._update_visibility).pack(anchor=tk.W)
        ttk.Radiobutton(modes, text=t("Importieren (Datei → Kamera)"),
                        value="import", variable=self._mode,
                        command=self._update_visibility).pack(anchor=tk.W)

        filerow = ttk.Frame(parent)
        filerow.pack(fill=tk.X, pady=(6, 0))
        self._file_label = ttk.Label(filerow, text=t("Zieldatei:"))
        self._file_label.grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(filerow, textvariable=self._path, width=42).grid(
            row=0, column=1, sticky="ew", padx=4)
        ttk.Button(filerow, text=t("Durchsuchen…"), command=self._browse).grid(
            row=0, column=2)
        filerow.columnconfigure(1, weight=1)

        self._hint = ttk.Label(parent, wraplength=440, justify=tk.LEFT)
        self._hint.pack(anchor=tk.W, pady=(8, 0))

        self._apply_btn = ttk.Button(parent, text=t("Anwenden"), command=self._apply)
        self._apply_btn.pack(anchor=tk.W, pady=(8, 0))
        self._update_visibility()

    # ---------------------------------------------------------------- helpers
    def _update_visibility(self):
        if self._mode.get() == "export":
            self._file_label.config(text=t("Zieldatei:"))
            self._hint.config(
                text=t("Lädt die Videoquellen-Liste der ersten ausgewählten Kamera "
                       "herunter. Achtung: Die Datei enthält die Zugangsdaten der "
                       "Quellen im Klartext — entsprechend sicher aufbewahren."))
        else:
            self._file_label.config(text=t("Quelldatei:"))
            self._hint.config(
                text=t("Spielt die Videoquellen aus der Datei ein. Der Import ergänzt "
                       "die vorhandene Liste (Abgleich über die Quellen-Kennung); das "
                       "Gerät startet dabei nicht neu."))

    def _browse(self):
        if self._mode.get() == "import":
            path = filedialog.askopenfilename(
                parent=self, title=t("Videoquellen-Datei wählen"),
                filetypes=self._filetypes)
        else:
            path = filedialog.asksaveasfilename(
                parent=self, title=t("Videoquellen speichern unter"),
                filetypes=self._filetypes, defaultextension=self._ext,
                initialfile=self._suggest_name())
        if path:
            self._path.set(path)

    def _suggest_name(self) -> str:
        # Namensschema der Geräte-Oberfläche: cameras-JJJJMMTT-HHMMSS.json
        return "cameras-" + time.strftime("%Y%m%d-%H%M%S") + self._ext

    # ------------------------------------------------------------------ apply
    def _apply(self):
        path = self._path.get().strip()
        if not path:
            messagebox.showinfo(t(self.title_text),
                                t("Bitte zuerst eine Datei wählen."), parent=self)
            return

        if self._mode.get() == "import":
            if not os.path.isfile(path):
                messagebox.showerror(
                    t(self.title_text),
                    t("Datei nicht gefunden: {path}", path=path), parent=self)
                return
            n = len(self.cameras)
            if not messagebox.askyesno(
                    t(self.title_text),
                    t("{n} Kamera(s) die Videoquellen aus der Datei einspielen?", n=n),
                    parent=self):
                return
            self.run_per_camera(
                lambda plugin, camera, creds: plugin.import_video_sources(
                    camera, creds, path),
                done_msg=t("Videoquellen-Import abgeschlossen."))
        else:
            first = self.cameras[0]

            def op(plugin, camera, creds):
                if camera is not first:
                    return t("übersprungen (Export nur von der ersten Kamera)")
                return plugin.export_video_sources(camera, creds, path)

            self.run_per_camera(op, done_msg=t("Videoquellen-Export abgeschlossen."))
