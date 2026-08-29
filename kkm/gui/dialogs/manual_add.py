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

"""Dialog »Kamera manuell hinzufügen« — Unterpunkt des Suchen/aktualisieren-Buttons.

Fügt eine Kamera über ihre IP-Adresse hinzu, die die Suche (mDNS/WS-Discovery) nicht
gefunden hat. Anders als beim reinen Discovery-Tool muss hier auch der **Hersteller**
gewählt werden: er bestimmt, welches Plugin die Aktionen (IP/Benutzer/Firmware …)
ausführt — ohne ``_vendor`` wüsste das Hauptfenster nicht, wen es fragen soll.

Der Dialog liefert bei Erfolg das fertige Kamera-Dict in :attr:`result` (sonst
``None``); das Hauptfenster nimmt es ins Roster auf. Modal via ``wait_window``.
"""

from __future__ import annotations

import ipaddress
import tkinter as tk
from tkinter import ttk, messagebox

from kkm.core import t, FIELD_NAMES, Capability


class ManualAddDialog(tk.Toplevel):
    """Name/IP/Port/Hostname + Hersteller abfragen und ein Kamera-Dict bauen."""

    def __init__(self, parent, registry, existing_ips):
        super().__init__(parent)
        self.title(t("Kamera manuell hinzufügen"))
        self.transient(parent)
        self.resizable(False, False)
        self.result: dict | None = None
        self._existing_ips = {str(ip).strip().lower() for ip in existing_ips}

        # Hersteller-Auswahl: nur aktivierte Plugins, die überhaupt eine Kamera
        # ansteuern können (Discovery-Fähigkeit reicht als Kriterium: das sind die
        # „echten" Geräte-Plugins). Axis als Vorauswahl, falls vorhanden.
        self._plugins = sorted(
            (p for p in registry.enabled() if p.supports(Capability.DISCOVER)),
            key=lambda p: p.name.casefold())
        self._by_label = {p.name: p for p in self._plugins}

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, wraplength=380, text=t(
            "Fügt eine Kamera über ihre IP-Adresse hinzu, die die Suche nicht "
            "gefunden hat. Der Eintrag bleibt in der Liste und wird durch einen "
            "späteren Suchtreffer derselben IP ersetzt.")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._name_var = tk.StringVar()
        self._ip_var = tk.StringVar()
        self._port_var = tk.StringVar(value="80")
        self._host_var = tk.StringVar()

        rows = [
            (t("Name:"), self._name_var, None),
            (t("IP-Adresse:"), self._ip_var, None),
            (t("Port:"), self._port_var, None),
            (t("Hostname:"), self._host_var, None),
        ]
        entries = {}
        for i, (label, var, _extra) in enumerate(rows, start=1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                            padx=(0, 8), pady=2)
            ent = ttk.Entry(frm, textvariable=var, width=30)
            ent.grid(row=i, column=1, sticky="ew", pady=2)
            entries[label] = ent

        # Hersteller-Combobox (nur wenn es mehr als ein Plugin zur Auswahl gibt;
        # bei genau einem wird es still verwendet).
        row_vendor = len(rows) + 1
        if len(self._plugins) > 1:
            ttk.Label(frm, text=t("Hersteller:")).grid(
                row=row_vendor, column=0, sticky="w", padx=(0, 8), pady=2)
            self._vendor_var = tk.StringVar()
            combo = ttk.Combobox(frm, textvariable=self._vendor_var, state="readonly",
                                 values=[p.name for p in self._plugins], width=28)
            combo.grid(row=row_vendor, column=1, sticky="ew", pady=2)
            default = next((p for p in self._plugins if p.id == "axis"),
                           self._plugins[0])
            self._vendor_var.set(default.name)
        else:
            self._vendor_var = None
        frm.columnconfigure(1, weight=1)

        btns = ttk.Frame(frm)
        btns.grid(row=row_vendor + 1, column=0, columnspan=2, sticky="e",
                  pady=(12, 0))
        ttk.Button(btns, text=t("Abbrechen"), command=self.destroy).pack(
            side=tk.RIGHT)
        ttk.Button(btns, text=t("Hinzufügen"), command=self._submit).pack(
            side=tk.RIGHT, padx=(0, 8))

        entries[t("IP-Adresse:")].focus_set()
        self.bind("<Return>", self._submit)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    def _selected_plugin(self):
        if self._vendor_var is None:
            return self._plugins[0] if self._plugins else None
        return self._by_label.get(self._vendor_var.get())

    def _submit(self, _evt=None):
        ip = self._ip_var.get().strip()
        if not ip:
            messagebox.showwarning(self.title(),
                                   t("Bitte eine IP-Adresse eingeben."), parent=self)
            return
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            messagebox.showwarning(
                self.title(),
                t("„{ip}“ ist keine gültige IP-Adresse.", ip=ip), parent=self)
            return
        if ip.lower() in self._existing_ips:
            messagebox.showinfo(
                self.title(),
                t("Eine Kamera mit der IP-Adresse {ip} ist bereits in der Liste.",
                  ip=ip), parent=self)
            return
        plugin = self._selected_plugin()
        if plugin is None:
            messagebox.showwarning(self.title(),
                                   t("Kein Hersteller-Plugin verfügbar."), parent=self)
            return

        cam = {name: "" for name in FIELD_NAMES}
        cam["Name"] = self._name_var.get().strip() or t("(manuell hinzugefügt)")
        cam["IP Adresse: Konfiguriert"] = ip
        cam["IP Adresse: IPv6"] = ip if addr.version == 6 else ""
        cam["Port"] = self._port_var.get().strip()
        cam["Hostname"] = self._host_var.get().strip()
        cam["_vendor"] = plugin.id
        cam["_manual"] = True     # überlebt die Suche, wird per IP durch echte Treffer ersetzt
        cam["_online"] = None      # noch nicht geprüft
        self.result = cam
        self.destroy()
