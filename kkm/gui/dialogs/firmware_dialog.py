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
import time
import queue
import dataclasses
import tkinter as tk
from tkinter import ttk, messagebox
from kkm.gui import filedialogs as filedialog   # feste Dialoggröße

from kkm.core import Capability, camera_key
from kkm.plugins.axis.discovery import get_first_ip
from .base import ActionDialog

FIRMWARE_TIMEOUT = 600   # seconds; upload + flash takes far longer than a probe
# Warten auf Wiedererreichbarkeit nach dem Neustart (Flash + Reboot dauern lange).
REBOOT_TIMEOUT = 600
REBOOT_INTERVAL = 8
PROBE_TIMEOUT = 15       # kurzes Timeout je Erreichbarkeits-Versuch


def _model_of(camera: dict) -> str:
    return camera.get("_model") or camera.get("Name") or "?"


class FirmwareDialog(ActionDialog):
    title_text = "Firmware aktualisieren"
    capability = Capability.FIRMWARE

    def build_body(self, parent):
        # Nach dem Update in die Liste zu übernehmen:
        self._fw_updates: dict[str, dict] = {}       # key -> device_info (neue FW)
        self._reset_all_keys: list[str] = []         # bei factory-default: Creds weg
        self._reset_factory_keys: list[str] = []     # bestätigt werksneu
        # Erfolge fließen (thread-sicher) aus dem Worker in die GUI zurück, damit
        # die Zeilen live grün werden — auch im Parallelbetrieb.
        self._success_q: queue.Queue = queue.Queue()
        self._cam_row: dict[str, str] = {}           # camera_key -> Kind-iid
        self._model_of_key: dict[str, str] = {}      # camera_key -> Modell-iid
        # model -> assigned firmware path
        self._fw_by_model: dict[str, str] = {}
        # model -> list of cameras
        self._by_model: dict[str, list[dict]] = {}
        for cam in self.cameras:
            self._by_model.setdefault(_model_of(cam), []).append(cam)

        ttk.Label(
            parent,
            text="Pro Modell eine passende Firmware-Datei zuweisen. Eine Modellzeile "
                 "lässt sich aufklappen, um die einzelnen Kameras zu sehen.",
            wraplength=560, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 6))

        cols = ("count", "current", "file")
        self.tree = ttk.Treeview(parent, columns=cols, show="tree headings", height=10,
                                 selectmode="browse")
        self.tree.heading("#0", text="Modell / Kamera")
        self.tree.heading("count", text="Kameras")
        self.tree.heading("current", text="Aktuelle Firmware")
        self.tree.heading("file", text="Neue Firmware-Datei")
        self.tree.column("#0", width=210)
        self.tree.column("count", width=70, anchor=tk.CENTER)
        self.tree.column("current", width=130, anchor=tk.CENTER)
        self.tree.column("file", width=240)
        self.tree.pack(fill=tk.X)
        # Erfolgs-Markierung: grüne Zeile.
        self.tree.tag_configure("done", background="#2e7d32", foreground="white")
        for model, cams in sorted(self._by_model.items()):
            fws = sorted({(c.get("_firmware") or "").strip()
                          for c in cams if (c.get("_firmware") or "").strip()})
            summary = fws[0] if len(fws) == 1 else ("verschieden" if fws else "—")
            self.tree.insert("", "end", iid=model, text=model, open=False,
                             values=(len(cams), summary, "—"))
            for cam in cams:
                key = camera_key(cam)
                child = f"cam::{key}"
                name = cam.get("Name", "?")
                ip = get_first_ip(cam) or "—"
                cur = (cam.get("_firmware") or "").strip() or "?"
                self.tree.insert(model, "end", iid=child, text=f"{name} ({ip})",
                                 values=("", cur, ""))
                self._cam_row[key] = child
                self._model_of_key[key] = model

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

        self.after(200, self._drain_success)   # Erfolge -> Zeilen grün färben

    # --------------------------------------------------------------- assignment
    def _selected_model(self) -> str | None:
        """Ausgewähltes Modell — auch, wenn eine einzelne Kamera (Kind) markiert ist
        (dann liefern wir deren Modellzeile)."""
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.parent(sel[0]) or sel[0]

    def _choose_for_model(self):
        model = self._selected_model()
        if not model:
            messagebox.showinfo(self.title_text, "Bitte zuerst ein Modell auswählen.", parent=self)
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
                                "Bitte mindestens einem Modell eine Firmware zuweisen.", parent=self)
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
        self._fw_updates.clear()
        self._reset_all_keys.clear()
        self._reset_factory_keys.clear()

        def op(plugin, camera, creds):
            model = _model_of(camera)
            path = fw_by_model.get(model)
            if not path:
                raise RuntimeError("übersprungen (keine Firmware für dieses Modell)")
            fname = os.path.basename(path)
            key = camera_key(camera)
            name = camera.get("Name", "?")
            ip = get_first_ip(camera) or "?"
            # Kurzes Timeout zum Anklopfen (nicht das lange Upload-Timeout).
            probe = dataclasses.replace(creds, timeout=PROBE_TIMEOUT)
            # Aktuelle Firmware vor dem Update merken (Fallback-Signal: Versionswechsel).
            old_fw = camera.get("_firmware") or ""
            try:
                pre = plugin.device_info(camera, probe)
                old_fw = pre.get("firmware") or old_fw
            except Exception:  # noqa: BLE001 - vorab-Lesen ist nur best effort
                pass

            creds.timeout = max(creds.timeout, FIRMWARE_TIMEOUT)
            plugin.upgrade_firmware(camera, creds, path, factory_default=factory)

            if factory:
                # factory-default beim Update -> Kamera kommt werksneu zurück.
                msg = f"… {name} ({ip}): warte auf Neustart (Werkszustand)…"
                if self.poll_until(lambda: plugin.is_unconfigured(camera, probe),
                                   REBOOT_TIMEOUT, REBOOT_INTERVAL, start_msg=msg):
                    self._reset_all_keys.append(key)
                    self._reset_factory_keys.append(key)
                    self._success_q.put((key, "werksneu"))
                    return (f"Firmware {fname} aufgespielt — Kamera werksneu "
                            "(Erstkonfiguration erforderlich)")
                return (f"Firmware {fname} aufgespielt — Kamera nicht rechtzeitig "
                        "zurück (später prüfen)")

            # Normalfall: auf den Reboot-Zyklus warten und neue Firmware auslesen.
            info = self._wait_reboot_and_info(plugin, camera, probe, old_fw, name, ip)
            if info is not None:
                self._fw_updates[key] = info
                self._success_q.put((key, info.get("firmware") or "?"))
                return (f"Firmware {fname} aufgespielt — Kamera wieder erreichbar, "
                        f"Version {info.get('firmware') or '?'}")
            return (f"Firmware {fname} aufgespielt — Kamera nicht rechtzeitig "
                    "zurück (Version später prüfen)")

        # Parallel-Modus aus den Einstellungen (neuer Reiter „Firmwareupdates").
        settings = getattr(self.master, "settings", None)
        parallel = bool(settings.get("firmware_parallel", True)) if settings else True
        max_workers = int(settings.get("firmware_max_parallel", 4)) if settings else 4
        self.run_per_camera(op, done_msg="Firmware-Update abgeschlossen.",
                            parallel=parallel, max_workers=max_workers)

    def _wait_reboot_and_info(self, plugin, camera, creds, old_fw, name, ip,
                              timeout=REBOOT_TIMEOUT, interval=REBOOT_INTERVAL):
        """Wartet auf den kompletten Reboot-Zyklus nach dem Firmware-Update und
        liest dann die neue Version.

        Wichtig für **alte** Firmware (z. B. M7001): dort bleibt die Kamera nach dem
        Upload zunächst noch erreichbar (alte Firmware) und startet erst danach neu.
        Ein simpler „ist erreichbar?"-Check würde sofort einen Fehl-Erfolg melden.
        Daher gilt als „fertig" erst, wenn die Kamera **zwischendurch offline war**
        (Reboot beobachtet) und wieder antwortet — oder wenn sich die
        **Firmware-Version geändert** hat (falls das Gerät den Neustart intern
        durchläuft, ohne dass wir das Offline-Fenster sehen)."""
        self._q.put(("line", f"… {name} ({ip}): warte auf Neustart "
                             "und lese neue Firmware…"))
        deadline = time.time() + timeout
        went_down = False
        time.sleep(interval)
        while time.time() < deadline:
            if not plugin.check_online(camera, creds):
                went_down = True          # Reboot hat begonnen
                time.sleep(interval)
                continue
            try:
                info = plugin.device_info(camera, creds)
            except Exception:  # noqa: BLE001 - Reboot -> Fehler erwartbar
                info = None
            if info:
                new_fw = info.get("firmware") or ""
                if went_down or (new_fw and new_fw != old_fw):
                    return info
            time.sleep(interval)
        return None

    # ------------------------------------------------------------- grüne Markierung
    def _drain_success(self):
        """Erfolge aus dem Worker (thread-sicher) verarbeiten und die zugehörige
        Zeile grün färben; läuft im Main-Thread."""
        try:
            while True:
                key, new_fw = self._success_q.get_nowait()
                self._mark_row_done(key, new_fw)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(200, self._drain_success)

    def _mark_row_done(self, key, new_fw):
        child = self._cam_row.get(key)
        if child and self.tree.exists(child):
            if new_fw:
                self.tree.set(child, "current", new_fw)   # neue Version anzeigen
            self.tree.item(child, tags=("done",))
        # Modellzeile grün, sobald alle ihre Kameras erledigt sind.
        model = self._model_of_key.get(key)
        if model and self.tree.exists(model):
            kids = self.tree.get_children(model)
            if kids and all("done" in self.tree.item(k, "tags") for k in kids):
                self.tree.item(model, tags=("done",))

    def _on_done(self):
        """Neue Firmware-Versionen bzw. Werkszustand nach dem Update in die Liste
        des Hauptfensters übernehmen."""
        if self._fw_updates:
            hook = getattr(self.master, "apply_firmware_update", None)
            if callable(hook):
                hook(dict(self._fw_updates))
            self._fw_updates.clear()
        if self._reset_all_keys:
            hook = getattr(self.master, "after_factory_reset", None)
            if callable(hook):
                hook(list(self._reset_all_keys), list(self._reset_factory_keys))
            self._reset_all_keys.clear()
            self._reset_factory_keys.clear()
