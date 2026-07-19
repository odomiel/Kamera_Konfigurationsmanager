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

"""IP address action: set the network configuration of the selected cameras.

Three modes (radio), mirroring the Discovery tool's IP tab:

- **DHCP** — switch all selected cameras to DHCP.
- **Feste IP fortlaufend** — assign static IPs starting at a Start-IP, incremented
  per camera in table order (shared subnet mask + optional gateway).
- **Pro Kamera einzeln** — one IP field per camera (prefilled with its current IP),
  shared subnet mask + gateway.

For the static modes the per-camera target IP is computed and validated *before*
any camera is touched (so a bad address aborts the whole run early), then applied
via :meth:`~kkm.core.VendorPlugin.set_static_ip`; DHCP via ``set_dhcp``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from kkm.core import Capability, camera_key
from kkm.core import next_ip, get_first_ip
from .base import ActionDialog


class IpDialog(ActionDialog):
    title_text = "IP-Adresse setzen"
    capability = Capability.SET_IP

    def build_body(self, parent):
        # camera_key (vor der Umstellung) -> erfolgreich gesetzte neue IP; wird nach
        # dem Durchlauf ins Hauptfenster übernommen, damit die Liste stimmt.
        self._applied_ips: dict[str, str] = {}
        self._mode = tk.StringVar(value="dhcp")
        self.mask = tk.StringVar(value="255.255.255.0")
        self.gateway = tk.StringVar()
        self.start_ip = tk.StringVar()
        self._ip_vars: dict[str, tk.StringVar] = {}   # camera_key -> entry var

        modes = ttk.Frame(parent)
        modes.pack(fill=tk.X)
        for val, text in (("dhcp", "Auf DHCP umstellen"),
                          ("range", "Feste IP fortlaufend ab Start-IP"),
                          ("each", "Pro Kamera einzeln")):
            ttk.Radiobutton(modes, text=text, value=val, variable=self._mode,
                            command=self._update_visibility).pack(anchor=tk.W)

        self._dynamic = ttk.Frame(parent)
        self._dynamic.pack(fill=tk.BOTH, expand=True, pady=6)

        # shared mask/gateway (range + each)
        self._shared = ttk.Frame(self._dynamic)
        ttk.Label(self._shared, text="Subnetzmaske:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self._shared, textvariable=self.mask, width=18).grid(
            row=0, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(self._shared, text="Gateway (optional):").grid(
            row=0, column=2, sticky=tk.W, padx=4, pady=2)
        ttk.Entry(self._shared, textvariable=self.gateway, width=18).grid(
            row=0, column=3, sticky=tk.W, padx=4, pady=2)

        # range: start IP
        self._rangef = ttk.Frame(self._dynamic)
        ttk.Label(self._rangef, text="Start-IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self._rangef, textvariable=self.start_ip, width=18).grid(
            row=0, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(self._rangef,
                  text="(wird fortlaufend in Tabellenreihenfolge vergeben)").grid(
            row=0, column=2, columnspan=2, sticky=tk.W, padx=4)

        # each: one IP entry per camera
        self._eachf = ttk.Frame(self._dynamic)
        for idx, cam in enumerate(self.cameras):
            current = get_first_ip(cam)
            var = tk.StringVar(value=current)
            self._ip_vars[camera_key(cam)] = var
            ttk.Label(self._eachf, text=f"{cam.get('Name', '?')} ({current or '—'}):").grid(
                row=idx, column=0, sticky=tk.W, padx=4, pady=1)
            ttk.Entry(self._eachf, textvariable=var, width=18).grid(
                row=idx, column=1, sticky=tk.W, padx=4, pady=1)

        ttk.Button(parent, text="Anwenden", command=self._apply).pack(anchor=tk.W)
        self._update_visibility()

    def _update_visibility(self):
        for f in (self._shared, self._rangef, self._eachf):
            f.pack_forget()
        mode = self._mode.get()
        if mode == "range":
            self._shared.pack(fill=tk.X)
            self._rangef.pack(fill=tk.X, pady=(6, 0))
        elif mode == "each":
            self._shared.pack(fill=tk.X)
            self._eachf.pack(fill=tk.X, pady=(6, 0))
        # dhcp: nothing extra

    # ------------------------------------------------------------------- apply
    def _apply(self):
        mode = self._mode.get()
        if mode == "dhcp":
            self.run_per_camera(
                lambda plugin, camera, creds: (plugin.set_dhcp(camera, creds)
                                               or "auf DHCP umgestellt"),
                done_msg="DHCP-Umstellung abgeschlossen.")
            return

        # Static: compute + validate target IPs up front.
        mask = self.mask.get().strip()
        gateway = self.gateway.get().strip()
        if not mask:
            messagebox.showinfo(self.title_text, "Bitte eine Subnetzmaske angeben.", parent=self)
            return

        targets: dict[str, str] = {}
        try:
            if mode == "range":
                start = self.start_ip.get().strip()
                if not start:
                    messagebox.showinfo(self.title_text, "Bitte eine Start-IP angeben.", parent=self)
                    return
                ip = next_ip(start, 0)   # validiert die Start-IP
                for cam in self.cameras:
                    # Netz-/Broadcast-Adressen (.0/.255 im üblichen /24) niemals
                    # vergeben — eine Kamera auf x.y.z.255 wäre unerreichbar.
                    while ip.rsplit(".", 1)[1] in ("0", "255"):
                        ip = next_ip(ip)
                    targets[camera_key(cam)] = ip
                    ip = next_ip(ip)
            else:  # each
                for cam in self.cameras:
                    key = camera_key(cam)
                    ip = self._ip_vars[key].get().strip()
                    if not ip:
                        raise ValueError(f"{cam.get('Name', '?')}: keine IP angegeben")
                    next_ip(ip, 0)   # validate format (raises on bad input)
                    targets[key] = ip
        except ValueError as exc:
            messagebox.showerror(self.title_text, f"Ungültige Eingabe: {exc}", parent=self)
            return

        # Confirm, since changing IPs may drop the current connection.
        if not messagebox.askyesno(
                self.title_text,
                f"{len(targets)} Kamera(s) auf feste IP umstellen?\n"
                "Die Kameras sind danach ggf. unter neuer Adresse erreichbar.",
                parent=self):
            return

        def op(plugin, camera, creds):
            key = camera_key(camera)
            new_ip = targets[key]
            plugin.set_static_ip(camera, creds, new_ip, mask, gateway)
            self._applied_ips[key] = new_ip   # nur bei Erfolg (sonst raise davor)
            return f"feste IP {new_ip} gesetzt"

        self.run_per_camera(op, done_msg="IP-Umstellung abgeschlossen.")

    def _on_done(self):
        """Erfolgreich gesetzte feste IPs in die Kameraliste des Hauptfensters
        übernehmen. (DHCP wird nicht übernommen — die neue Adresse vergibt der
        DHCP-Server und ist hier nicht bekannt.)"""
        if not self._applied_ips:
            return
        apply = getattr(self.master, "apply_ip_changes", None)
        if callable(apply):
            apply(dict(self._applied_ips))
        self._applied_ips.clear()
