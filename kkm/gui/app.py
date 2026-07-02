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
import re
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

# Parallele Netzwerk-Zugriffe (Firmware/Online/Zugangsdaten) je Suche.
NET_WORKERS = 12

from kkm.version import APP_NAME, __version__
from kkm.core import (Credentials, Capability, GroupStore, ALL_CAMERAS_ID,
                      camera_key, PasswordVault, AppSettings, VaultError)
from kkm.core.groups import config_dir
from kkm.plugins import build_registry
from kkm.plugins.axis.discovery import FIELD_NAMES, get_first_ip, export_results
from kkm.gui import theme
from kkm.gui.dialogs import ACTION_DIALOGS
from kkm.gui.dialogs.settings_dialog import SettingsDialog
from kkm.gui.dialogs.credentials_prompt import CredentialPromptDialog
from kkm.gui.dialogs.vault_access import ensure_vault_unlocked

ONLINE_COL = "● Status"
GROUP_COL = "Gruppe(n)"
TABLE_COLUMNS = ["Name", "Modell", "IP-Adresse", "MAC/Seriennummer", "Firmware",
                 GROUP_COL, ONLINE_COL]
FIXED_COLUMNS = {"Name"}   # always visible, cannot be hidden

_NUM_CHUNK = re.compile(r"(\d+)")


def _sort_key(value):
    """Natürliche Sortierung: Zahlengruppen numerisch, Rest kleingeschrieben.

    Sorgt für sinnvolle Reihenfolge bei IPs (192.168.0.9 < .10), Firmware-
    Versionen (5.20.5 < 11.9.61) und Namen. Leere Werte / Platzhalter ("—")
    sortieren aufsteigend nach hinten."""
    s = str(value).strip()
    if s in ("", "—"):
        return (1, [])
    parts = []
    for chunk in _NUM_CHUNK.split(s.lower()):
        if chunk.isdigit():
            parts.append((0, int(chunk), ""))
        elif chunk:
            parts.append((1, 0, chunk))
    return (0, parts)


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("1100x650")

        self.store = GroupStore()
        self.settings = AppSettings()
        # Modernes Erscheinungsbild (Sun Valley) vor dem UI-Aufbau anwenden.
        self._theme = self.settings.get("theme", "dark")
        theme.apply_theme(self, self._theme)
        self.registry = build_registry(self.settings.get("enabled_plugins"))
        self.vault = PasswordVault()
        # Tresor beim Start automatisch entsperren, falls der Nutzer das in den
        # Einstellungen aktiviert hat (hinterlegtes, geräte­gebundenes Token).
        if self.vault.autounlock_enabled:
            try:
                self.vault.try_autounlock()
            except Exception:  # noqa: BLE001 - Start darf daran nie scheitern
                pass
        self.creds = Credentials()
        self._q: queue.Queue = queue.Queue()
        self._current_gid = ALL_CAMERAS_ID
        # rowid (in tree) -> camera dict, for the device table
        self._row_cam: dict[str, dict] = {}
        # Spalten-Sortierung: aktuelle Spalte + Richtung (None = ungeordnet)
        self._sort_col: str | None = None
        self._sort_reverse = False
        self._online_job = None   # after() id for the per-group auto online check
        # Session-Cache erfolgreich verwendeter Zugangsdaten je Kamera (camera_key
        # -> (user, password)); ergänzt den Tresor, falls dieser gesperrt ist.
        self._cam_creds: dict[str, tuple] = {}
        self._unknown_queue: list[dict] = []

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
        # Tresor-Schnellschalter: 🔒 gesperrt / 🔓 entsperrt, klickbar zum Umschalten.
        # Das Symbol soll möglichst groß sein, der Button aber gleich hoch wie die
        # anderen. Deshalb wählt _match_lock_height die größte Schriftgröße, deren
        # Button-Naturhöhe noch in die Nachbar-Höhe passt — so zentriert ttk das
        # Symbol von selbst (kein Beschneiden, kein Versatz).
        ttk.Style().configure("Lock.TButton", font=("TkDefaultFont", 14), padding=0,
                              anchor="center")
        self._lock_btn = ttk.Button(bar, width=2, style="Lock.TButton",
                                    command=self._toggle_vault_lock)
        self._lock_btn.pack(side=tk.RIGHT, padx=(0, 6))
        settings_btn = ttk.Button(bar, text="Einstellungen", command=self._open_settings)
        settings_btn.pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(bar, text="Exportieren", command=self._export).pack(
            side=tk.RIGHT, padx=(0, 6))
        self._update_lock_button()
        # Größte Schrift wählen, deren Button noch so hoch wie die Nachbarn ist.
        self._match_lock_height(settings_btn)
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
        gt_frame = ttk.Frame(left)
        gt_frame.pack(fill=tk.BOTH, expand=True)
        self.group_tree = ttk.Treeview(gt_frame, show="tree", selectmode="browse")
        self._add_scrollbars(gt_frame, self.group_tree)
        self.group_tree.bind("<<TreeviewSelect>>", self._on_group_select)

        gbtns = ttk.Frame(left)
        gbtns.pack(fill=tk.X, pady=4)
        ttk.Button(gbtns, text="+ Gruppe", command=self._add_group).pack(side=tk.LEFT)
        ttk.Button(gbtns, text="Umbenennen", command=self._rename_group).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(gbtns, text="Löschen", command=self._delete_group).pack(side=tk.LEFT)

        # Mindestbreite der linken Spalte: die drei Gruppen-Buttons müssen immer
        # lesbar nebeneinander passen. ttk.PanedWindow kennt keine Pro-Pane-
        # minsize, darum klemmen wir die Sash-Position auf deren Wunschbreite.
        self._paned = paned
        self._left_ctrls = gbtns
        self._left_min = 0
        self.after_idle(self._init_left_min)
        paned.bind("<B1-Motion>", self._enforce_left_min, add="+")
        paned.bind("<ButtonRelease-1>", self._enforce_left_min, add="+")
        paned.bind("<Configure>", self._enforce_left_min, add="+")

        # --- right: device table ---
        right = ttk.Frame(paned)
        paned.add(right, weight=4)
        tbl_frame = ttk.Frame(right)
        tbl_frame.pack(fill=tk.BOTH, expand=True)
        self.table = ttk.Treeview(tbl_frame, columns=TABLE_COLUMNS, show="headings",
                                  selectmode="extended")
        for col in TABLE_COLUMNS:
            self.table.heading(col, text=col,
                               command=lambda c=col: self._sort_by(c))
            # minwidth = Vorgabebreite: Spalten quetschen sich nicht beliebig
            # zusammen -> ab zu schmalem Fenster erscheint der H-Scrollbalken.
            self.table.column(col, width=160, minwidth=160, stretch=True)
        self.table.column(ONLINE_COL, width=90, minwidth=90, stretch=False,
                          anchor=tk.CENTER)
        self._apply_status_tags()      # Statusfarben (themen-passend): online/offline
        self._add_scrollbars(tbl_frame, self.table)
        # Rechtsklick -> Kameras Gruppen zuweisen (additiv) / entfernen.
        self.table.bind("<Button-3>", self._show_table_menu)
        # Doppelklick -> Kamera-Weboberfläche im Browser öffnen.
        self.table.bind("<Double-Button-1>", self._open_camera_web)

    def _init_left_min(self):
        """Mindestbreite der linken Spalte aus der Button-Zeile ableiten und die
        Anfangs-Sash-Position sicherstellen."""
        self._left_ctrls.update_idletasks()
        self._left_min = self._left_ctrls.winfo_reqwidth() + 12
        self._enforce_left_min()

    def _enforce_left_min(self, _evt=None):
        """Sash 0 nicht enger als ``_left_min`` zulassen (Gruppen-Buttons lesbar)."""
        if not self._left_min:
            return
        try:
            if self._paned.sashpos(0) < self._left_min:
                self._paned.sashpos(0, self._left_min)
        except tk.TclError:
            pass

    def _add_scrollbars(self, container, tree):
        """Bettet *tree* per Grid in *container* ein und hängt auto-versteckende
        Scrollbalken an (vertikal rechts, horizontal unten). Ein Balken wird nur
        eingeblendet, wenn der Inhalt in der jeweiligen Richtung nicht passt."""
        vbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        hbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(
            yscrollcommand=self._autohide_scroll(vbar, row=0, column=1, sticky="ns"),
            xscrollcommand=self._autohide_scroll(hbar, row=1, column=0, sticky="ew"),
        )
        tree.grid(row=0, column=0, sticky="nsew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

    @staticmethod
    def _autohide_scroll(bar, row, column, sticky):
        """Liefert ein ``set``-Callback, das *bar* nur einblendet (grid), wenn der
        sichtbare Bereich < 1 ist, sonst ausblendet (grid_remove)."""
        def _set(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                bar.grid_remove()
            else:
                bar.grid(row=row, column=column, sticky=sticky)
            bar.set(first, last)
        return _set

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
        self._autosize_group_column()

    def _autosize_group_column(self):
        """minwidth der Baumspalte (#0) an den längsten Gruppennamen anpassen.

        Sonst füllt die stretch-Spalte nur die Widget-Breite und klemmt langen
        Text ab (xview bleibt 0..1) — der horizontale Scrollbalken erschiene nie.
        Mit passender minwidth kann die Spalte bei zu schmalem Panel nicht mehr
        schrumpfen -> der Auto-Hide-H-Balken greift."""
        # Mit der *tatsächlichen* Treeview-Schrift messen: sv_ttk setzt eine
        # größere (SunValleyBodyFont) als TkDefaultFont. Würde man mit der
        # falschen Schrift messen, fiele `need` zu klein aus — die stretch-Spalte
        # dehnte sich dann nur bis zur Panelbreite und klemmte den echten Text ab,
        # ohne dass ein Scrollbalken erscheint. Tcls `font measure` akzeptiert das
        # Font-Objekt aus dem Style direkt.
        tv_font = ttk.Style().lookup("Treeview", "font") or "TkDefaultFont"

        def measure(text):
            try:
                return int(self.group_tree.tk.call("font", "measure", tv_font, text))
            except tk.TclError:
                return len(text) * 8   # grobe Schätzung als Rückfall

        indent = 24   # Einrückung je Ebene inkl. Aufklapp-Indikator (großzügig)
        need = 0
        for iid in self.group_tree.get_children(""):   # Wurzel: Ebene 1
            need = max(need, measure(self.group_tree.item(iid, "text")) + indent)
            for child in self.group_tree.get_children(iid):   # Kinder: Ebene 2
                need = max(need, measure(self.group_tree.item(child, "text")) + 2 * indent)
        need += 24   # etwas Luft
        try:
            self.group_tree.column("#0", width=need, minwidth=need, stretch=True)
        except tk.TclError:
            pass

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
        rows = []
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
            tag = "" if online is None else ("online" if online else "offline")
            rows.append((key, values, tag, cam))
        if self._sort_col in TABLE_COLUMNS:
            idx = TABLE_COLUMNS.index(self._sort_col)
            rows.sort(key=lambda r: _sort_key(r[1][idx]),
                      reverse=self._sort_reverse)
        for key, values, tag, cam in rows:
            rowid = self.table.insert("", "end", iid=key, values=values,
                                      tags=(tag,) if tag else ())
            self._row_cam[rowid] = cam
        g = self.store.groups.get(self._current_gid)
        n = len(self._row_cam)
        self.status.config(text=f"{g.name if g else ''}: {n} Gerät(e)")

    def _sort_by(self, col):
        """Klick auf Spaltenkopf: nach dieser Spalte sortieren, Richtung togglen."""
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._update_sort_indicators()
        self._refresh_table()

    def _update_sort_indicators(self):
        """Pfeil (▲/▼) an den aktiv sortierten Spaltenkopf hängen."""
        for col in TABLE_COLUMNS:
            if col == self._sort_col:
                arrow = " ▼" if self._sort_reverse else " ▲"
                self.table.heading(col, text=col + arrow)
            else:
                self.table.heading(col, text=col)

    def _selected_cameras(self) -> list[dict]:
        return [self._row_cam[r] for r in self.table.selection() if r in self._row_cam]

    # ---------------------------------------------- Kamera im Browser öffnen
    def _open_camera_web(self, event):
        """Doppelklick: die angeklickte Kamera im Webbrowser öffnen."""
        row = self.table.identify_row(event.y)
        cam = self._row_cam.get(row)
        if cam:
            self._open_camera_web_cam(cam)

    def _open_camera_web_cam(self, cam):
        ip = get_first_ip(cam)
        if not ip:
            messagebox.showinfo(APP_NAME, "Für diese Kamera ist keine IP-Adresse bekannt.")
            return
        url = ip if "://" in ip else f"http://{ip}"
        try:
            webbrowser.open(url)
            self.status.config(text=f"Kamera im Browser geöffnet: {url}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Konnte den Browser nicht öffnen:\n{exc}")

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
        # Nur bei genau einer Auswahl mit IP im Browser öffnen anbieten.
        if len(cams) == 1 and get_first_ip(cams[0]):
            menu.add_command(label="Kamera öffnen",
                             command=lambda: self._open_camera_web_cam(cams[0]))
            menu.add_separator()
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
        self.store.forget_many(keys)            # ein Speichervorgang statt N
        if self.vault and not self.vault.is_locked:
            self.vault.delete_many(keys)
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

    @staticmethod
    def _run_pool(items, task, workers=NET_WORKERS):
        """Führt task(item) parallel aus (Thread-Pool); Tasks fangen Fehler selbst."""
        if not items:
            return
        with ThreadPoolExecutor(max_workers=min(workers, len(items))) as ex:
            list(ex.map(task, items))

    def _worker_online(self, cams):
        def task(cam):
            vendor = self.registry.get(cam.get("_vendor", "axis"))
            ok = bool(vendor and vendor.check_online(cam, self.creds))
            self._q.put(("online", (camera_key(cam), ok)))
        self._run_pool(cams, task)
        self._q.put(("online_done", None))

    # -------------------------------------------- Geräteinfo (Firmware/Modell)
    def _creds_known(self, cam) -> bool:
        key = camera_key(cam)
        if key in self._cam_creds:
            return True
        return bool(self.vault and not self.vault.is_locked
                    and self.vault.get_password(key))

    def _creds_for(self, cam) -> Credentials | None:
        """Bekannte Zugangsdaten einer Kamera (Session-Cache oder Tresor)."""
        key = camera_key(cam)
        if key in self._cam_creds:
            u, p = self._cam_creds[key]
            return Credentials(username=u, password=p)
        if self.vault and not self.vault.is_locked:
            stored = self.vault.get_password(key)
            if stored:
                return Credentials(username=stored.get("username", "root"),
                                   password=stored.get("password", ""))
        return None

    def _after_search(self, found):
        """Nach der Suche: bekannte Kameras still auslesen, für unbekannte fragen."""
        known = [c for c in found if self._creds_known(c)]
        if known:
            threading.Thread(target=self._worker_enrich, args=(known,),
                             daemon=True).start()
        self._unknown_queue = [c for c in found if not self._creds_known(c)]
        # Wenn Zugangsdaten abgefragt werden und der Tresor gesperrt/nicht angelegt
        # ist, einmal anbieten, ihn einzurichten -> sonst nur Sitzungs-Cache.
        if self._unknown_queue and self.vault is not None and self.vault.is_locked:
            ensure_vault_unlocked(
                self, self.vault,
                "Damit eingegebene Zugangsdaten dauerhaft gespeichert werden")
        # asynchron, damit der Queue-Poll während der modalen Abfrage weiterläuft
        self.after(0, self._prompt_next_credentials)

    def _worker_enrich(self, cams):
        """Liest Firmware/Modell für Kameras mit bekannten Zugangsdaten (still).

        Zählt Erfolge/Fehler mit, damit die Statuszeile Rückmeldung geben kann
        (statt Lesefehler komplett stumm zu verschlucken)."""
        stats = {"fw": 0, "nofw": 0, "fail": 0}
        lock = threading.Lock()
        def task(cam):
            plugin = self.registry.get(cam.get("_vendor", "axis"))
            creds = self._creds_for(cam)
            if not plugin or not creds:
                with lock:
                    stats["fail"] += 1
                return
            try:
                info = plugin.device_info(cam, creds)
                self._q.put(("device_info", (camera_key(cam), info)))
                with lock:
                    stats["fw" if info.get("firmware") else "nofw"] += 1
            except Exception:  # noqa: BLE001 - Lesefehler -> Feld bleibt leer
                with lock:
                    stats["fail"] += 1
        self._run_pool(cams, task)
        self._q.put(("enrich_done", (stats["fw"], stats["nofw"], stats["fail"])))

    def _prompt_next_credentials(self):
        # bereits aufgelöste Kameras herausfiltern
        self._unknown_queue = [c for c in self._unknown_queue if not self._creds_known(c)]
        if not self._unknown_queue:
            self._refresh_table()
            return
        cam = self._unknown_queue[0]
        dlg = CredentialPromptDialog(self, cam, len(self._unknown_queue))
        self.wait_window(dlg)
        action, user, pw, try_all = dlg.result or ("cancel", None, None, False)
        if action == "cancel":
            self._unknown_queue = []
            self._refresh_table()
            return
        if action == "skip":
            self._unknown_queue.pop(0)
            self._prompt_next_credentials()
            return
        # action == "apply"
        targets = list(self._unknown_queue) if try_all else [cam]
        self.progress.start(12)
        self.status.config(text="Prüfe Zugangsdaten…")
        threading.Thread(target=self._worker_creds, args=(targets, user, pw),
                         daemon=True).start()

    def _apply_device_info(self, key, info):
        cam = self.store.roster.get(key)
        if not cam:
            return
        fw = info.get("firmware")
        model = info.get("model")
        if fw:
            cam["_firmware"] = fw
        if model and model != "?":
            cam["_model"] = model

    def _worker_creds(self, targets, user, pw):
        creds = Credentials(username=user, password=pw)
        def task(cam):
            plugin = self.registry.get(cam.get("_vendor", "axis"))
            if not plugin:
                return
            try:
                info = plugin.device_info(cam, creds)
                self._q.put(("cred_ok", (camera_key(cam), user, pw, info)))
            except Exception:  # noqa: BLE001 - Zugangsdaten passen (noch) nicht
                self._q.put(("cred_fail", camera_key(cam)))
        self._run_pool(targets, task)
        self._q.put(("creds_done", None))

    # ---------------------------------------------------------------- queue
    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "search_done":
                    self.store.remember_all(payload)
                    # Gefundene Kameras = online, alle übrigen bekannten = offline.
                    found_keys = {camera_key(c) for c in payload}
                    for key, cam in self.store.roster.items():
                        cam["_online"] = key in found_keys
                    self.progress.stop()
                    self._refresh_table()
                    self.status.config(text=f"Suche fertig: {len(payload)} Gerät(e)")
                    self._after_search(payload)
                elif kind == "online":
                    key, ok = payload
                    if key in self.store.roster:
                        self.store.roster[key]["_online"] = ok
                elif kind == "online_done":
                    self.progress.stop()
                    self._refresh_table()
                elif kind == "device_info":
                    self._apply_device_info(*payload)
                elif kind == "enrich_done":
                    self.store.save()
                    self._refresh_table()
                    fw, nofw, fail = payload if payload else (0, 0, 0)
                    if fw or nofw or fail:
                        msg = f"Firmware gelesen: {fw}"
                        if nofw:
                            msg += f", {nofw} ohne Firmware-Wert"
                        if fail:
                            msg += (f", {fail} fehlgeschlagen (Zugangsdaten/"
                                    "Erreichbarkeit)")
                        self.status.config(text=msg)
                elif kind == "cred_ok":
                    key, user, pw, info = payload
                    self._cam_creds[key] = (user, pw)
                    if self.vault and not self.vault.is_locked:
                        self.vault.set_password(key, user, pw)
                    self._apply_device_info(key, info)
                elif kind == "cred_fail":
                    pass   # Zugangsdaten passten nicht -> Kamera bleibt unbekannt
                elif kind == "creds_done":
                    self.progress.stop()
                    self.store.save()
                    self._refresh_table()
                    self.after(0, self._prompt_next_credentials)   # nächste/erneute Abfrage
                elif kind == "error":
                    self.progress.stop()
                    messagebox.showerror(APP_NAME, payload)
        except queue.Empty:
            pass
        self._update_lock_button()   # Schloss-Symbol mit Tresor-Status synchron halten
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
            apply_columns=self.apply_columns,
            theme_mode=self._theme, on_theme_change=self.set_theme)
        self.wait_window(dlg)
        # Ein Import kann Geräte/Gruppen geändert haben -> Ansicht neu aufbauen.
        if getattr(dlg, "data_changed", False):
            self._refresh_groups()
            self._refresh_table()
        # The group's online-check config may have changed -> reschedule.
        self._schedule_online_autocheck()
        self._update_lock_button()      # Tresor-Status kann sich geändert haben

    # ----------------------------------------------------------- vault lock button
    def _match_lock_height(self, ref_btn):
        """Größte Schriftgröße für das Schloss-Symbol wählen, deren Button-Naturhöhe
        noch ≤ Höhe eines normalen Toolbar-Buttons ist. So ist der Button gleich hoch
        und ttk zentriert das Symbol von selbst (kein Beschneiden, kein Versatz)."""
        try:
            self.update_idletasks()
            ref_h = ref_btn.winfo_reqheight()
            if ref_h <= 1:
                return
            best = 11
            for size in range(22, 10, -1):
                ttk.Style().configure("Lock.TButton", font=("TkDefaultFont", size),
                                      padding=0, anchor="center")
                self.update_idletasks()
                if self._lock_btn.winfo_reqheight() <= ref_h:
                    best = size
                    break
            ttk.Style().configure("Lock.TButton", font=("TkDefaultFont", best),
                                  padding=0, anchor="center")
        except Exception:  # noqa: BLE001 - Layout darf daran nie scheitern
            pass

    def _update_lock_button(self):
        """Vorhängeschloss-Symbol an den Tresor-Status anpassen."""
        if not hasattr(self, "_lock_btn"):
            return
        locked = self.vault is None or self.vault.is_locked
        self._lock_btn.config(text="🔒" if locked else "🔓")

    def _toggle_vault_lock(self):
        """Klick auf das Schloss: entsperren (oder anlegen) bzw. sperren."""
        v = self.vault
        if v is None:
            return
        if not v.is_locked:
            v.lock()
            self.status.config(text="Tresor gesperrt 🔒")
        elif v.exists:
            pw = simpledialog.askstring("Tresor entsperren", "Master-Passwort:",
                                        show="*", parent=self)
            if not pw:
                return
            try:
                v.unlock(pw)
            except VaultError as exc:
                messagebox.showerror("Tresor", str(exc), parent=self)
                return
            self.status.config(text="Tresor entsperrt 🔓")
        else:
            # Noch nicht angelegt -> gemeinsamer Helfer bietet das Anlegen an.
            if not ensure_vault_unlocked(self, v, "Zum Entsperren"):
                return
            self.status.config(text="Tresor entsperrt 🔓")
        self._update_lock_button()

    # ------------------------------------------------------------- columns
    def apply_columns(self, hidden):
        visible = [c for c in TABLE_COLUMNS if c not in hidden or c in FIXED_COLUMNS]
        self.table.config(displaycolumns=visible)

    # --------------------------------------------------------------- theme
    def _apply_status_tags(self):
        self.table.tag_configure("online", foreground=theme.CURRENT["online"])
        self.table.tag_configure("offline", foreground=theme.CURRENT["offline"])

    def set_theme(self, mode):
        self._theme = mode
        self.settings.set("theme", mode)
        theme.apply_theme(self, mode)
        self._apply_status_tags()
        self._refresh_table()

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
