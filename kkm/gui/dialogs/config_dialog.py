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

- **Import**: pick a ``.cfg``, choose what of it to take over, and apply that to *all*
  selected cameras (parameters via ``param.cgi`` + stream profiles + VMD4
  motion-detection config via the VMD4 app API), each outcome logged.
- **Export**: read the configuration of the *first* selected camera, choose what to
  keep, and save a ``.cfg``.

Both directions share :class:`ConfigSelectDialog` — the same list of parameters, stream
profiles and motion detection, defaulted to everything the configuration contains. A
``.cfg`` is rarely wanted wholesale: it carries the source camera's IP, hostname and
users along with the picture settings, so importing all of it onto a fleet is usually
not what one means.

All vendor work goes through the camera's :class:`~kkm.core.VendorPlugin`
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

from kkm.core import Capability, t
from kkm.core import get_first_ip
from .base import ActionDialog
from .vault_access import ensure_vault_unlocked


class ConfigDialog(ActionDialog):
    title_text = "Konfiguration (Axis .cfg Import/Export)"
    capability = Capability.CONFIG

    def build_body(self, parent):
        self._cfg_path = tk.StringVar()
        self._read_q: queue.Queue = queue.Queue()

        # --- Import ---
        imp = ttk.LabelFrame(parent, text=t("Importieren (auf alle ausgewählten Kameras)"),
                             padding=8)
        imp.pack(fill=tk.X, pady=(0, 6))
        row = ttk.Frame(imp)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self._cfg_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=t("Datei…"), command=self._choose_cfg).pack(side=tk.LEFT, padx=4)
        self._cfg_info = ttk.Label(imp, text=t("Keine Datei gewählt."))
        self._cfg_info.pack(anchor=tk.W, pady=(4, 0))
        ttk.Button(imp, text=t("Importieren"), command=self._do_import).pack(
            anchor=tk.W, pady=(6, 0))

        # --- Export ---
        exp = ttk.LabelFrame(parent, text=t("Exportieren (von der ersten ausgewählten Kamera)"),
                             padding=8)
        exp.pack(fill=tk.X)
        ttk.Label(
            exp,
            text=t("Liest die Konfiguration aus und speichert ausgewählte Parameter als .cfg."),
        ).pack(anchor=tk.W)
        ttk.Button(exp, text=t("Konfiguration auslesen…"), command=self._do_export_read).pack(
            anchor=tk.W, pady=(6, 0))

        # Werkseinstellungen sind eine eigenständige Aktion im Rechtsklickmenü
        # (FactoryResetDialog) — sie hingen früher hier, waren so aber nur für Axis
        # (einziges Plugin mit CONFIG) erreichbar.

        self.after(120, self._check_read)

    # ----------------------------------------------------------------- import
    def _choose_cfg(self):
        path = filedialog.askopenfilename(
            parent=self, title=t("ADM-Konfiguration wählen"),
            filetypes=[(t("Axis ADM-Konfiguration"), "*.cfg"), (t("Alle Dateien"), "*.*")])
        if not path:
            return
        self._cfg_path.set(path)
        try:
            cfg = self.plugin0().parse_config_file(path)
            info = t("Modell: {model} · Firmware: {fw} · {np} Parameter · {ns} Stream-Profile",
                     model=cfg.get('model') or '?', fw=cfg.get('firmware') or '?',
                     np=len(cfg.get('parameters', {})), ns=len(cfg.get('profiles', [])))
            if cfg.get("vmd4") is not None:
                info += " · " + t("Bewegungserkennung (VMD4)")
            self._cfg_info.config(text=info)
        except Exception as exc:  # noqa: BLE001 - Dateifehler des Plugins anzeigen
            self._cfg_info.config(text=t("Ungültig: {err}", err=exc))
            self._cfg_path.set("")

    def _do_import(self):
        path = self._cfg_path.get().strip()
        if not path:
            messagebox.showinfo(t(self.title_text), t("Bitte zuerst eine .cfg-Datei wählen."), parent=self)
            return
        try:
            # Einmal vorab lesen: validiert die Datei und liefert zugleich, was
            # drinsteht — daraus baut sich die Auswahl unten auf.
            config = self.plugin0().parse_config_file(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(t(self.title_text), str(exc), parent=self)
            return

        dlg = ConfigSelectDialog(
            self, config, title=t("Einstellungen für den Import auswählen"),
            ok_text=t("Importieren"), verb=t("importieren"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        params, profiles, with_vmd4 = dlg.result
        if not params and not profiles and not with_vmd4:
            messagebox.showinfo(t(self.title_text),
                                t("Nichts ausgewählt — es gibt nichts zu importieren."),
                                parent=self)
            return

        vmd_note = (" + " + t("Bewegungserkennung")) if with_vmd4 and config.get("vmd4") else ""
        if not messagebox.askyesno(
                t(self.title_text),
                t("{np} Parameter, {ns} Stream-Profil(e){vmd} auf {nc} Kamera(s) anwenden?",
                  np=len(params), ns=len(profiles), vmd=vmd_note, nc=len(self.cameras)), parent=self):
            return

        def op(plugin, camera, creds):
            res = plugin.import_config(camera, creds, path, selected_params=params,
                                       selected_profiles=profiles, with_vmd4=with_vmd4)
            if isinstance(res, int):
                return t("angewendet ({n} Parameter)", n=res)
            return str(res) if res else t("angewendet")

        self.run_per_camera(op, done_msg=t("Import abgeschlossen."))

    # ----------------------------------------------------------------- export
    def _do_export_read(self):
        if self._busy:
            return
        camera = self.cameras[0]
        plugin = self.plugin_for(camera)
        if plugin is None:
            messagebox.showerror(t(self.title_text), t("Kein Plugin für diese Kamera."), parent=self)
            return
        # Zugangsdaten aus dem Tresor gewünscht, aber gesperrt -> anbieten zu
        # entsperren, damit das Passwort fürs Auslesen zur Verfügung steht.
        if self.use_vault_var.get() and self.vault is not None and self.vault.is_locked:
            ensure_vault_unlocked(self, self.vault,
                                  t("Zum Verwenden der gespeicherten Passwörter"))
        self._busy = True
        self.progress.start(12)
        self._log_clear()
        self._log_line(t("Lese Konfiguration von {name} ({ip}) …",
                         name=camera.get('Name', '?'), ip=get_first_ip(camera)))
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
                self._log_line("✗ " + t("Auslesen fehlgeschlagen: {err}", err=payload))
            else:
                vmd_note = (" + " + t("Bewegungserkennung (VMD4)")) if payload.get("vmd4") else ""
                self._log_line(
                    "✓ " + t("Ausgelesen: {n} Parameter", n=len(payload.get('parameters', {})))
                    + vmd_note)
                self._open_param_select(payload)
        except queue.Empty:
            pass
        self.after(120, self._check_read)

    def _open_param_select(self, config: dict):
        dlg = ConfigSelectDialog(self, config,
                                 title=t("Einstellungen für den Export auswählen"),
                                 ok_text=t("Speichern…"), verb=t("exportieren"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        selected, profiles, with_vmd4 = dlg.result
        path = filedialog.asksaveasfilename(
            parent=self, title=t("Als ADM-Konfiguration speichern"),
            defaultextension=".cfg",
            filetypes=[(t("Axis ADM-Konfiguration"), "*.cfg")])
        if not path:
            return
        try:
            self.plugin0().write_config_file(path, config, selected_params=selected,
                                             with_profiles=bool(profiles),
                                             selected_profiles=profiles,
                                             with_vmd4=with_vmd4)
            extra = (" + " + t("Bewegungserkennung")) if with_vmd4 and config.get("vmd4") else ""
            self._log_line(
                "✓ " + t("Gespeichert: {path} ({np} Parameter, {ns} Profil(e){extra})",
                         path=path, np=len(selected), ns=len(profiles), extra=extra))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(t(self.title_text), t("Speichern fehlgeschlagen: {err}", err=exc), parent=self)


class ConfigSelectDialog(tk.Toplevel):
    """Auswahl dessen, was aus einer Konfiguration übernommen wird — für **beide**
    Richtungen: beim Export (was in die ``.cfg`` geschrieben wird) und beim Import
    (was aus der ``.cfg`` auf die Kameras geht).

    Angeboten wird dasselbe, was eine ``.cfg`` enthält: die einzelnen Parameter
    (durchsuchbare Liste), die Stream-Profile (einzeln) und die Bewegungserkennung
    (VMD4). Voreingestellt ist alles, was vorhanden ist — abwählen ist der bewusste
    Schritt.

    Die Auswahl liegt in Mengen (``_selected`` / ``_sel_profiles``) unabhängig von den
    sichtbaren Zeilen, damit das Filtern kein Häkchen verliert.

    ``result`` ist ``(parameter, profile, vmd4)`` oder ``None`` bei Abbruch.
    """

    def __init__(self, parent, config: dict, *, title="Einstellungen auswählen",
                 ok_text="Übernehmen", verb="übernehmen"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.result = None

        params = config.get("parameters", {})
        self._values = params
        self._all = sorted(params.keys())
        self._selected: set[str] = set(self._all)          # Voreinstellung: alles

        profiles = config.get("profiles", []) or []
        self._profiles = [p.get("name", "") for p in profiles if p.get("name")]
        self._prof_desc = {p.get("name", ""): (p.get("description") or "")
                           for p in profiles}
        self._sel_profiles: set[str] = set(self._profiles)

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        model = config.get("model") or "?"
        firmware = config.get("firmware") or "?"
        ttk.Label(outer, text=t("Quelle: {model} · Firmware {fw}", model=model, fw=firmware)).pack(anchor=tk.W)

        # --- Parameter ---
        top = ttk.Frame(outer)
        top.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(top, text=t("Filter:")).pack(side=tk.LEFT)
        self._filter = tk.StringVar()
        self._filter.trace_add("write", lambda *_: self._refresh())
        ttk.Entry(top, textvariable=self._filter, width=30).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text=t("Alle"), command=self._select_all).pack(side=tk.RIGHT)
        ttk.Button(top, text=t("Keine"), command=self._select_none).pack(side=tk.RIGHT, padx=4)
        self._only_selected = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text=t("Nur Ausgewählte anzeigen"),
                        variable=self._only_selected,
                        command=self._refresh).pack(side=tk.RIGHT, padx=4)

        self.tree = ttk.Treeview(outer, columns=("value",), show="tree headings",
                                 selectmode="none", height=14)
        self.tree.heading("#0", text=t("Parameter"))
        self.tree.heading("value", text=t("Wert"))
        self.tree.column("#0", width=380)
        self.tree.column("value", width=240)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.tree.bind("<Button-1>", self._toggle)

        # --- Stream-Profile (einzeln an-/abwählbar) ---
        prof_frame = ttk.LabelFrame(outer, text=t("Stream-Profile ({verb})", verb=verb), padding=6)
        prof_frame.pack(fill=tk.X)
        if self._profiles:
            self.prof_tree = ttk.Treeview(prof_frame, columns=("desc",),
                                          show="tree headings", selectmode="none",
                                          height=min(4, len(self._profiles)))
            self.prof_tree.heading("#0", text=t("Profil"))
            self.prof_tree.heading("desc", text=t("Beschreibung"))
            self.prof_tree.column("#0", width=200)
            self.prof_tree.column("desc", width=380)
            self.prof_tree.pack(fill=tk.X)
            self.prof_tree.bind("<Button-1>", self._toggle_profile)
            self._refresh_profiles()
        else:
            self.prof_tree = None
            ttk.Label(prof_frame, text=t("Keine Stream-Profile enthalten.")).pack(anchor=tk.W)

        # --- Bewegungserkennung (VMD4) — nur, wenn die Konfiguration eine enthält ---
        has_vmd4 = config.get("vmd4") is not None
        self._with_vmd4 = tk.BooleanVar(value=has_vmd4)
        vmd4_chk = ttk.Checkbutton(
            outer, text=t("Bewegungserkennung (VMD4) {verb}", verb=verb), variable=self._with_vmd4)
        vmd4_chk.pack(anchor=tk.W, pady=(6, 0))
        if not has_vmd4:
            vmd4_chk.state(["disabled"])
            ttk.Label(outer, text=t("(keine Bewegungserkennung enthalten)")).pack(anchor=tk.W)

        self._count_lbl = ttk.Label(outer)
        self._count_lbl.pack(anchor=tk.W, pady=(6, 0))

        btns = ttk.Frame(outer)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text=ok_text, command=self._ok).pack(side=tk.RIGHT)
        ttk.Button(btns, text=t("Abbrechen"), command=self.destroy).pack(side=tk.RIGHT, padx=6)

        self._refresh()

    # ------------------------------------------------------------------ Parameter
    def _update_count(self):
        text = t("Ausgewählt: {n} von {total} Parametern",
                 n=len(self._selected), total=len(self._all))
        if self._profiles:
            text += t(" · {n} von {total} Stream-Profilen",
                      n=len(self._sel_profiles), total=len(self._profiles))
        self._count_lbl.config(text=text)

    @staticmethod
    def _box(selected: bool) -> str:
        return "☑" if selected else "☐"

    def _refresh(self):
        flt = self._filter.get().lower()
        only_sel = self._only_selected.get()
        self.tree.delete(*self.tree.get_children())
        for name in self._all:
            if flt and flt not in name.lower():
                continue
            if only_sel and name not in self._selected:
                continue
            self.tree.insert("", "end", iid=name,
                             text=f"{self._box(name in self._selected)}  {name}",
                             values=(self._values.get(name, ""),))
        self._update_count()

    def _toggle(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row in self._selected:
            self._selected.discard(row)
        else:
            self._selected.add(row)
        if self._only_selected.get():
            # In der Ansicht "Nur Ausgewählte" abgewählte Zeilen sofort ausblenden.
            self._refresh()
        else:
            self.tree.item(row, text=f"{self._box(row in self._selected)}  {row}")
            self._update_count()

    def _select_all(self):
        self._selected = set(self._all)
        self._refresh()

    def _select_none(self):
        self._selected.clear()
        self._refresh()

    # -------------------------------------------------------------------- Profile
    def _refresh_profiles(self):
        self.prof_tree.delete(*self.prof_tree.get_children())
        for name in self._profiles:
            self.prof_tree.insert(
                "", "end", iid=name,
                text=f"{self._box(name in self._sel_profiles)}  {name}",
                values=(self._prof_desc.get(name, ""),))

    def _toggle_profile(self, event):
        row = self.prof_tree.identify_row(event.y)
        if not row:
            return
        if row in self._sel_profiles:
            self._sel_profiles.discard(row)
        else:
            self._sel_profiles.add(row)
        self.prof_tree.item(
            row, text=f"{self._box(row in self._sel_profiles)}  {row}")
        self._update_count()

    def _ok(self):
        self.result = (sorted(self._selected), sorted(self._sel_profiles),
                       self._with_vmd4.get())
        self.destroy()
