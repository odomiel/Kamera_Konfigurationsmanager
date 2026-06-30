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

"""Main window — group tree + device table + front-view action toolbar.

Layout mirrors the Axis Device Manager *grob*: a left group panel, a right device
table, and a toolbar whose buttons are the former "Kameraeinstellungen" tabs, now
each a first-class action. Long-running work (LAN scan, online checks, camera
writes) runs in background threads and reports back through a ``queue.Queue``
polled with ``after()`` so the UI never freezes (same pattern as the Discovery
tool).

This is the scaffold: the shell, threading, group/table wiring and online check
are functional. The per-action dialogs (IP/Users/ONVIF/Firmware/Config) are
stubbed with TODO markers — they will reuse the plugin methods in
:class:`kkm.plugins.axis.plugin.AxisPlugin`.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from kkm.version import APP_NAME, __version__
from kkm.core import (Credentials, Capability, GroupStore, ALL_CAMERAS_ID,
                      camera_key, PasswordVault, AppSettings)
from kkm.core.groups import config_dir
from kkm.plugins import build_registry
from kkm.plugins.axis.discovery import FIELD_NAMES, get_first_ip, export_results
from kkm.gui.dialogs import ACTION_DIALOGS
from kkm.gui.dialogs.settings_dialog import SettingsDialog

ONLINE_COL = "● Status"
GROUP_COL = "Gruppe(n)"
TABLE_COLUMNS = ["Name", "Modell", "IP-Adresse", "MAC/Seriennummer", "Firmware",
                 GROUP_COL, ONLINE_COL]
FIXED_COLUMNS = {"Name"}   # always visible, cannot be hidden


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("1100x650")

        self.store = GroupStore()
        self.settings = AppSettings()
        self.registry = build_registry(self.settings.get("enabled_plugins"))
        self.vault = PasswordVault()
        self.creds = Credentials()
        self._q: queue.Queue = queue.Queue()
        self._current_gid = ALL_CAMERAS_ID
        # rowid (in tree) -> camera dict, for the device table
        self._row_cam: dict[str, dict] = {}
        self._online_job = None   # after() id for the per-group auto online check

        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._refresh_groups()
        self.apply_columns(self.settings.get("hidden_columns", []))
        self._refresh_table()
        self.after(100, self._poll)
        self._schedule_online_autocheck()

    # ------------------------------------------------------------------ UI
    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(bar, text="Suchen", command=self.start_search).pack(side=tk.LEFT)
        ttk.Button(bar, text="Online prüfen", command=self.start_online_check).pack(
            side=tk.LEFT, padx=(6, 0))

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Front-view action buttons = former "Kameraeinstellungen" tabs.
        self._action_buttons: dict[str, ttk.Button] = {}
        actions = [
            ("IP-Adresse", Capability.SET_IP),
            ("Benutzer", Capability.USERS),
            ("ONVIF-Benutzer", Capability.ONVIF_USERS),
            ("Firmware", Capability.FIRMWARE),
            ("Konfiguration", Capability.CONFIG),
        ]
        for label, cap in actions:
            btn = ttk.Button(bar, text=label,
                             command=lambda c=cap, l=label: self._open_action(c, l))
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._action_buttons[cap] = btn

        ttk.Button(bar, text="Hilfe", command=self._open_help).pack(side=tk.RIGHT)
        ttk.Button(bar, text="Einstellungen", command=self._open_settings).pack(
            side=tk.RIGHT, padx=(0, 6))
        ttk.Button(bar, text="Exportieren", command=self._export).pack(
            side=tk.RIGHT, padx=(0, 6))
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=140)
        self.progress.pack(side=tk.RIGHT, padx=8)

    def _build_body(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # --- left: group tree + group controls ---
        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        ttk.Label(left, text="Gerätegruppen", font=("TkDefaultFont", 11, "bold")).pack(
            anchor=tk.W, pady=(0, 4))
        self.group_tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.group_tree.pack(fill=tk.BOTH, expand=True)
        self.group_tree.bind("<<TreeviewSelect>>", self._on_group_select)

        gbtns = ttk.Frame(left)
        gbtns.pack(fill=tk.X, pady=4)
        ttk.Button(gbtns, text="+ Gruppe", command=self._add_group).pack(side=tk.LEFT)
        ttk.Button(gbtns, text="Umbenennen", command=self._rename_group).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(gbtns, text="Löschen", command=self._delete_group).pack(side=tk.LEFT)

        # --- right: device table ---
        right = ttk.Frame(paned)
        paned.add(right, weight=4)
        self.table = ttk.Treeview(right, columns=TABLE_COLUMNS, show="headings",
                                  selectmode="extended")
        for col in TABLE_COLUMNS:
            self.table.heading(col, text=col)
            self.table.column(col, width=160, stretch=True)
        self.table.column(ONLINE_COL, width=90, stretch=False, anchor=tk.CENTER)
        self.table.pack(fill=tk.BOTH, expand=True)
        # Rechtsklick -> Kameras Gruppen zuweisen (additiv) / entfernen.
        self.table.bind("<Button-3>", self._show_table_menu)

    def _build_statusbar(self):
        self.status = ttk.Label(self, text="Bereit", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # -------------------------------------------------------------- groups
    def _refresh_groups(self):
        self.group_tree.delete(*self.group_tree.get_children())
        # "Alle Kameras" always first and non-deletable.
        self.group_tree.insert("", "end", iid=ALL_CAMERAS_ID,
                               text=f"  {self.store.groups[ALL_CAMERAS_ID].name}",
                               open=True)
        for gid, g in self.store.groups.items():
            if gid == ALL_CAMERAS_ID:
                continue
            self.group_tree.insert(ALL_CAMERAS_ID, "end", iid=gid, text=f"  {g.name}")
        if self.group_tree.exists(self._current_gid):
            self.group_tree.selection_set(self._current_gid)

    def _on_group_select(self, _evt=None):
        sel = self.group_tree.selection()
        if sel:
            self._current_gid = sel[0]
            self._refresh_table()
            self._schedule_online_autocheck()

    def _add_group(self):
        name = simpledialog.askstring("Neue Gruppe", "Name der Gruppe:", parent=self)
        if name:
            g = self.store.create_group(name.strip())
            self._current_gid = g.id
            self._refresh_groups()

    def _rename_group(self):
        gid = self._current_gid
        g = self.store.groups.get(gid)
        if not g or not g.deletable:
            messagebox.showinfo(APP_NAME, "Diese Gruppe kann nicht umbenannt werden.")
            return
        name = simpledialog.askstring("Umbenennen", "Neuer Name:", initialvalue=g.name,
                                      parent=self)
        if name:
            self.store.rename_group(gid, name.strip())
            self._refresh_groups()

    def _delete_group(self):
        gid = self._current_gid
        if not self.store.delete_group(gid):
            messagebox.showinfo(APP_NAME, "Diese Gruppe kann nicht gelöscht werden.")
            return
        self._current_gid = ALL_CAMERAS_ID
        self._refresh_groups()
        self._refresh_table()

    # --------------------------------------------------------------- table
    def _refresh_table(self):
        self.table.delete(*self.table.get_children())
        self._row_cam.clear()
        for cam in self.store.cameras_in(self._current_gid):
            key = camera_key(cam)
            online = cam.get("_online")
            badge = "—" if online is None else ("● Online" if online else "○ Offline")
            groups = ", ".join(self.store.groups_of(key)) or "—"
            values = [
                cam.get("Name", ""),
                cam.get("_model", cam.get("Name", "")),
                get_first_ip(cam),
                cam.get("MAC-Adresse/Seriennummer", ""),
                cam.get("_firmware", ""),
                groups,
                badge,
            ]
            rowid = self.table.insert("", "end", iid=key, values=values)
            self._row_cam[rowid] = cam
        g = self.store.groups.get(self._current_gid)
        n = len(self._row_cam)
        self.status.config(text=f"{g.name if g else ''}: {n} Gerät(e)")

    def _selected_cameras(self) -> list[dict]:
        return [self._row_cam[r] for r in self.table.selection() if r in self._row_cam]

    # ------------------------------------------------- camera -> group (Rechtsklick)
    def _show_table_menu(self, event):
        # Rechtsklick auf eine nicht-markierte Zeile wählt sie zuerst aus.
        row = self.table.identify_row(event.y)
        if row and row not in self.table.selection():
            self.table.selection_set(row)
        cams = self._selected_cameras()
        if not cams:
            return
        keys = [camera_key(c) for c in cams]

        menu = tk.Menu(self, tearoff=0)
        add_menu = tk.Menu(menu, tearoff=0)
        user_groups = [(gid, g) for gid, g in self.store.groups.items()
                       if gid != ALL_CAMERAS_ID]
        for gid, g in user_groups:
            add_menu.add_command(label=g.name,
                                 command=lambda gid=gid: self._assign_selected(gid, keys))
        if user_groups:
            add_menu.add_separator()
        add_menu.add_command(label="Neue Gruppe…",
                             command=lambda: self._assign_new_group(keys))
        menu.add_cascade(label=f"Zu Gruppe hinzufügen ({len(cams)} Kamera(s))",
                         menu=add_menu)

        g = self.store.groups.get(self._current_gid)
        if g and self._current_gid != ALL_CAMERAS_ID:
            menu.add_separator()
            menu.add_command(label=f"Aus „{g.name}“ entfernen",
                             command=lambda: self._unassign_selected(self._current_gid, keys))
        menu.add_separator()
        menu.add_command(label=f"Kamera(s) vollständig entfernen ({len(cams)})",
                         command=lambda: self._remove_selected(cams, keys))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _assign_selected(self, gid, keys):
        self.store.assign(gid, keys)
        name = self.store.groups[gid].name
        if self._current_gid == gid:
            self._refresh_table()
        self.status.config(text=f"{len(keys)} Kamera(s) zu „{name}“ hinzugefügt")

    def _assign_new_group(self, keys):
        name = simpledialog.askstring("Neue Gruppe", "Name der Gruppe:", parent=self)
        if not name:
            return
        g = self.store.create_group(name.strip())
        self.store.assign(g.id, keys)
        self._refresh_groups()
        self.status.config(text=f"{len(keys)} Kamera(s) zu neuer Gruppe „{g.name}“ hinzugefügt")

    def _unassign_selected(self, gid, keys):
        self.store.unassign(gid, keys)
        name = self.store.groups[gid].name
        self._refresh_table()   # Ansicht zeigt diese Gruppe -> Zeilen verschwinden
        self.status.config(text=f"{len(keys)} Kamera(s) aus „{name}“ entfernt")

    def _remove_selected(self, cams, keys):
        """Remove cameras entirely: roster, all groups, and vault entry."""
        names = ", ".join(c.get("Name", "?") for c in cams[:5]) + (" …" if len(cams) > 5 else "")
        if not messagebox.askyesno(
                APP_NAME,
                f"{len(keys)} Kamera(s) vollständig entfernen?\n\n{names}\n\n"
                "Sie werden aus allen Gruppen und der Geräteliste entfernt; ein "
                "gespeichertes Passwort wird (bei entsperrtem Tresor) ebenfalls gelöscht. "
                "Bei der nächsten Suche tauchen erreichbare Kameras wieder auf.",
                parent=self):
            return
        for key in keys:
            self.store.forget(key)
            if self.vault and not self.vault.is_locked:
                self.vault.delete(key)
        self._refresh_table()
        self.status.config(text=f"{len(keys)} Kamera(s) vollständig entfernt")

    # -------------------------------------------------------------- search
    def start_search(self):
        self.progress.start(12)
        self.status.config(text="Suche läuft…")
        threading.Thread(target=self._worker_search, daemon=True).start()

    def _worker_search(self):
        found: list[dict] = []
        try:
            for plugin in self.registry.enabled():
                if plugin.supports(Capability.DISCOVER):
                    found.extend(plugin.discover(timeout=self.creds.timeout))
            self._q.put(("search_done", found))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self._q.put(("error", f"Suche fehlgeschlagen: {exc}"))

    def start_online_check(self):
        cams = self._selected_cameras() or self.store.cameras_in(self._current_gid)
        if not cams:
            return
        self.progress.start(12)
        self.status.config(text="Prüfe Online-Status…")
        threading.Thread(target=self._worker_online, args=(cams,), daemon=True).start()

    def _worker_online(self, cams):
        for cam in cams:
            vendor = self.registry.get(cam.get("_vendor", "axis"))
            ok = bool(vendor and vendor.check_online(cam, self.creds))
            self._q.put(("online", (camera_key(cam), ok)))
        self._q.put(("online_done", None))

    # ---------------------------------------------------------------- queue
    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "search_done":
                    self.store.remember_all(payload)
                    self.progress.stop()
                    self._refresh_table()
                    self.status.config(text=f"Suche fertig: {len(payload)} Gerät(e)")
                elif kind == "online":
                    key, ok = payload
                    if key in self.store.roster:
                        self.store.roster[key]["_online"] = ok
                elif kind == "online_done":
                    self.progress.stop()
                    self._refresh_table()
                elif kind == "error":
                    self.progress.stop()
                    messagebox.showerror(APP_NAME, payload)
        except queue.Empty:
            pass
        self.after(150, self._poll)

    # -------------------------------------------------------------- actions
    def _open_action(self, capability: str, label: str):
        cams = self._selected_cameras()
        if not cams:
            messagebox.showinfo(APP_NAME, "Bitte zuerst Kameras in der Tabelle auswählen.")
            return
        dialog_cls = ACTION_DIALOGS.get(capability)
        if dialog_cls is None:
            messagebox.showinfo(
                APP_NAME,
                f"Aktion „{label}“ folgt — die Plugin-Logik (VAPIX) ist vorhanden, "
                "der Dialog ist noch nicht gebaut.")
            return
        dialog_cls(self, cams, self.registry, vault=getattr(self, "vault", None))

    def _export(self):
        cams = self.store.cameras_in(self._current_gid)
        if not cams:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt")])
        if path:
            export_results(cams, path, columns=FIELD_NAMES)
            self.status.config(text=f"Exportiert nach {path}")

    def _open_help(self):
        import sys
        from pathlib import Path
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", "."))
        else:
            base = Path(__file__).resolve().parents[2]   # <root>/ bzw. AppImage app/
        path = base / "HILFE.md"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = "Hilfedatei (HILFE.md) nicht gefunden."

        win = tk.Toplevel(self)
        win.title("Hilfe")
        win.geometry("720x600")
        win.transient(self)
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(frame, wrap=tk.WORD, yscrollcommand=scroll.set,
                      padx=8, pady=8)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=txt.yview)
        txt.insert("1.0", text)
        txt.config(state=tk.DISABLED)
        ttk.Button(win, text="Schließen", command=win.destroy).pack(
            anchor=tk.E, padx=8, pady=(0, 8))

    def _open_settings(self):
        dlg = SettingsDialog(
            self, vault=self.vault, registry=self.registry, settings=self.settings,
            store=self.store, current_gid=self._current_gid,
            columns=TABLE_COLUMNS, fixed_columns=FIXED_COLUMNS,
            apply_columns=self.apply_columns)
        self.wait_window(dlg)
        # The group's online-check config may have changed -> reschedule.
        self._schedule_online_autocheck()

    # ------------------------------------------------------------- columns
    def apply_columns(self, hidden):
        visible = [c for c in TABLE_COLUMNS if c not in hidden or c in FIXED_COLUMNS]
        self.table.config(displaycolumns=visible)

    # ------------------------------------------------- online auto-check
    def _schedule_online_autocheck(self):
        if self._online_job is not None:
            self.after_cancel(self._online_job)
            self._online_job = None
        g = self.store.groups.get(self._current_gid)
        if g and g.online_check:
            self._online_job = self.after(max(5, g.online_interval) * 1000,
                                          self._run_online_autocheck)

    def _run_online_autocheck(self):
        self._online_job = None
        cams = self.store.cameras_in(self._current_gid)
        if cams:
            threading.Thread(target=self._worker_online, args=(cams,), daemon=True).start()
        # reschedule the next tick
        self._schedule_online_autocheck()


def main():
    MainWindow().mainloop()


if __name__ == "__main__":
    main()
