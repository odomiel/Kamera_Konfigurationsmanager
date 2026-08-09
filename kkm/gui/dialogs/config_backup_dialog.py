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

"""Config-backup action: import/export a vendor's opaque full-device backup.

Unlike :class:`ConfigDialog` (which handles a *selectable* Axis ADM parameter
template), a config backup is a device-/model-specific whole-device image that is only
ever applied as a whole — an encrypted ``.bin`` blob (Hikvision/Hanwha/Dahua) or the
Axis DCA ``.json`` resource map. The file type, an optional "keep network" checkbox,
and optional import variants (Axis merge/default) all come from the plugin. Two
operations on the selected cameras:

- **Einspielen**: pick a backup file and restore it. The device reboots afterwards.
  Because a backup carries device-specific settings (IP, name, users), applying one
  file to several cameras clones that identity — the dialog warns about it.
- **Herunterladen**: read the backup of the *first* selected camera and save it.

All vendor work goes through the camera's :class:`~kkm.core.VendorPlugin`
(``import_config_backup`` / ``export_config_backup``); the dialog only appears for
plugins that declare ``Capability.CONFIG_BACKUP``.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox
from kkm.gui import filedialogs as filedialog

from kkm.core import Capability, get_first_ip, t
from .base import ActionDialog


class ConfigBackupDialog(ActionDialog):
    title_text = "Konfigurations-Backup"
    capability = Capability.CONFIG_BACKUP

    def build_body(self, parent):
        self._mode = tk.StringVar(value="import")
        self._path = tk.StringVar()
        self._keep_net = tk.BooleanVar(value=True)
        # „Netz behalten" bietet nur an, wessen Plugin es unterstützt (Hanwha).
        plugin0 = self.plugin0()
        self._supports_keep_net = bool(getattr(plugin0, "config_backup_keep_network", False))
        # Warnhinweis nur, wenn das Einspielen (noch) nicht an Hardware verifiziert ist.
        self._import_verified = bool(getattr(plugin0, "config_backup_import_verified", False))
        # Dateiendung/-filter und optionale Einspiel-Varianten sind herstellerspezifisch.
        self._ext = getattr(plugin0, "config_backup_extension", ".bin") or ".bin"
        label = getattr(plugin0, "config_backup_filetype_label", "Backup")
        self._filetypes = [(f"{t(label)} (*{self._ext})", f"*{self._ext}"),
                           (t("Alle Dateien"), "*.*")]
        self._import_modes = tuple(getattr(plugin0, "config_backup_import_modes", ()))
        self._import_mode = tk.StringVar(
            value=self._import_modes[0][0] if self._import_modes else "")

        modes = ttk.Frame(parent)
        modes.pack(fill=tk.X)
        ttk.Radiobutton(modes, text=t("Backup einspielen (Datei → Kamera)"),
                        value="import", variable=self._mode,
                        command=self._update_visibility).pack(anchor=tk.W)
        ttk.Radiobutton(modes, text=t("Backup herunterladen (Kamera → Datei)"),
                        value="export", variable=self._mode,
                        command=self._update_visibility).pack(anchor=tk.W)

        filerow = ttk.Frame(parent)
        filerow.pack(fill=tk.X, pady=(6, 0))
        self._file_label = ttk.Label(filerow, text=t("Backup-Datei:"))
        self._file_label.grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(filerow, textvariable=self._path, width=42).grid(
            row=0, column=1, sticky="ew", padx=4)
        self._browse_btn = ttk.Button(filerow, text=t("Durchsuchen…"),
                                      command=self._browse)
        self._browse_btn.grid(row=0, column=2)
        filerow.columnconfigure(1, weight=1)

        self._keep_net_cb = ttk.Checkbutton(
            parent, text=t("Netzwerkeinstellungen (IP) der Zielkamera beibehalten"),
            variable=self._keep_net)

        # Einspiel-Variante (nur wenn das Plugin welche anbietet, z. B. Axis merge/default).
        self._mode_frame = ttk.LabelFrame(parent, text=t("Einspiel-Variante"))
        for value, mlabel in self._import_modes:
            ttk.Radiobutton(self._mode_frame, text=t(mlabel), value=value,
                            variable=self._import_mode).pack(anchor=tk.W)

        self._hint = ttk.Label(parent, wraplength=440, justify=tk.LEFT)
        self._hint.pack(anchor=tk.W, pady=(8, 0))

        from kkm.gui import theme
        self._warn = ttk.Label(parent, wraplength=440, justify=tk.LEFT,
                               foreground=theme.CURRENT.get("warn", "#c0392b"))

        self._apply_btn = ttk.Button(parent, text=t("Anwenden"), command=self._apply)
        self._apply_btn.pack(anchor=tk.W, pady=(8, 0))
        self._update_visibility()

    # ---------------------------------------------------------------- helpers
    def _update_visibility(self):
        if self._mode.get() == "import":
            if self._supports_keep_net:
                self._keep_net_cb.pack(anchor=tk.W, pady=(6, 0), before=self._hint)
            if self._import_modes:
                self._mode_frame.pack(fill=tk.X, pady=(6, 0), before=self._hint)
            self._file_label.config(text=t("Backup-Datei:"))
            self._hint.config(
                text=t("Ein Backup enthält gerätespezifische Einstellungen (IP, Name, "
                       "Benutzer). Es ist an Modell/Firmware gebunden und wird als "
                       "Ganzes übernommen; die Kamera startet danach neu. Auf mehrere "
                       "Kameras gespielt, führt es zu Adress-/Identitätskonflikten."))
            if not self._import_verified:
                self._warn.config(
                    text=t("Hinweis: Das Einspielen ist noch nicht an echter Hardware "
                           "verifiziert — die Kamera kann es mit einem Geräte-Fehler "
                           "ablehnen. Das Herunterladen von Backups ist getestet."))
                self._warn.pack(anchor=tk.W, pady=(6, 0), before=self._apply_btn)
        else:
            self._keep_net_cb.pack_forget()
            self._mode_frame.pack_forget()
            self._warn.pack_forget()
            self._file_label.config(text=t("Zieldatei:"))
            self._hint.config(
                text=t("Lädt das Backup der ersten ausgewählten Kamera herunter."))

    def _browse(self):
        if self._mode.get() == "import":
            path = filedialog.askopenfilename(parent=self, title=t("Backup-Datei wählen"),
                                              filetypes=self._filetypes)
        else:
            cam = self.cameras[0]
            suggested = self._suggest_name(cam)
            path = filedialog.asksaveasfilename(parent=self, title=t("Backup speichern unter"),
                                                filetypes=self._filetypes,
                                                defaultextension=self._ext,
                                                initialfile=suggested)
        if path:
            self._path.set(path)

    def _suggest_name(self, cam) -> str:
        base = (cam.get("Modell") or cam.get("Name") or "backup").strip() or "backup"
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
        ip = get_first_ip(cam) or ""
        return f"{safe}_{ip}{self._ext}" if ip else f"{safe}{self._ext}"

    # ------------------------------------------------------------------ apply
    def _apply(self):
        path = self._path.get().strip()
        if not path:
            messagebox.showinfo(t(self.title_text),
                                t("Bitte zuerst eine Datei wählen."), parent=self)
            return

        if self._mode.get() == "import":
            if not os.path.isfile(path):
                messagebox.showerror(t(self.title_text),
                                     t("Datei nicht gefunden: {path}", path=path), parent=self)
                return
            n = len(self.cameras)
            warn = t("{n} Kamera(s) das Backup einspielen?\n\nDie Kameras übernehmen die "
                     "Einstellungen komplett und starten danach neu. Diese Aktion kann "
                     "nicht rückgängig gemacht werden.", n=n)
            if n > 1:
                warn += "\n\n" + t("Achtung: Dasselbe Backup auf mehrere Kameras zu "
                                   "spielen erzeugt IP-/Identitätskonflikte.")
            if not messagebox.askyesno(t(self.title_text), warn, parent=self):
                return
            keep_net = self._keep_net.get()
            import_mode = self._import_mode.get() or None
            self.run_per_camera(
                lambda plugin, camera, creds: plugin.import_config_backup(
                    camera, creds, path, keep_network=keep_net, import_mode=import_mode),
                done_msg=t("Backup-Einspielung abgeschlossen."))
        else:
            first = self.cameras[0]

            def op(plugin, camera, creds):
                if camera is not first:
                    return t("übersprungen (Export nur von der ersten Kamera)")
                return plugin.export_config_backup(camera, creds, path)

            self.run_per_camera(op, done_msg=t("Backup-Download abgeschlossen."))
