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

Beyond assigning local files, the dialog can look the models up **online**
(``Capability.FIRMWARE_CHECK``): the plugin reports which versions exist and which
one it recommends, the download lands in a cache and is then assigned to the model
exactly like a hand-picked file — the upgrade path below stays untouched. Lookup and
download run on background threads and report through queues polled with ``after()``,
like everything else here.
"""

from __future__ import annotations

import os
import time
import queue
import threading
import dataclasses
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
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
CHECK_WORKERS = 4        # parallele Modell-Abfragen bei der Update-Suche


def _model_of(camera: dict) -> str:
    return camera.get("_model") or camera.get("Name") or "?"


def _mb(size: int) -> str:
    return f"{size / (1024 * 1024):.0f} MB" if size else "?"


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
        # Online-Suche: Ergebnisse und (abweichende) Versionswahl je Modell.
        self._info_by_model: dict[str, object] = {}   # model -> FirmwareInfo
        self._pick_by_model: dict[str, str] = {}      # model -> gewählte Version
        self._repo_q: queue.Queue = queue.Queue()     # Worker -> GUI
        self._repo_busy = False
        self._cancel = threading.Event()

        ttk.Label(
            parent,
            text="Pro Modell eine passende Firmware-Datei zuweisen — von Hand oder "
                 "über die Update-Suche. Eine Modellzeile lässt sich aufklappen, um "
                 "die einzelnen Kameras zu sehen.",
            wraplength=560, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 6))

        cols = ("count", "current", "online", "file")
        self.tree = ttk.Treeview(parent, columns=cols, show="tree headings", height=10,
                                 selectmode="browse")
        self.tree.heading("#0", text="Modell / Kamera")
        self.tree.heading("count", text="Kameras")
        self.tree.heading("current", text="Aktuelle Firmware")
        self.tree.heading("online", text="Verfügbar (online)")
        self.tree.heading("file", text="Neue Firmware-Datei")
        self.tree.column("#0", width=200)
        self.tree.column("count", width=60, anchor=tk.CENTER)
        self.tree.column("current", width=120, anchor=tk.CENTER)
        self.tree.column("online", width=150, anchor=tk.CENTER)
        self.tree.column("file", width=220)
        self.tree.pack(fill=tk.X)
        # Erfolgs-Markierung: grüne Zeile.
        self.tree.tag_configure("done", background="#2e7d32", foreground="white")
        for model, cams in sorted(self._by_model.items()):
            fws = sorted({(c.get("_firmware") or "").strip()
                          for c in cams if (c.get("_firmware") or "").strip()})
            summary = fws[0] if len(fws) == 1 else ("verschieden" if fws else "—")
            self.tree.insert("", "end", iid=model, text=model, open=False,
                             values=(len(cams), summary, "—", "—"))
            for cam in cams:
                key = camera_key(cam)
                child = f"cam::{key}"
                name = cam.get("Name", "?")
                ip = get_first_ip(cam) or "—"
                cur = (cam.get("_firmware") or "").strip() or "?"
                self.tree.insert(model, "end", iid=child, text=f"{name} ({ip})",
                                 values=("", cur, "", ""))
                self._cam_row[key] = child
                self._model_of_key[key] = model

        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=6)
        ttk.Button(row, text="Firmware-Datei für Modell wählen…",
                   command=self._choose_for_model).pack(side=tk.LEFT)
        ttk.Button(row, text="Zuweisung entfernen",
                   command=self._clear_for_model).pack(side=tk.LEFT, padx=6)

        self._build_repo_row(parent)

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

    # -------------------------------------------------------------- update-suche
    def _settings(self):
        return getattr(self.master, "settings", None)

    def _repo_plugin(self):
        """Plugin der ausgewählten Kameras, sofern es die Online-Suche beherrscht."""
        plugin = self.plugin_for(self.cameras[0]) if self.cameras else None
        if plugin is None or not plugin.supports(Capability.FIRMWARE_CHECK):
            return None
        settings = self._settings()
        if settings and not settings.get("firmware_check_online", True):
            return None
        url = (settings.get("firmware_repo_url") or "").strip() if settings else ""
        if url:
            plugin.repo_url = url          # interner Spiegel aus den Einstellungen
        return plugin

    def _build_repo_row(self, parent):
        """Zeile für die Online-Update-Suche — nur, wenn das Plugin sie anbietet."""
        if self._repo_plugin() is None:
            return
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 4))
        self._btn_check = ttk.Button(row, text="Nach Updates suchen",
                                     command=self._check_updates)
        self._btn_check.pack(side=tk.LEFT)
        self._btn_get = ttk.Button(row, text="Update herunterladen und zuweisen",
                                   command=self._download_updates, state=tk.DISABLED)
        self._btn_get.pack(side=tk.LEFT, padx=6)
        self._btn_pick = ttk.Button(row, text="Version wählen…",
                                    command=self._pick_version, state=tk.DISABLED)
        self._btn_pick.pack(side=tk.LEFT)

        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X)
        self._repo_status = ttk.Label(bar, text="")
        self._repo_status.pack(side=tk.LEFT)
        self._repo_bar = ttk.Progressbar(bar, mode="determinate", length=180,
                                         maximum=100)
        # Balken erscheint erst beim Download (pack/pack_forget).

    def _repo_set_busy(self, busy: bool):
        self._repo_busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self._btn_check.config(state=state)
        have = bool(self._info_by_model)
        self._btn_get.config(state=tk.DISABLED if busy or not have else tk.NORMAL)
        self._btn_pick.config(state=tk.DISABLED if busy or not have else tk.NORMAL)

    def _current_of_model(self, model: str) -> str:
        """Vergleichsbasis einer Modellzeile: die **neueste** Firmware unter ihren
        Kameras. Eine Modellzeile bekommt genau eine Datei, die auf alle Kameras der
        Zeile geht — wäre die Basis der älteste Stand, würde bei gemischten Ständen
        (eine Kamera auf 10.12, eine auf 11.11) ein Vorschlag herauskommen, der für
        die neuere Kamera ein **Downgrade** ist. Vom neuesten Stand aus ist der
        Vorschlag für jede Kamera der Zeile ein Schritt nach vorn."""
        from kkm.plugins.axis.firmware_repo import version_tuple
        vers = [(c.get("_firmware") or "").strip()
                for c in self._by_model.get(model, [])]
        vers = [v for v in vers if v]
        return max(vers, key=version_tuple) if vers else ""

    def _check_updates(self):
        plugin = self._repo_plugin()
        if plugin is None or self._repo_busy:
            return
        settings = self._settings()
        prefer_track = bool(settings.get("firmware_prefer_track", True)) if settings else True
        models = sorted(self._by_model)
        self._repo_set_busy(True)
        self._repo_status.config(text="Suche nach Updates …")
        for model in models:
            self.tree.set(model, "online", "…")

        def work():
            def one(model):
                current = self._current_of_model(model)
                try:
                    info = plugin.firmware_updates(model, current, prefer_track)
                except Exception as exc:  # noqa: BLE001 - je Modell melden, nicht abbrechen
                    self._repo_q.put(("fail", model, str(exc)))
                    return
                self._repo_q.put(("info", model, info))

            workers = min(CHECK_WORKERS, max(1, len(models)))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                list(ex.map(one, models))
            self._repo_q.put(("checked", None, None))

        threading.Thread(target=work, daemon=True).start()

    def _online_text(self, model: str) -> str:
        info = self._info_by_model.get(model)
        if info is None:
            return "—"
        pick = self._pick_by_model.get(model)
        if pick:
            return f"{pick} (gewählt)"
        if info.recommended:
            return f"{info.recommended} ↑"
        return f"{info.latest or '?'} (aktuell)"

    def _pending_version(self, model: str) -> str:
        """Version, die für dieses Modell geladen werden soll ('' = nichts zu tun)."""
        info = self._info_by_model.get(model)
        if info is None:
            return ""
        return self._pick_by_model.get(model) or info.recommended or ""

    def _pick_version(self):
        """Andere als die vorgeschlagene Version wählen (z. B. Sprung auf den
        Active-Track oder bewusst eine ältere Version)."""
        model = self._selected_model()
        if not model:
            messagebox.showinfo(self.title_text, "Bitte zuerst ein Modell auswählen.",
                                parent=self)
            return
        info = self._info_by_model.get(model)
        if info is None or not info.versions:
            messagebox.showinfo(self.title_text,
                                "Für dieses Modell liegt kein Suchergebnis vor.",
                                parent=self)
            return
        version = _VersionPicker(self, model, info,
                                 self._pick_by_model.get(model)).result
        if version:
            self._pick_by_model[model] = version
            self.tree.set(model, "online", self._online_text(model))

    def _download_updates(self):
        """Firmware für das ausgewählte Modell (oder alle mit Update) laden und
        als Datei-Zuweisung eintragen — der Upload-Weg unten bleibt unverändert."""
        plugin = self._repo_plugin()
        if plugin is None or self._repo_busy:
            return
        selected = self._selected_model()
        models = [selected] if selected else sorted(self._by_model)
        todo = [(m, self._pending_version(m)) for m in models if self._pending_version(m)]
        if not todo:
            messagebox.showinfo(
                self.title_text,
                "Kein Update zum Herunterladen — entweder sind die Kameras aktuell "
                "oder es wurde noch nicht gesucht.", parent=self)
            return

        self._cancel.clear()
        self._repo_set_busy(True)
        self._repo_bar.pack(side=tk.LEFT, padx=8)
        self._repo_bar["value"] = 0

        def work():
            for model, version in todo:
                try:
                    rel = plugin.firmware_release(model, version)
                    self._repo_q.put((
                        "status", None,
                        f"Lade {rel.filename} ({rel.version}, {_mb(rel.size)}) …"))

                    last = [0.0]

                    def progress(done, total, _last=last):
                        pct = (done * 100.0 / total) if total else 0.0
                        if pct - _last[0] >= 1 or done == total:
                            _last[0] = pct
                            self._repo_q.put(("progress", None, pct))

                    path = plugin.download_firmware(rel, progress=progress,
                                                    cancelled=self._cancel.is_set)
                    self._repo_q.put(("assigned", model, (rel.version, path)))
                except Exception as exc:  # noqa: BLE001 - je Modell melden
                    self._repo_q.put(("fail", model, str(exc)))
                if self._cancel.is_set():
                    break
            self._repo_q.put(("loaded", None, None))

        threading.Thread(target=work, daemon=True).start()

    def _drain_repo(self):
        """Meldungen der Such-/Download-Threads im Main-Thread verarbeiten."""
        try:
            while True:
                kind, model, payload = self._repo_q.get_nowait()
                if kind == "info":
                    self._info_by_model[model] = payload
                    self._pick_by_model.pop(model, None)
                    self.tree.set(model, "online", self._online_text(model))
                    if payload.recommended:
                        self._q.put(("line", f"↑ {model}: {payload.current or '?'} → "
                                             f"{payload.recommended} verfügbar"))
                    else:
                        self._q.put(("line", f"✓ {model}: aktuell "
                                             f"({payload.latest or '?'})"))
                elif kind == "fail":
                    if model and self.tree.exists(model):
                        self.tree.set(model, "online", "?")
                    self._q.put(("line", f"✗ {model}: {payload}"))
                elif kind == "status":
                    self._repo_status.config(text=payload)
                elif kind == "progress":
                    self._repo_bar["value"] = payload
                elif kind == "assigned":
                    version, path = payload
                    self._fw_by_model[model] = path
                    self._pick_by_model[model] = version
                    self.tree.set(model, "file", os.path.basename(path))
                    self.tree.set(model, "online", self._online_text(model))
                    self._q.put(("line", f"✓ {model}: {version} heruntergeladen "
                                         "und zugewiesen"))
                elif kind == "checked":
                    self._repo_set_busy(False)
                    self._repo_status.config(text="")
                elif kind == "loaded":
                    self._repo_set_busy(False)
                    self._repo_bar.pack_forget()
                    self._repo_status.config(text="")
        except queue.Empty:
            pass

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
        self._drain_repo()          # Ergebnisse der Update-Suche/Downloads
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


class _VersionPicker(tk.Toplevel):
    """Auswahl einer anderen als der vorgeschlagenen Version eines Modells.

    Nötig, weil der Vorschlag bewusst in der Hauptversion der Kamera bleibt (LTS-treu):
    Wer den Sprung auf den Active-Track will — oder gezielt eine ältere Version —,
    wählt sie hier. ``result`` ist die gewählte Version oder ``None``.
    """

    def __init__(self, parent, model, info, preselect=None):
        super().__init__(parent)
        self.title(f"Version wählen — {model}")
        self.transient(parent)
        self.result: str | None = None

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=f"Kameras dieses Modells: {info.current or 'unbekannt'} — "
                              f"vorgeschlagen: {info.recommended or 'kein Update'}",
                  wraplength=360, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 6))

        box = ttk.Frame(frame)
        box.pack(fill=tk.BOTH, expand=True)
        self._list = tk.Listbox(box, height=12, exportselection=False)
        scroll = ttk.Scrollbar(box, orient=tk.VERTICAL, command=self._list.yview)
        self._list.config(yscrollcommand=scroll.set)
        self._list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)

        self._versions = list(info.versions)
        want = preselect or info.recommended or info.latest
        for i, ver in enumerate(self._versions):
            marks = []
            if ver == info.latest:
                marks.append("neueste")
            if ver == info.recommended:
                marks.append("Vorschlag")
            if ver == info.current:
                marks.append("installiert")
            self._list.insert(tk.END, f"{ver}  ({', '.join(marks)})" if marks else ver)
            if ver == want:
                self._list.selection_set(i)
                self._list.see(i)

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(row, text="Übernehmen", command=self._ok).pack(side=tk.LEFT)
        ttk.Button(row, text="Abbrechen", command=self.destroy).pack(side=tk.LEFT, padx=6)
        self._list.bind("<Double-Button-1>", lambda _e: self._ok())

        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        sel = self._list.curselection()
        if sel:
            self.result = self._versions[sel[0]]
        self.destroy()
