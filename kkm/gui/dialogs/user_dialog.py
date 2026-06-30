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

"""User action: manage regular Axis users on the selected cameras.

Three modes (radio), mirroring the Discovery tool's "Benutzer" tab but as a
front-view action:

- **Anlegen**: create a user with a role; optional *factory* flow for
  out-of-the-box devices (tries unauthenticated, then default credentials).
- **Passwort ändern**: set the password of an existing user.
- **Stapel-Import**: read a ``Name,Passwort[,Rolle]`` list and apply every user to
  every selected camera (parsed once up front; invalid rows abort with line
  numbers before any camera is touched).

Optionally the entered/created password is written to the encrypted vault per
camera (only when the vault is unlocked), so later actions can auto-fill it.
All vendor work goes through :class:`AxisPlugin` (``add_user`` / wrapping
``add_or_set_user``, ``set_user_password``, ``parse_user_list``).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from kkm.core import Capability
from kkm.plugins.axis.plugin import AxisPlugin
from .base import ActionDialog


class UserDialog(ActionDialog):
    title_text = "Benutzer verwalten"
    capability = Capability.USERS

    def build_body(self, parent):
        self._mode = tk.StringVar(value="add")

        modes = ttk.Frame(parent)
        modes.pack(fill=tk.X)
        for val, text in (("add", "Benutzer anlegen"),
                          ("setpw", "Passwort ändern"),
                          ("import", "Stapel-Import aus Datei")):
            ttk.Radiobutton(modes, text=text, value=val, variable=self._mode,
                            command=self._update_visibility).pack(side=tk.LEFT, padx=(0, 12))

        # --- shared fields ---
        self.user_name = tk.StringVar()
        self.user_pw = tk.StringVar()
        self.role = tk.StringVar(value="viewer")
        self.factory = tk.BooleanVar(value=False)
        self.import_path = tk.StringVar()
        self.store_vault = tk.BooleanVar(value=False)

        # Container for the mode-specific area, kept above the vault/apply row so
        # toggling modes never disturbs the overall layout order.
        self._dynamic = ttk.Frame(parent)
        self._dynamic.pack(fill=tk.X, pady=6)

        # --- "add" / "setpw" frame (single user) ---
        self._single = ttk.Frame(self._dynamic)
        ttk.Label(self._single, text="Benutzername:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self._single, textvariable=self.user_name, width=22).grid(
            row=0, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(self._single, text="Passwort:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self._single, textvariable=self.user_pw, width=22, show="*").grid(
            row=1, column=1, sticky=tk.W, padx=4, pady=2)
        self._role_label = ttk.Label(self._single, text="Rolle:")
        self._role_label.grid(row=2, column=0, sticky=tk.W, pady=2)
        self._role_box = ttk.Combobox(self._single, textvariable=self.role, width=19,
                                      state="readonly", values=AxisPlugin.USER_ROLES)
        self._role_box.grid(row=2, column=1, sticky=tk.W, padx=4, pady=2)
        self._factory_cb = ttk.Checkbutton(
            self._single, text="Auslieferungszustand (factory)", variable=self.factory)
        self._factory_cb.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)

        # --- "import" frame ---
        self._importf = ttk.Frame(self._dynamic)
        row = ttk.Frame(self._importf)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self.import_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Datei…", command=self._choose_list).pack(side=tk.LEFT, padx=4)
        self._import_info = ttk.Label(
            self._importf, text="Format: Name,Passwort[,Rolle] — eine Zeile je Benutzer.")
        self._import_info.pack(anchor=tk.W, pady=(4, 0))
        ttk.Checkbutton(self._importf, text="Auslieferungszustand (factory)",
                        variable=self.factory).pack(anchor=tk.W, pady=2)

        # --- vault + apply ---
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
            # role only relevant when creating a user
            self._role_box.config(state=("readonly" if mode == "add" else "disabled"))
            self._factory_cb.config(state=("normal" if mode == "add" else "disabled"))

    # ------------------------------------------------------------------ import
    def _choose_list(self):
        path = filedialog.askopenfilename(
            parent=self, title="Benutzerliste wählen",
            filetypes=[("Textliste/CSV", "*.txt *.csv"), ("Alle Dateien", "*.*")])
        if not path:
            return
        self.import_path.set(path)
        try:
            users = AxisPlugin.parse_user_list(path, onvif=False)
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
        elif mode == "setpw":
            self._apply_setpw()
        else:
            self._apply_add()

    def _apply_add(self):
        name = self.user_name.get().strip()
        pw = self.user_pw.get()
        if not name or not pw:
            messagebox.showinfo(self.title_text, "Bitte Benutzername und Passwort angeben.")
            return
        role = self.role.get()
        factory = self.factory.get()

        def op(plugin, camera, creds):
            msg = plugin.add_user(camera, creds, name, pw, role=role, factory=factory)
            self._maybe_store(camera, name, pw)
            return msg or f"Benutzer '{name}' angelegt"

        self.run_per_camera(op, done_msg="Anlegen abgeschlossen.")

    def _apply_setpw(self):
        name = self.user_name.get().strip()
        pw = self.user_pw.get()
        if not name or not pw:
            messagebox.showinfo(self.title_text, "Bitte Benutzername und neues Passwort angeben.")
            return

        def op(plugin, camera, creds):
            msg = plugin.set_user_password(camera, creds, name, pw)
            self._maybe_store(camera, name, pw)
            return msg or f"Passwort von '{name}' geändert"

        self.run_per_camera(op, done_msg="Passwortänderung abgeschlossen.")

    def _apply_import(self):
        path = self.import_path.get().strip()
        if not path:
            messagebox.showinfo(self.title_text, "Bitte zuerst eine Benutzerliste wählen.")
            return
        try:
            users = AxisPlugin.parse_user_list(path, onvif=False)  # validate once
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.title_text, str(exc))
            return
        factory = self.factory.get()

        def op(plugin, camera, creds):
            ok, fail = 0, 0
            for u in users:
                try:
                    plugin.add_user(camera, creds, u["name"], u["password"],
                                    role=u["role"], factory=factory)
                    self._maybe_store(camera, u["name"], u["password"])
                    ok += 1
                except Exception:  # noqa: BLE001 - counted, details omitted per camera
                    fail += 1
            if fail:
                raise RuntimeError(f"{ok} angelegt, {fail} fehlgeschlagen")
            return f"{ok} Benutzer angelegt"

        self.run_per_camera(op, done_msg="Stapel-Import abgeschlossen.")
