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
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk, messagebox, simpledialog
from kkm.gui import filedialogs as filedialog   # feste Dialoggröße

from kkm.core import Credentials, camera_key, get_first_ip, looks_like_zip, t
from .vault_access import ensure_vault_unlocked
from .reauth_prompt import ReauthPromptDialog


class ActionDialog(tk.Toplevel):
    #: German source string used as message id — translated at display time via
    #: ``t()`` because class attributes are evaluated at import (before the active
    #: language is known). Subclasses override with their own German title.
    title_text = "Aktion"
    #: Zeilen des Ergebnis-Logs. Dialoge mit viel eigenem Inhalt (Firmware) setzen
    #: das kleiner, damit sie auf kleine Bildschirme passen.
    log_height = 8

    def __init__(self, parent, cameras: list[dict], registry, vault=None):
        super().__init__(parent)
        self.title(t(self.title_text))
        self.transient(parent)
        self.cameras = cameras
        self.registry = registry
        self.vault = vault
        self._q: queue.Queue = queue.Queue()
        self._busy = False
        # Re-Auth: pro Kamera überschriebene Zugangsdaten (nach erneuter Passwortabfrage),
        # gültig für die Dialog-Sitzung; und der Zustand des laufenden Retry-Durchlaufs.
        self._creds_override: dict = {}
        self._active_op = None
        self._reauth_in_progress = False
        self._reauth_cams: list = []
        self._reauth_store = False

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text=t("{n} Kamera(s) ausgewählt", n=len(cameras)),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)

        self._build_credentials(outer)

        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True, pady=6)
        self.build_body(body)

        # --- result log ---
        logframe = ttk.LabelFrame(outer, text=t("Ergebnis"), padding=6)
        logframe.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.log = tk.Text(logframe, height=self.log_height, state=tk.DISABLED,
                           wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)

        self.progress = ttk.Progressbar(outer, mode="indeterminate", length=200)
        self.progress.pack(fill=tk.X, pady=(6, 0))

        # Auf kleinen Bildschirmen nicht höher werden als der Bildschirm: Der Dialog
        # bleibt scrollbar dort, wo Inhalt anfällt (Kameraliste, Ergebnis-Log).
        self.update_idletasks()
        max_h = self.winfo_screenheight() - 80
        if self.winfo_reqheight() > max_h:
            self.geometry(f"{self.winfo_reqwidth()}x{max_h}+40+20")
        self.maxsize(self.winfo_screenwidth(), max_h)

        # Schließen wird abgefangen: läuft noch ein Durchlauf, erst nachfragen.
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._poll)

    def _on_close(self):
        """Fenster-Schließen: bei laufendem Durchlauf zuerst rückfragen (der
        Worker-Thread selbst läuft als Daemon im Hintergrund weiter)."""
        if self._busy and not messagebox.askyesno(
                t(self.title_text),
                t("Ein Vorgang läuft noch. Dialog trotzdem schließen?\n"
                  "(Die laufenden Kamera-Zugriffe werden im Hintergrund beendet, "
                  "ihre Ergebnisse sind dann aber nicht mehr sichtbar.)"),
                parent=self):
            return
        self.destroy()

    # ------------------------------------------------------------ credentials
    def _build_credentials(self, parent):
        cred = ttk.LabelFrame(parent, text=t("Zugangsdaten"), padding=8)
        cred.pack(fill=tk.X, pady=(8, 4))
        # Standard-Benutzer je Hersteller vorbelegen (Axis „root", sonst meist „admin")
        # — sonst schlaegt jede Aktion an einer Nicht-Axis-Kamera mit 401 fehl.
        default_user = getattr(self.plugin0(), "default_username", "root") or "root"
        self.user_var = tk.StringVar(value=default_user)
        self.pass_var = tk.StringVar()
        self.scheme_var = tk.StringVar(value="auto")
        self.port_var = tk.StringVar()
        self.timeout_var = tk.IntVar(value=10)

        ttk.Label(cred, text=t("Benutzer:")).grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self._user_entry = ttk.Entry(cred, textvariable=self.user_var, width=18)
        self._user_entry.grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(cred, text=t("Passwort:")).grid(row=0, column=2, sticky=tk.W, padx=4, pady=2)
        self._pass_entry = ttk.Entry(cred, textvariable=self.pass_var, width=18, show="*")
        self._pass_entry.grid(row=0, column=3, padx=4, pady=2)
        ttk.Label(cred, text=t("Verbindung:")).grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Combobox(cred, textvariable=self.scheme_var, width=15, state="readonly",
                     values=("auto", "https", "http")).grid(row=1, column=1, padx=4, pady=2)
        ttk.Label(cred, text=t("Port (optional):")).grid(row=1, column=2, sticky=tk.W, padx=4, pady=2)
        ttk.Entry(cred, textvariable=self.port_var, width=18).grid(row=1, column=3, padx=4, pady=2)
        ttk.Label(cred, text=t("Timeout (s):")).grid(row=2, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Spinbox(cred, from_=2, to=120, width=6, textvariable=self.timeout_var).grid(
            row=2, column=1, sticky=tk.W, padx=4, pady=2)

        # Zugangsdaten aus dem Tresor verwenden (pro Kamera Benutzer+Passwort).
        # Standardmaessig an, sobald ein Tresor existiert; die Felder oben dienen
        # dann nur als Rueckfall fuer Kameras ohne Tresor-Eintrag.
        self.use_vault_var = tk.BooleanVar(value=self.vault is not None)
        self._vault_chk = ttk.Checkbutton(
            cred, variable=self.use_vault_var, command=self._on_use_vault_toggle,
            text=t("Zugangsdaten aus Tresor verwenden — Felder oben nur als Rückfall"))
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
        """Zugangsdaten je Kamera. Ein per erneuter Passwortabfrage gesetztes Override
        gewinnt vor allem anderen; sonst gewinnt bei aktivem „Aus Tresor verwenden" und
        entsperrtem Tresor **immer** der Tresor-Eintrag (Benutzer + Passwort); die
        Dialogfelder dienen nur als Rückfall für Kameras ohne Eintrag."""
        creds = self.credentials()
        override = self._creds_override.get(camera_key(camera))
        if override:
            creds.username, creds.password = override
            return creds
        if self.use_vault_var.get() and self.vault and not self.vault.is_locked:
            stored = self.vault.get_password(camera_key(camera))
            if stored:
                creds.username = stored.get("username", creds.username)
                creds.password = stored.get("password", creds.password)
        return creds

    def plugin_for(self, camera: dict):
        return self.registry.get(camera.get("_vendor", "axis"))

    def plugin0(self):
        """Plugin der ersten ausgewählten Kamera — für alles, was der Dialog *vor*
        dem eigentlichen Durchlauf vom Hersteller braucht (Rollen, ONVIF-Stufen,
        Dateiformate). Die Aktion ist ohnehin nur wählbar, wenn das Plugin sie meldet."""
        return self.plugin_for(self.cameras[0]) if self.cameras else None

    def choose_user_list(self, title):
        """Datei-Auswahl für eine Benutzerliste inkl. optionaler ZIP-Entschlüsselung.

        Liefert ``(path, zip_password)`` oder ``(None, None)`` bei Abbruch. Ist die
        gewählte Datei ein passwortgeschütztes ZIP (WinZip-AES-256, z. B. mit
        7-Zip/WinZip erstellt), wird das Archiv-Passwort maskiert abgefragt."""
        path = filedialog.askopenfilename(
            parent=self, title=title,
            filetypes=[(t("Textliste/CSV"), "*.txt *.csv"),
                       (t("Verschlüsseltes ZIP"), "*.zip"),
                       (t("Alle Dateien"), "*.*")])
        if not path:
            return None, None
        zip_password = None
        if looks_like_zip(path):
            zip_password = simpledialog.askstring(
                t("ZIP-Passwort"), t("Passwort des verschlüsselten ZIP-Archivs:"),
                show="*", parent=self)
            if zip_password is None:      # Abbruch der Passwortabfrage
                return None, None
        return path, zip_password

    # ----------------------------------------------------------------- to override
    def build_body(self, parent):  # pragma: no cover - overridden
        raise NotImplementedError

    def _on_done(self):
        """Hook: läuft im Main-Thread, sobald ein ``run_per_camera``-Durchlauf
        fertig ist. Unterklassen können hier die Kameraliste aktualisieren."""

    # ------------------------------------------------------------- poll-Helfer
    def poll_until(self, predicate, timeout, interval, start_msg=None):
        """Im Worker-Thread wiederholt ``predicate()`` auswerten, bis es einen
        truthy-Wert liefert (der zurückgegeben wird) oder *timeout* (Sekunden)
        abläuft (dann ``None``). Nützlich, um nach einem Neustart auf die
        Wiedererreichbarkeit einer Kamera zu warten. Fehler in ``predicate`` (z. B.
        während des Reboots) werden verschluckt und weiter gepollt. *start_msg*
        wird — falls gesetzt — einmal ins Ergebnis-Log geschrieben."""
        if start_msg:
            self._q.put(("line", start_msg))
        deadline = time.time() + timeout
        time.sleep(interval)        # das Gerät geht nach dem Auslösen erst offline
        while time.time() < deadline:
            try:
                result = predicate()
                if result:
                    return result
            except Exception:  # noqa: BLE001 - Reboot -> Fehler sind erwartbar
                pass
            time.sleep(interval)
        return None

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
    def run_per_camera(self, op, done_msg=None, parallel=False, max_workers=4,
                       cameras=None):
        """Run ``op(plugin, camera, creds)`` for each camera in a worker thread.

        ``op`` returns a short status string on success or raises on failure; each
        outcome is logged per camera. Disables re-entry while busy.

        Mit ``parallel=True`` werden die Kameras nebenläufig (Thread-Pool, höchstens
        ``max_workers`` gleichzeitig) statt nacheinander abgearbeitet — sinnvoll für
        langlaufende Operationen wie Firmware-Updates. ``cameras`` schränkt den Durchlauf
        auf eine Teilmenge ein (für den erneuten Versuch nach einer Passwort-Neueingabe);
        Standard ist die ganze Auswahl.
        """
        if self._busy:
            return
        if done_msg is None:
            done_msg = t("Fertig.")
        self._parallel = parallel
        self._max_workers = max(1, int(max_workers))
        # Für einen etwaigen erneuten Versuch nach Auth-Fehler merken.
        self._active_op = op
        self._active_parallel = parallel
        self._active_max_workers = self._max_workers
        self._run_cameras = list(cameras) if cameras is not None else self.cameras
        self._auth_failures = []
        # Tresor wird gebraucht (zum Lesen der Passwörter und/oder zum Speichern),
        # ist aber gesperrt/nicht angelegt -> auf dem Main-Thread anbieten, ihn
        # einzurichten. Eine Nachfrage deckt beide Fälle ab.
        wants_read = self.use_vault_var.get()
        wants_store = self._wants_vault()
        if (wants_read or wants_store) and self.vault is not None and self.vault.is_locked:
            reason = (t("Zum Verwenden und Speichern der Passwörter") if wants_store
                      else t("Zum Verwenden der gespeicherten Passwörter"))
            if not ensure_vault_unlocked(self, self.vault, reason) and wants_store:
                messagebox.showinfo(
                    t(self.title_text),
                    t("Ohne Tresor werden die Passwörter nur für die laufende "
                      "Sitzung gemerkt (beim Schließen verworfen)."), parent=self)
        self._busy = True
        self.progress.start(12)
        self._log_clear()
        threading.Thread(target=self._worker, args=(op, done_msg), daemon=True).start()

    def _run_one(self, op, cam):
        """Führt ``op`` für **eine** Kamera aus und protokolliert das Ergebnis."""
        ip = get_first_ip(cam) or "?"
        name = cam.get("Name", "?")
        plugin = self.plugin_for(cam)
        if plugin is None:
            self._q.put(("line", f"✗ {name} ({ip}): " + t("kein Plugin")))
            return
        try:
            msg = op(plugin, cam, self.creds_for(cam))
            self._q.put(("line", f"✓ {name} ({ip}): {msg or 'OK'}"))
        except Exception as exc:  # noqa: BLE001 - per-camera failure is logged
            # Auth-Fehler (401): Kamera vormerken, damit der Dialog nach dem Durchlauf das
            # Passwort erneut abfragen und die Aktion wiederholen kann.
            if plugin.is_auth_error(exc):
                self._q.put(("authfail", cam))
                self._q.put(("line", f"✗ {name} ({ip}): {exc} — "
                             + t("Passwort ggf. veraltet.")))
            else:
                self._q.put(("line", f"✗ {name} ({ip}): {exc}"))

    def _worker(self, op, done_msg):
        cams = getattr(self, "_run_cameras", self.cameras)
        if getattr(self, "_parallel", False) and len(cams) > 1:
            # Nebenläufig, aber gedeckelt (max_workers). Die Ergebnis-Queue ist
            # thread-sicher; Log-Zeilen können sich dadurch verschränken.
            workers = min(self._max_workers, len(cams))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                list(ex.map(lambda cam: self._run_one(op, cam), cams))
        else:
            for cam in cams:
                self._run_one(op, cam)
        self._q.put(("done", done_msg))

    # --------------------------------------------------------------------- queue
    def _poll(self):
        # Nach dem Schließen des Dialogs können noch Meldungen des Worker-Threads
        # eintreffen — die Widgets sind dann zerstört, also Schleife beenden statt
        # mit TclError zu sterben.
        if not self.winfo_exists():
            return
        done_seen = False
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "line":
                    self._log_line(payload)
                elif kind == "authfail":
                    self._auth_failures.append(payload)
                elif kind == "done":
                    self.progress.stop()
                    self._busy = False
                    self._log_line(f"— {payload}")
                    self._on_done()
                    done_seen = True
        except queue.Empty:
            pass
        # Erst nach dem Leeren der Queue behandeln — kann modal nachfragen und einen
        # erneuten Durchlauf starten (setzt dann wieder ``_busy``).
        if done_seen:
            self._handle_auth_failures()
        self.after(120, self._poll)

    # ------------------------------------------------------- erneute Passwortabfrage
    def _handle_auth_failures(self):
        """Nach einem Durchlauf: erfolgreiche Retries im Tresor nachziehen und, wenn noch
        Kameras die Zugangsdaten ablehnen, das Passwort erneut abfragen und wiederholen."""
        # War das gerade ein Wiederholungs-Durchlauf? Was diesmal *nicht* wieder scheiterte,
        # gilt als erfolgreich — dessen neues Passwort ggf. in den Tresor übernehmen.
        if self._reauth_in_progress:
            self._reauth_in_progress = False
            failed_now = {camera_key(c) for c in self._auth_failures}
            if self._reauth_store:
                for cam in self._reauth_cams:
                    if camera_key(cam) not in failed_now:
                        self._persist_override(cam)
        if self._auth_failures and self._active_op is not None:
            self._prompt_and_retry(list(self._auth_failures))

    def _prompt_and_retry(self, cams):
        default_user = self.creds_for(cams[0]).username
        can_store = bool(self.vault and not self.vault.is_locked)
        dlg = ReauthPromptDialog(self, cams, default_user=default_user, can_store=can_store)
        self.wait_window(dlg)
        if not dlg.result or dlg.result[0] != "apply":
            return
        _, user, password, store = dlg.result
        for cam in cams:
            self._creds_override[camera_key(cam)] = (user, password)
        self._reauth_in_progress = True
        self._reauth_cams = cams
        self._reauth_store = store
        self.run_per_camera(self._active_op, done_msg=t("Erneuter Versuch abgeschlossen."),
                            parallel=getattr(self, "_active_parallel", False),
                            max_workers=getattr(self, "_active_max_workers", 4),
                            cameras=cams)

    def _persist_override(self, camera):
        """Übernimmt die per Re-Auth gesetzten Zugangsdaten der Kamera in den Tresor
        (und den Sitzungs-Cache des Hauptfensters)."""
        ov = self._creds_override.get(camera_key(camera))
        if not ov:
            return
        username, password = ov
        key = camera_key(camera)
        if self.vault and not self.vault.is_locked:
            self.vault.set_password(key, username, password)
        cache = getattr(self.master, "_cam_creds", None)
        if cache is not None:
            cache[key] = (username, password)

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
