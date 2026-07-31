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

"""Factory-reset action: reset the selected cameras to factory settings.

Reachable from the table's right-click menu for **every** vendor whose plugin
declares ``Capability.FACTORY_RESET`` (Axis, Hikvision, Hanwha, Dahua, ONVIF) — it
used to be buried in the Axis-only configuration dialog. Two modes:

- **Werksreset mit Erhalt der IP-Adresse** (``keep_ip=True``): network settings stay,
  so the camera reappears at the same address; after the reboot the dialog waits until
  it answers again and is in the out-of-box state.
- **Kompletter Werksreset** (``keep_ip=False``): the camera drops to its default/DHCP
  address — not pollable at the old target, so only a hint is logged.

All vendor work goes through the camera's :class:`~kkm.core.VendorPlugin`
(``factory_reset`` / ``is_unconfigured``). After the run, the (now invalid) stored
credentials of the reset cameras are discarded via the main window's
``after_factory_reset`` hook.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from kkm.core import Capability, camera_key, get_first_ip, t
from .base import ActionDialog


class FactoryResetDialog(ActionDialog):
    title_text = "Werkseinstellungen"
    capability = Capability.FACTORY_RESET

    def build_body(self, parent):
        # camera_keys der zurückgesetzten Kameras: alle (Zugangsdaten ungültig ->
        # aufräumen) bzw. bestätigt werksneu (-> in der Liste kennzeichnen).
        self._reset_all_keys: list[str] = []
        self._reset_factory_keys: list[str] = []
        self._reset_mode = tk.StringVar(value="keep")

        ttk.Label(parent, text=t("Setzt die Kamera(s) zurück; sie starten danach neu.")).pack(
            anchor=tk.W)
        ttk.Radiobutton(parent, text=t("Werksreset mit Erhalt der IP-Adresse"),
                        value="keep", variable=self._reset_mode).pack(anchor=tk.W, pady=(6, 0))
        ttk.Radiobutton(parent, text=t("Kompletter Werksreset (inkl. IP-Adresse)"),
                        value="full", variable=self._reset_mode).pack(anchor=tk.W)
        ttk.Button(parent, text=t("Auf Werkseinstellungen zurücksetzen"),
                   command=self._do_factory_reset).pack(anchor=tk.W, pady=(10, 0))

    # ------------------------------------------------------------- factory reset
    def _do_factory_reset(self):
        keep_ip = self._reset_mode.get() == "keep"
        mode = (t("mit Erhalt der IP-Adresse") if keep_ip
                else t("inkl. IP-Adresse — kompletter Reset"))
        if not messagebox.askyesno(
                t(self.title_text),
                t("{n} Kamera(s) auf Werkseinstellungen zurücksetzen ({mode})?\n\n"
                  "Die Kameras starten danach neu. Diese Aktion kann "
                  "nicht rückgängig gemacht werden.", n=len(self.cameras), mode=mode), parent=self):
            return
        self._reset_all_keys.clear()
        self._reset_factory_keys.clear()

        def op(plugin, camera, creds):
            key = camera_key(camera)
            plugin.factory_reset(camera, creds, keep_ip=keep_ip)   # löst Reset aus
            self._reset_all_keys.append(key)   # Zugangsdaten sind jetzt ungültig
            if not keep_ip:
                # IP ändert sich -> nicht am alten Ziel pollbar. Nur Hinweis.
                return t("Reset ausgelöst — Kamera startet neu und ist danach unter "
                         "Standard-/DHCP-Adresse erreichbar (bitte neu suchen).")
            # keep_ip: warten, bis die Kamera neu gestartet und wieder erreichbar
            # UND im Werkszustand (Erstkonfiguration) ist.
            if self._wait_until_factory(plugin, camera, creds):
                self._reset_factory_keys.append(key)
                return t("Werksreset erfolgreich — Kamera wieder erreichbar, "
                         "Erstkonfiguration erforderlich.")
            return t("Reset ausgelöst, aber Kamera kam im Zeitfenster nicht "
                     "erreichbar/werksneu zurück — später erneut suchen.")

        self.run_per_camera(op, done_msg=t("Werksreset abgeschlossen."))

    def _wait_until_factory(self, plugin, camera, creds,
                            timeout=180, interval=5) -> bool:
        """Pollt (im Worker-Thread) die Kamera, bis sie nach dem Neustart wieder
        antwortet und sich im Auslieferungszustand befindet. Gibt True zurück,
        sobald der Werkszustand bestätigt ist."""
        name = camera.get("Name", "?")
        ip = get_first_ip(camera) or "?"
        msg = "… " + t("{name} ({ip}): warte auf Neustart und Erstkonfigurationsmodus…",
                       name=name, ip=ip)
        return bool(self.poll_until(
            lambda: plugin.is_unconfigured(camera, creds),
            timeout, interval, start_msg=msg))

    def _on_done(self):
        """Nach dem Durchlauf: Zugangsdaten der zurückgesetzten Kameras verwerfen
        und werksneu bestätigte Kameras in der Liste kennzeichnen."""
        all_keys = getattr(self, "_reset_all_keys", None)
        if not all_keys:
            return
        hook = getattr(self.master, "after_factory_reset", None)
        if callable(hook):
            hook(list(all_keys), list(self._reset_factory_keys))
        self._reset_all_keys.clear()
        self._reset_factory_keys.clear()
