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

"""ONVIF user action: manage ONVIF users on the selected cameras.

Same shape as the regular user dialog, but for ONVIF users (levels
Administrator/Operator/User) and without a factory flow — ONVIF users are managed
over the VAPIX SOAP endpoint ``/vapix/services`` with an authenticated admin, so a
working admin login is always required.

Three modes: anlegen / Passwort ändern / Stapel-Import
(``Name,Passwort[,Stufe]``). All vendor work goes through the camera's
:class:`~kkm.core.VendorPlugin` (``add_onvif_user``, ``set_onvif_user_password``,
``parse_user_list(onvif=True)``); the levels come from its ``ONVIF_LEVELS``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from kkm.gui import filedialogs as filedialog   # feste Dialoggröße

from kkm.core import Capability
from .base import ActionDialog


class OnvifDialog(ActionDialog):
    title_text = "ONVIF-Benutzer verwalten"
    capability = Capability.ONVIF_USERS

    def build_body(self, parent):
        self._mode = tk.StringVar(value="add")

        modes = ttk.Frame(parent)
        modes.pack(fill=tk.X)
        for val, text in (("add", "Benutzer anlegen"),
                          ("setpw", "Passwort ändern"),
                          ("import", "Stapel-Import aus Datei")):
            ttk.Radiobutton(modes, text=text, value=val, variable=self._mode,
                            command=self._update_visibility).pack(side=tk.LEFT, padx=(0, 12))

        self.user_name = tk.StringVar()
        self.user_pw = tk.StringVar()
        self.level = tk.StringVar(value="User")
        self.import_path = tk.StringVar()
        self.store_vault = tk.BooleanVar(value=False)

        self._dynamic = ttk.Frame(parent)
        self._dynamic.pack(fill=tk.X, pady=6)

        # --- single user (add / setpw) ---
        self._single = ttk.Frame(self._dynamic)
        ttk.Label(self._single, text="Benutzername:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self._single, textvariable=self.user_name, width=22).grid(
            row=0, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(self._single, text="Passwort:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self._single, textvariable=self.user_pw, width=22, show="*").grid(
            row=1, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(self._single, text="Stufe:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self._level_box = ttk.Combobox(self._single, textvariable=self.level, width=19,
                                       state="readonly", values=self.plugin0().ONVIF_LEVELS)
        self._level_box.grid(row=2, column=1, sticky=tk.W, padx=4, pady=2)

        # --- import ---
        self._importf = ttk.Frame(self._dynamic)
        row = ttk.Frame(self._importf)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self.import_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Datei…", command=self._choose_list).pack(side=tk.LEFT, padx=4)
        self._import_info = ttk.Label(
            self._importf, text="Format: Name,Passwort[,Stufe] — eine Zeile je Benutzer.")
        self._import_info.pack(anchor=tk.W, pady=(4, 0))

        ttk.Checkbutton(
            parent, text="Passwort im Tresor speichern (nur wenn entsperrt)",
            variable=self.store_vault).pack(anchor=tk.W, pady=(8, 2))
        ttk.Button(parent, text="Ausführen", command=self._apply).pack(anchor=tk.W)

        self._update_visibility()

    def _update_visibility(self):
        mode = self._mode.get()
        self._single.pack_forget()
        self._importf.pack_forget()
        if mode == "import":
            self._importf.pack(fill=tk.X)
        else:
            self._single.pack(fill=tk.X)

    # ------------------------------------------------------------------ import
    def _choose_list(self):
        path = filedialog.askopenfilename(
            parent=self, title="ONVIF-Benutzerliste wählen",
            filetypes=[("Textliste/CSV", "*.txt *.csv"), ("Alle Dateien", "*.*")])
        if not path:
            return
        self.import_path.set(path)
        try:
            users = self.plugin0().parse_user_list(path, onvif=True)
            self._import_info.config(text=f"{len(users)} Benutzer in der Datei: "
                                          + ", ".join(u["name"] for u in users[:6])
                                          + (" …" if len(users) > 6 else ""))
        except Exception as exc:  # noqa: BLE001
            self._import_info.config(text=f"Ungültig: {exc}")
            self.import_path.set("")

    # ------------------------------------------------------------------- apply
    def _apply(self):
        mode = self._mode.get()
        if mode == "import":
            self._apply_import()
            return
        name = self.user_name.get().strip()
        pw = self.user_pw.get()
        if not name or not pw:
            messagebox.showinfo(self.title_text, "Bitte Benutzername und Passwort angeben.", parent=self)
            return
        level = self.level.get()

        if mode == "setpw":
            def op(plugin, camera, creds):
                msg = plugin.set_onvif_user_password(camera, creds, name, pw, level=level)
                self._maybe_store(camera, name, pw)
                return msg or f"ONVIF-Passwort von '{name}' geändert"
            self.run_per_camera(op, done_msg="Passwortänderung abgeschlossen.")
        else:
            def op(plugin, camera, creds):
                msg = plugin.add_onvif_user(camera, creds, name, pw, level=level)
                self._maybe_store(camera, name, pw)
                return msg or f"ONVIF-Benutzer '{name}' angelegt"
            self.run_per_camera(op, done_msg="Anlegen abgeschlossen.")

    def _apply_import(self):
        path = self.import_path.get().strip()
        if not path:
            messagebox.showinfo(self.title_text, "Bitte zuerst eine Benutzerliste wählen.", parent=self)
            return
        try:
            users = self.plugin0().parse_user_list(path, onvif=True)  # validate once
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.title_text, str(exc), parent=self)
            return

        def op(plugin, camera, creds):
            ok, fail = 0, 0
            for u in users:
                try:
                    plugin.add_onvif_user(camera, creds, u["name"], u["password"],
                                          level=u["role"])
                    self._maybe_store(camera, u["name"], u["password"])
                    ok += 1
                except Exception:  # noqa: BLE001
                    fail += 1
            if fail:
                raise RuntimeError(f"{ok} angelegt, {fail} fehlgeschlagen")
            return f"{ok} ONVIF-Benutzer angelegt"

        self.run_per_camera(op, done_msg="Stapel-Import abgeschlossen.")
