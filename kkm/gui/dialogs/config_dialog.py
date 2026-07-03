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

"""Configuration action: import/export Axis ADM ``.cfg`` (format v1 + v2).

Two operations, both on the cameras selected in the main table:

- **Import**: pick a ``.cfg`` and apply it to *all* selected cameras (parameters
  via ``param.cgi`` + stream profiles), each outcome logged. The file is parsed
  once up front to validate it and show its model/firmware before applying.
- **Export**: read the configuration of the *first* selected camera, let the user
  pick which parameters to keep (searchable checkbox list), and save a ``.cfg``.

All vendor work goes through :class:`kkm.plugins.axis.plugin.AxisPlugin`
(``import_config`` / ``read_config`` / ``export_config``), which wraps the copied
VAPIX functions ``parse_adm_config`` / ``apply_adm_config`` / ``read_device_config``
/ ``write_adm_config``.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from kkm.gui import filedialogs as filedialog   # feste Dialoggröße

from kkm.core import Capability, camera_key
from kkm.plugins.axis.discovery import get_first_ip
from kkm.plugins.axis import vapix
from .base import ActionDialog
from .vault_access import ensure_vault_unlocked


class ConfigDialog(ActionDialog):
    title_text = "Konfiguration (Axis .cfg Import/Export)"
    capability = Capability.CONFIG

    def build_body(self, parent):
        self._cfg_path = tk.StringVar()
        self._read_q: queue.Queue = queue.Queue()

        # --- Import ---
        imp = ttk.LabelFrame(parent, text="Importieren (auf alle ausgewählten Kameras)",
                             padding=8)
        imp.pack(fill=tk.X, pady=(0, 6))
        row = ttk.Frame(imp)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self._cfg_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Datei…", command=self._choose_cfg).pack(side=tk.LEFT, padx=4)
        self._cfg_info = ttk.Label(imp, text="Keine Datei gewählt.")
        self._cfg_info.pack(anchor=tk.W, pady=(4, 0))
        ttk.Button(imp, text="Importieren", command=self._do_import).pack(
            anchor=tk.W, pady=(6, 0))

        # --- Export ---
        exp = ttk.LabelFrame(parent, text="Exportieren (von der ersten ausgewählten Kamera)",
                             padding=8)
        exp.pack(fill=tk.X)
        ttk.Label(
            exp,
            text="Liest die Konfiguration aus und speichert ausgewählte Parameter als .cfg.",
        ).pack(anchor=tk.W)
        ttk.Button(exp, text="Konfiguration auslesen…", command=self._do_export_read).pack(
            anchor=tk.W, pady=(6, 0))

        # --- Werkseinstellungen (Reset) — nur wenn das Plugin es unterstützt ---
        plugin0 = self.plugin_for(self.cameras[0]) if self.cameras else None
        if plugin0 and plugin0.supports(Capability.FACTORY_RESET):
            # camera_keys der zurückgesetzten Kameras: alle (Zugangsdaten ungültig
            # -> aufräumen) bzw. bestätigt werksneu (-> in der Liste kennzeichnen).
            self._reset_all_keys: list[str] = []
            self._reset_factory_keys: list[str] = []
            self._reset_mode = tk.StringVar(value="keep")
            rst = ttk.LabelFrame(
                parent, text="Werkseinstellungen (auf alle ausgewählten Kameras)",
                padding=8)
            rst.pack(fill=tk.X, pady=(6, 0))
            ttk.Label(rst, text="Setzt die Kamera(s) zurück; sie starten danach neu.").pack(
                anchor=tk.W)
            ttk.Radiobutton(rst, text="Werksreset mit Erhalt der IP-Adresse",
                            value="keep", variable=self._reset_mode).pack(anchor=tk.W)
            ttk.Radiobutton(rst, text="Kompletter Werksreset (inkl. IP-Adresse)",
                            value="full", variable=self._reset_mode).pack(anchor=tk.W)
            ttk.Button(rst, text="Auf Werkseinstellungen zurücksetzen",
                       command=self._do_factory_reset).pack(anchor=tk.W, pady=(6, 0))

        self.after(120, self._check_read)

    # ------------------------------------------------------------- factory reset
    def _do_factory_reset(self):
        keep_ip = self._reset_mode.get() == "keep"
        mode = ("mit Erhalt der IP-Adresse" if keep_ip
                else "inkl. IP-Adresse — kompletter Reset")
        if not messagebox.askyesno(
                self.title_text,
                f"{len(self.cameras)} Kamera(s) auf Werkseinstellungen zurücksetzen "
                f"({mode})?\n\nDie Kameras starten danach neu. Diese Aktion kann "
                "nicht rückgängig gemacht werden.", parent=self):
            return
        self._reset_all_keys.clear()
        self._reset_factory_keys.clear()

        def op(plugin, camera, creds):
            key = camera_key(camera)
            plugin.factory_reset(camera, creds, keep_ip=keep_ip)   # löst Reset aus
            self._reset_all_keys.append(key)   # Zugangsdaten sind jetzt ungültig
            if not keep_ip:
                # IP ändert sich -> nicht am alten Ziel pollbar. Nur Hinweis.
                return ("Reset ausgelöst — Kamera startet neu und ist danach unter "
                        "Standard-/DHCP-Adresse erreichbar (bitte neu suchen).")
            # keep_ip: warten, bis die Kamera neu gestartet und wieder erreichbar
            # UND im Werkszustand (Erstkonfiguration) ist.
            if self._wait_until_factory(plugin, camera, creds):
                self._reset_factory_keys.append(key)
                return ("Werksreset erfolgreich — Kamera wieder erreichbar, "
                        "Erstkonfiguration erforderlich.")
            return ("Reset ausgelöst, aber Kamera kam im Zeitfenster nicht "
                    "erreichbar/werksneu zurück — später erneut suchen.")

        self.run_per_camera(op, done_msg="Werksreset abgeschlossen.")

    def _wait_until_factory(self, plugin, camera, creds,
                            timeout=180, interval=5) -> bool:
        """Pollt (im Worker-Thread) die Kamera, bis sie nach dem Neustart wieder
        antwortet und sich im Auslieferungszustand befindet. Gibt True zurück,
        sobald der Werkszustand bestätigt ist."""
        name = camera.get("Name", "?")
        ip = get_first_ip(camera) or "?"
        msg = f"… {name} ({ip}): warte auf Neustart und Erstkonfigurationsmodus…"
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

    # ----------------------------------------------------------------- import
    def _choose_cfg(self):
        path = filedialog.askopenfilename(
            parent=self, title="ADM-Konfiguration wählen",
            filetypes=[("Axis ADM-Konfiguration", "*.cfg"), ("Alle Dateien", "*.*")])
        if not path:
            return
        self._cfg_path.set(path)
        try:
            cfg = vapix.parse_adm_config(path)
            self._cfg_info.config(
                text=f"Modell: {cfg.get('model') or '?'} · "
                     f"Firmware: {cfg.get('firmware') or '?'} · "
                     f"{len(cfg.get('parameters', {}))} Parameter · "
                     f"{len(cfg.get('profiles', []))} Stream-Profile")
        except vapix.VapixError as exc:
            self._cfg_info.config(text=f"Ungültig: {exc}")
            self._cfg_path.set("")

    def _do_import(self):
        path = self._cfg_path.get().strip()
        if not path:
            messagebox.showinfo(self.title_text, "Bitte zuerst eine .cfg-Datei wählen.")
            return
        try:
            vapix.parse_adm_config(path)   # validate once before touching cameras
        except vapix.VapixError as exc:
            messagebox.showerror(self.title_text, str(exc))
            return

        def op(plugin, camera, creds):
            n = plugin.import_config(camera, creds, path)
            return f"angewendet ({n} Parameter)" if isinstance(n, int) else "angewendet"

        self.run_per_camera(op, done_msg="Import abgeschlossen.")

    # ----------------------------------------------------------------- export
    def _do_export_read(self):
        if self._busy:
            return
        camera = self.cameras[0]
        plugin = self.plugin_for(camera)
        if plugin is None:
            messagebox.showerror(self.title_text, "Kein Plugin für diese Kamera.")
            return
        # Zugangsdaten aus dem Tresor gewünscht, aber gesperrt -> anbieten zu
        # entsperren, damit das Passwort fürs Auslesen zur Verfügung steht.
        if self.use_vault_var.get() and self.vault is not None and self.vault.is_locked:
            ensure_vault_unlocked(self, self.vault,
                                  "Zum Verwenden der gespeicherten Passwörter")
        self._busy = True
        self.progress.start(12)
        self._log_clear()
        self._log_line(f"Lese Konfiguration von {camera.get('Name','?')} "
                       f"({get_first_ip(camera)}) …")
        creds = self.creds_for(camera)
        threading.Thread(target=self._worker_read, args=(plugin, camera, creds),
                         daemon=True).start()

    def _worker_read(self, plugin, camera, creds):
        try:
            cfg = plugin.read_config(camera, creds)
            self._read_q.put(("ok", cfg))
        except Exception as exc:  # noqa: BLE001 - surfaced on the main thread
            self._read_q.put(("err", str(exc)))

    def _check_read(self):
        try:
            kind, payload = self._read_q.get_nowait()
            self.progress.stop()
            self._busy = False
            if kind == "err":
                self._log_line(f"✗ Auslesen fehlgeschlagen: {payload}")
            else:
                self._log_line(f"✓ Ausgelesen: {len(payload.get('parameters', {}))} Parameter")
                self._open_param_select(payload)
        except queue.Empty:
            pass
        self.after(120, self._check_read)

    def _open_param_select(self, config: dict):
        dlg = ParameterSelectDialog(self, config)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        selected, with_profiles = dlg.result
        path = filedialog.asksaveasfilename(
            parent=self, title="Als ADM-Konfiguration speichern",
            defaultextension=".cfg",
            filetypes=[("Axis ADM-Konfiguration", "*.cfg")])
        if not path:
            return
        try:
            vapix.write_adm_config(path, config, selected_params=selected,
                                   with_profiles=with_profiles)
            self._log_line(f"✓ Gespeichert: {path} ({len(selected)} Parameter)")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.title_text, f"Speichern fehlgeschlagen: {exc}")


class ParameterSelectDialog(tk.Toplevel):
    """Searchable checkbox list of parameters to include in an export.

    Selection state is kept in ``self._selected`` (a set) independently of the
    visible rows, so filtering never loses checked items — same approach as the
    Discovery tool.
    """

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.title("Parameter auswählen")
        self.transient(parent)
        self.grab_set()
        self.result = None

        params = config.get("parameters", {})
        self._all = sorted(params.keys())
        self._selected: set[str] = set(self._all)   # default: everything

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(outer)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Filter:").pack(side=tk.LEFT)
        self._filter = tk.StringVar()
        self._filter.trace_add("write", lambda *_: self._refresh())
        ttk.Entry(top, textvariable=self._filter, width=30).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Alle", command=self._select_all).pack(side=tk.RIGHT)
        ttk.Button(top, text="Keine", command=self._select_none).pack(side=tk.RIGHT, padx=4)

        self.tree = ttk.Treeview(outer, columns=("value",), show="tree headings",
                                 selectmode="none", height=16)
        self.tree.heading("#0", text="Parameter")
        self.tree.heading("value", text="Wert")
        self.tree.column("#0", width=380)
        self.tree.column("value", width=240)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.tree.bind("<Button-1>", self._toggle)
        self._values = params

        self._with_profiles = tk.BooleanVar(value=bool(config.get("profiles")))
        ttk.Checkbutton(outer, text="Stream-Profile mit exportieren",
                        variable=self._with_profiles).pack(anchor=tk.W)

        btns = ttk.Frame(outer)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Speichern…", command=self._ok).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT, padx=6)

        self._refresh()

    def _checkbox(self, name: str) -> str:
        return "☑" if name in self._selected else "☐"

    def _refresh(self):
        flt = self._filter.get().lower()
        self.tree.delete(*self.tree.get_children())
        for name in self._all:
            if flt and flt not in name.lower():
                continue
            self.tree.insert("", "end", iid=name,
                             text=f"{self._checkbox(name)}  {name}",
                             values=(self._values.get(name, ""),))

    def _toggle(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row in self._selected:
            self._selected.discard(row)
        else:
            self._selected.add(row)
        self.tree.item(row, text=f"{self._checkbox(row)}  {row}")

    def _select_all(self):
        self._selected = set(self._all)
        self._refresh()

    def _select_none(self):
        self._selected.clear()
        self._refresh()

    def _ok(self):
        self.result = (sorted(self._selected), self._with_profiles.get())
        self.destroy()
