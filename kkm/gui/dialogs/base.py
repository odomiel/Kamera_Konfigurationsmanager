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

"""Shared base for the front-view action dialogs.

Every action (IP, Users, ONVIF, Firmware, Configuration) operates on the cameras
currently selected in the main table and needs the same scaffolding:

- a "Zugangsdaten" block that produces a :class:`Credentials`,
- background execution (camera writes must not freeze the UI) with a per-camera
  result log, via a ``queue.Queue`` polled with ``after()`` — the same pattern as
  the Discovery tool's ``CameraSettingsDialog``,
- optional pre-fill of each camera's stored password from the vault.

Subclasses build their action-specific widgets in :meth:`build_body` and start
work with :meth:`run_per_camera`.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from kkm.core import Credentials, camera_key
from kkm.plugins.axis.discovery import get_first_ip
from .vault_access import ensure_vault_unlocked


class ActionDialog(tk.Toplevel):
    title_text = "Aktion"

    def __init__(self, parent, cameras: list[dict], registry, vault=None):
        super().__init__(parent)
        self.title(self.title_text)
        self.transient(parent)
        self.cameras = cameras
        self.registry = registry
        self.vault = vault
        self._q: queue.Queue = queue.Queue()
        self._busy = False

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text=f"{len(cameras)} Kamera(s) ausgewählt",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)

        self._build_credentials(outer)

        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True, pady=6)
        self.build_body(body)

        # --- result log ---
        logframe = ttk.LabelFrame(outer, text="Ergebnis", padding=6)
        logframe.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.log = tk.Text(logframe, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)

        self.progress = ttk.Progressbar(outer, mode="indeterminate", length=200)
        self.progress.pack(fill=tk.X, pady=(6, 0))

        self.after(120, self._poll)

    # ------------------------------------------------------------ credentials
    def _build_credentials(self, parent):
        cred = ttk.LabelFrame(parent, text="Zugangsdaten", padding=8)
        cred.pack(fill=tk.X, pady=(8, 4))
        self.user_var = tk.StringVar(value="root")
        self.pass_var = tk.StringVar()
        self.scheme_var = tk.StringVar(value="auto")
        self.port_var = tk.StringVar()
        self.timeout_var = tk.IntVar(value=10)

        ttk.Label(cred, text="Benutzer:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self._user_entry = ttk.Entry(cred, textvariable=self.user_var, width=18)
        self._user_entry.grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(cred, text="Passwort:").grid(row=0, column=2, sticky=tk.W, padx=4, pady=2)
        self._pass_entry = ttk.Entry(cred, textvariable=self.pass_var, width=18, show="*")
        self._pass_entry.grid(row=0, column=3, padx=4, pady=2)
        ttk.Label(cred, text="Verbindung:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Combobox(cred, textvariable=self.scheme_var, width=15, state="readonly",
                     values=("auto", "https", "http")).grid(row=1, column=1, padx=4, pady=2)
        ttk.Label(cred, text="Port (optional):").grid(row=1, column=2, sticky=tk.W, padx=4, pady=2)
        ttk.Entry(cred, textvariable=self.port_var, width=18).grid(row=1, column=3, padx=4, pady=2)
        ttk.Label(cred, text="Timeout (s):").grid(row=2, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Spinbox(cred, from_=2, to=120, width=6, textvariable=self.timeout_var).grid(
            row=2, column=1, sticky=tk.W, padx=4, pady=2)

        # Zugangsdaten aus dem Tresor verwenden (pro Kamera Benutzer+Passwort).
        # Standardmaessig an, sobald ein Tresor existiert; die Felder oben dienen
        # dann nur als Rueckfall fuer Kameras ohne Tresor-Eintrag.
        self.use_vault_var = tk.BooleanVar(value=self.vault is not None)
        self._vault_chk = ttk.Checkbutton(
            cred, variable=self.use_vault_var, command=self._on_use_vault_toggle,
            text="Zugangsdaten aus Tresor verwenden — Felder oben nur als Rückfall")
        self._vault_chk.grid(row=3, column=0, columnspan=4, sticky=tk.W, padx=4, pady=(6, 2))
        if self.vault is None:
            self._vault_chk.state(["disabled"])
        self._on_use_vault_toggle()   # Anfangszustand der Felder setzen

    def _on_use_vault_toggle(self):
        """Bei aktiver Tresor-Nutzung Benutzer/Passwort ausgrauen (optional)."""
        state = "disabled" if self.use_vault_var.get() else "normal"
        self._user_entry.config(state=state)
        self._pass_entry.config(state=state)

    def credentials(self) -> Credentials:
        port = self.port_var.get().strip()
        return Credentials(
            username=self.user_var.get().strip() or "root",
            password=self.pass_var.get(),
            scheme=self.scheme_var.get(),
            port=int(port) if port.isdigit() else None,
            timeout=int(self.timeout_var.get()),
        )

    def creds_for(self, camera: dict) -> Credentials:
        """Zugangsdaten je Kamera. Ist „Aus Tresor verwenden" aktiv und der Tresor
        entsperrt, gewinnt **immer** der Tresor-Eintrag (Benutzer + Passwort); die
        Dialogfelder dienen nur als Rückfall für Kameras ohne Eintrag."""
        creds = self.credentials()
        if self.use_vault_var.get() and self.vault and not self.vault.is_locked:
            stored = self.vault.get_password(camera_key(camera))
            if stored:
                creds.username = stored.get("username", creds.username)
                creds.password = stored.get("password", creds.password)
        return creds

    def plugin_for(self, camera: dict):
        return self.registry.get(camera.get("_vendor", "axis"))

    # ----------------------------------------------------------------- to override
    def build_body(self, parent):  # pragma: no cover - overridden
        raise NotImplementedError

    def _on_done(self):
        """Hook: läuft im Main-Thread, sobald ein ``run_per_camera``-Durchlauf
        fertig ist. Unterklassen können hier die Kameraliste aktualisieren."""

    # --------------------------------------------------------------- vault store
    def _wants_vault(self) -> bool:
        var = getattr(self, "store_vault", None)
        return bool(var and var.get())

    def _maybe_store(self, camera, username, password):
        """Speichert Zugangsdaten, wenn der Nutzer es will: in den Tresor (falls
        entsperrt) und zusätzlich in den Sitzungs-Cache des Hauptfensters."""
        if not self._wants_vault():
            return
        key = camera_key(camera)
        if self.vault and not self.vault.is_locked:
            self.vault.set_password(key, username, password)
        cache = getattr(self.master, "_cam_creds", None)
        if cache is not None:                     # Fallback: nur laufende Sitzung
            cache[key] = (username, password)

    # ------------------------------------------------------------- background run
    def run_per_camera(self, op, done_msg="Fertig."):
        """Run ``op(plugin, camera, creds)`` for each camera in a worker thread.

        ``op`` returns a short status string on success or raises on failure; each
        outcome is logged per camera. Disables re-entry while busy.
        """
        if self._busy:
            return
        # Tresor wird gebraucht (zum Lesen der Passwörter und/oder zum Speichern),
        # ist aber gesperrt/nicht angelegt -> auf dem Main-Thread anbieten, ihn
        # einzurichten. Eine Nachfrage deckt beide Fälle ab.
        wants_read = self.use_vault_var.get()
        wants_store = self._wants_vault()
        if (wants_read or wants_store) and self.vault is not None and self.vault.is_locked:
            reason = ("Zum Verwenden und Speichern der Passwörter" if wants_store
                      else "Zum Verwenden der gespeicherten Passwörter")
            if not ensure_vault_unlocked(self, self.vault, reason) and wants_store:
                messagebox.showinfo(
                    self.title_text,
                    "Ohne Tresor werden die Passwörter nur für die laufende "
                    "Sitzung gemerkt (beim Schließen verworfen).")
        self._busy = True
        self.progress.start(12)
        self._log_clear()
        threading.Thread(target=self._worker, args=(op, done_msg), daemon=True).start()

    def _worker(self, op, done_msg):
        for cam in self.cameras:
            ip = get_first_ip(cam) or "?"
            name = cam.get("Name", "?")
            plugin = self.plugin_for(cam)
            if plugin is None:
                self._q.put(("line", f"✗ {name} ({ip}): kein Plugin"))
                continue
            try:
                msg = op(plugin, cam, self.creds_for(cam))
                self._q.put(("line", f"✓ {name} ({ip}): {msg or 'OK'}"))
            except Exception as exc:  # noqa: BLE001 - per-camera failure is logged
                self._q.put(("line", f"✗ {name} ({ip}): {exc}"))
        self._q.put(("done", done_msg))

    # --------------------------------------------------------------------- queue
    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "line":
                    self._log_line(payload)
                elif kind == "done":
                    self.progress.stop()
                    self._busy = False
                    self._log_line(f"— {payload}")
                    self._on_done()
        except queue.Empty:
            pass
        self.after(120, self._poll)

    # ----------------------------------------------------------------------- log
    def _log_clear(self):
        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.config(state=tk.DISABLED)

    def _log_line(self, text):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)
