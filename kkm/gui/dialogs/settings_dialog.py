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

"""Settings dialog: vault, plugin manager, per-group online check, columns.

A tabbed Toplevel that operates directly on the shared objects passed in
(``vault``, ``registry``, ``store``, ``settings``) so changes take effect
immediately; column changes are pushed back to the main window via the
``apply_columns`` callback.

Tabs:
- **Tresor** — create / unlock / lock / change the master password of the
  encrypted password vault (:class:`kkm.core.PasswordVault`).
- **Plugins** — enable/disable vendor plugins (persisted in ``settings``).
- **Online-Prüfung** — per-group online check on/off + interval (stored in the
  :class:`kkm.core.GroupStore`).
- **Spalten** — hide/show device-table columns (persisted in ``settings``).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from kkm.core import ALL_CAMERAS_ID, VIRTUAL_GROUP_IDS, VaultError, camera_key
from kkm.gui.dialogs.vault_access import ensure_vault_unlocked


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, *, vault, registry, settings, store, current_gid,
                 columns, fixed_columns=(), apply_columns=None,
                 theme_mode="dark", on_theme_change=None):
        super().__init__(parent)
        self.title("Einstellungen")
        self.transient(parent)
        self.vault = vault
        self.registry = registry
        self.settings = settings
        self.store = store
        self.current_gid = current_gid
        self.columns = list(columns)
        self.fixed_columns = set(fixed_columns)
        self.apply_columns = apply_columns
        self.theme_mode = theme_mode
        self.on_theme_change = on_theme_change
        # Wird True, sobald der Import Geräte/Gruppen geändert hat -> Hauptfenster
        # muss danach Baum + Tabelle neu aufbauen.
        self.data_changed = False

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        nb.add(self._build_appearance_tab(nb), text="Darstellung")
        nb.add(self._build_vault_tab(nb), text="Tresor")
        nb.add(self._build_plugins_tab(nb), text="Plugins")
        nb.add(self._build_online_tab(nb), text="Online-Prüfung")
        nb.add(self._build_columns_tab(nb), text="Spalten")
        nb.add(self._build_import_tab(nb), text="Import")

        ttk.Button(self, text="Schließen", command=self.destroy).pack(
            anchor=tk.E, padx=8, pady=(0, 8))

    # -------------------------------------------------------------- appearance
    def _build_appearance_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text="Erscheinungsbild:",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))
        self._theme_var = tk.StringVar(value=self.theme_mode)
        for val, text in (("dark", "Dunkel"), ("light", "Hell")):
            ttk.Radiobutton(tab, text=text, value=val, variable=self._theme_var,
                            command=self._on_theme).pack(anchor=tk.W, pady=1)
        ttk.Label(tab, text="Modernes Sun-Valley-Design. Wirkt sofort.").pack(
            anchor=tk.W, pady=(6, 0))
        return tab

    def _on_theme(self):
        if self.on_theme_change:
            self.on_theme_change(self._theme_var.get())

    # ------------------------------------------------------------------- vault
    def _build_vault_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        self._vault_status = ttk.Label(tab, font=("TkDefaultFont", 10, "bold"))
        self._vault_status.pack(anchor=tk.W, pady=(0, 8))

        self._vault_body = ttk.Frame(tab)
        self._vault_body.pack(fill=tk.X)
        self._render_vault()
        return tab

    def _render_vault(self):
        for w in self._vault_body.winfo_children():
            w.destroy()
        if self.vault is None:
            self._vault_status.config(text="Tresor nicht verfügbar.")
            return

        if not self.vault.exists:
            self._vault_status.config(text="Status: noch nicht angelegt")
            self._pw_fields(self._vault_body,
                            [("Master-Passwort:", "m1"), ("Wiederholen:", "m2")])
            ttk.Button(self._vault_body, text="Tresor anlegen",
                       command=self._create_vault).grid(row=2, column=0, columnspan=2,
                                                        sticky=tk.W, pady=6)
        elif self.vault.is_locked:
            self._vault_status.config(text="Status: gesperrt 🔒")
            self._pw_fields(self._vault_body, [("Master-Passwort:", "m1")])
            ttk.Button(self._vault_body, text="Entsperren",
                       command=self._unlock_vault).grid(row=1, column=0, columnspan=2,
                                                        sticky=tk.W, pady=6)
            self._autounlock_widgets(self._vault_body, start_row=2)
        else:
            self._vault_status.config(text="Status: entsperrt 🔓")
            ttk.Button(self._vault_body, text="Sperren",
                       command=self._lock_vault).grid(row=0, column=0, sticky=tk.W)
            ttk.Separator(self._vault_body, orient=tk.HORIZONTAL).grid(
                row=1, column=0, columnspan=2, sticky="ew", pady=8)
            ttk.Label(self._vault_body, text="Master-Passwort ändern:").grid(
                row=2, column=0, columnspan=2, sticky=tk.W)
            self._pw_fields(self._vault_body,
                            [("Aktuell:", "old"), ("Neu:", "m1"), ("Wiederholen:", "m2")],
                            start_row=3)
            ttk.Button(self._vault_body, text="Ändern",
                       command=self._change_master).grid(row=6, column=0, columnspan=2,
                                                         sticky=tk.W, pady=6)
            ttk.Separator(self._vault_body, orient=tk.HORIZONTAL).grid(
                row=7, column=0, columnspan=2, sticky="ew", pady=8)
            self._autounlock_widgets(self._vault_body, start_row=8)

    def _autounlock_widgets(self, parent, start_row):
        """Checkbox + Warnhinweis für die automatische Entsperrung beim Start."""
        from kkm.gui import theme
        self._auto_var = tk.BooleanVar(value=self.vault.autounlock_enabled)
        ttk.Checkbutton(parent, text="Tresor beim Programmstart automatisch entsperren",
                        variable=self._auto_var,
                        command=self._toggle_autounlock).grid(
            row=start_row, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        ttk.Label(parent, wraplength=380, justify=tk.LEFT,
                  foreground=theme.CURRENT.get("warn", "#c0392b"),
                  text="Hinweis: Speichert das Master-Passwort gerätegebunden auf "
                       "diesem Rechner. Bequem, aber weniger sicher — wer als dieser "
                       "Benutzer Zugriff hat, kann den Tresor öffnen.").grid(
            row=start_row + 1, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))

    def _toggle_autounlock(self):
        if self._auto_var.get():
            pw = simpledialog.askstring(
                "Auto-Entsperrung", "Master-Passwort zur Bestätigung:",
                show="*", parent=self)
            if not pw:
                self._auto_var.set(False)
                return
            try:
                self.vault.enable_autounlock(pw)
            except VaultError as exc:
                messagebox.showerror("Tresor", str(exc), parent=self)
                self._auto_var.set(False)
                return
            messagebox.showinfo(
                "Tresor", "Auto-Entsperrung aktiviert — der Tresor wird beim Start "
                "automatisch entsperrt.", parent=self)
            self._render_vault()       # war evtl. gesperrt -> jetzt entsperrt
        else:
            self.vault.disable_autounlock()

    def _pw_fields(self, parent, fields, start_row=0):
        self._pw_vars = getattr(self, "_pw_vars", {})
        for i, (label, key) in enumerate(fields):
            r = start_row + i
            ttk.Label(parent, text=label).grid(row=r, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar()
            self._pw_vars[key] = var
            ttk.Entry(parent, textvariable=var, width=24, show="*").grid(
                row=r, column=1, sticky=tk.W, padx=4, pady=2)

    def _create_vault(self):
        m1, m2 = self._pw_vars["m1"].get(), self._pw_vars["m2"].get()
        if not m1:
            messagebox.showinfo("Tresor", "Bitte ein Master-Passwort eingeben.", parent=self)
            return
        if m1 != m2:
            messagebox.showerror("Tresor", "Die Passwörter stimmen nicht überein.", parent=self)
            return
        try:
            self.vault.create(m1)
        except VaultError as exc:
            messagebox.showerror("Tresor", str(exc), parent=self)
            return
        messagebox.showinfo("Tresor", "Tresor angelegt und entsperrt.", parent=self)
        self._render_vault()

    def _unlock_vault(self):
        try:
            self.vault.unlock(self._pw_vars["m1"].get())
        except VaultError as exc:
            messagebox.showerror("Tresor", str(exc), parent=self)
            return
        self._render_vault()

    def _lock_vault(self):
        self.vault.lock()
        self._render_vault()

    def _change_master(self):
        old, m1, m2 = (self._pw_vars["old"].get(), self._pw_vars["m1"].get(),
                       self._pw_vars["m2"].get())
        if m1 != m2:
            messagebox.showerror("Tresor", "Die neuen Passwörter stimmen nicht überein.",
                                 parent=self)
            return
        try:
            self.vault.change_master(old, m1)
        except VaultError as exc:
            messagebox.showerror("Tresor", str(exc), parent=self)
            return
        messagebox.showinfo("Tresor", "Master-Passwort geändert.", parent=self)
        self._render_vault()

    # ----------------------------------------------------------------- plugins
    def _build_plugins_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text="Hersteller-Plugins aktivieren/deaktivieren:").pack(anchor=tk.W)
        self._plugin_vars = {}
        for plugin in self.registry.all():
            var = tk.BooleanVar(value=self.registry.is_enabled(plugin.id))
            self._plugin_vars[plugin.id] = var
            ttk.Checkbutton(tab, text=plugin.name, variable=var,
                            command=self._save_plugins).pack(anchor=tk.W, pady=2)
        return tab

    def _save_plugins(self):
        for pid, var in self._plugin_vars.items():
            self.registry.set_enabled(pid, var.get())
        self.settings.set("enabled_plugins", self.registry.enabled_ids())

    # ----------------------------------------------------------------- online
    def _build_online_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        g = self.store.groups.get(self.current_gid)
        name = g.name if g else "?"
        ttk.Label(tab, text=f"Online-Prüfung für Gruppe: {name}",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self._online_on = tk.BooleanVar(value=bool(g and g.online_check))
        ttk.Checkbutton(tab, text="Automatische Online-Prüfung aktiv",
                        variable=self._online_on,
                        command=self._save_online).pack(anchor=tk.W)
        row = ttk.Frame(tab)
        row.pack(anchor=tk.W, pady=4)
        ttk.Label(row, text="Intervall (Sekunden):").pack(side=tk.LEFT)
        self._online_interval = tk.IntVar(value=(g.online_interval if g else 60))
        sp = ttk.Spinbox(row, from_=5, to=3600, width=7,
                         textvariable=self._online_interval, command=self._save_online)
        sp.pack(side=tk.LEFT, padx=4)
        sp.bind("<FocusOut>", lambda _e: self._save_online())
        ttk.Label(tab, text="Gilt je Gruppe; im Hauptfenster wird die jeweils "
                            "gewählte Gruppe automatisch geprüft.").pack(anchor=tk.W, pady=(6, 0))
        return tab

    def _save_online(self):
        self.store.set_online_check(self.current_gid, self._online_on.get(),
                                    self._online_interval.get())

    # ----------------------------------------------------------------- columns
    def _build_columns_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text="Sichtbare Spalten der Geräteliste:").pack(anchor=tk.W)
        hidden = set(self.settings.get("hidden_columns", []))
        self._col_vars = {}
        for col in self.columns:
            var = tk.BooleanVar(value=col not in hidden)
            self._col_vars[col] = var
            state = tk.DISABLED if col in self.fixed_columns else tk.NORMAL
            ttk.Checkbutton(tab, text=col, variable=var, state=state,
                            command=self._save_columns).pack(anchor=tk.W, pady=1)
        return tab

    def _save_columns(self):
        hidden = [c for c, v in self._col_vars.items()
                  if not v.get() and c not in self.fixed_columns]
        self.settings.set("hidden_columns", hidden)
        if self.apply_columns:
            self.apply_columns(hidden)

    # ------------------------------------------------------------------ import
    def _build_import_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text="Import aus AXIS Device Manager",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(tab, justify=tk.LEFT, text=(
            "Übernimmt Geräte und Gruppen aus einer AXIS-Device-Manager-Export-"
            "datei (JSON, Format 1.x und 2.x). Vorhandene Gruppen gleichen Namens "
            "werden ergänzt, Geräte anhand ihrer MAC/Seriennummer zusammengeführt.\n"
            "Enthaltene Zugangsdaten werden — sofern vorhanden — in den Tresor "
            "übernommen (dazu muss er entsperrt sein).")
        ).pack(anchor=tk.W, pady=(2, 8), fill=tk.X)

        self._import_creds_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(tab, text="Zugangsdaten in den Tresor übernehmen",
                        variable=self._import_creds_var).pack(anchor=tk.W)

        ttk.Button(tab, text="Export-Datei wählen und importieren…",
                   command=self._run_import).pack(anchor=tk.W, pady=(8, 6))

        logframe = ttk.Frame(tab)
        logframe.pack(fill=tk.BOTH, expand=True)
        self._import_log = tk.Text(logframe, height=10, width=60, wrap=tk.WORD,
                                   state=tk.DISABLED)
        sb = ttk.Scrollbar(logframe, orient=tk.VERTICAL,
                           command=self._import_log.yview)
        self._import_log.configure(yscrollcommand=sb.set)
        self._import_log.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        logframe.rowconfigure(0, weight=1)
        logframe.columnconfigure(0, weight=1)
        return tab

    def _log_import(self, text):
        self._import_log.configure(state=tk.NORMAL)
        self._import_log.insert(tk.END, text + "\n")
        self._import_log.see(tk.END)
        self._import_log.configure(state=tk.DISABLED)
        self._import_log.update_idletasks()

    def _run_import(self):
        path = filedialog.askopenfilename(
            parent=self, title="AXIS-Device-Manager-Export wählen",
            filetypes=[("AXIS-Export (JSON)", "*.json"), ("Alle Dateien", "*.*")])
        if not path:
            return
        # Import-Parser erst hier laden (zieht das axis-Paket / zeroconf nach).
        from kkm.plugins.axis.adm_import import parse_export, AdmImportError
        try:
            result = parse_export(path)
        except AdmImportError as exc:
            messagebox.showerror("Import", str(exc), parent=self)
            return

        summary = (f"Datei-Format {result.version}\n"
                   f"  Geräte: {result.n_cameras}\n"
                   f"  Gruppen: {result.n_groups}\n"
                   f"  Zugangsdaten: {result.n_credentials}")
        if not messagebox.askyesno(
                "Import bestätigen",
                summary + "\n\nJetzt importieren?", parent=self):
            return

        # Zugangsdaten -> Tresor entsperren (wenn gewünscht und vorhanden)
        want_creds = self._import_creds_var.get() and result.n_credentials > 0
        store_creds = False
        if want_creds:
            if ensure_vault_unlocked(self, self.vault,
                                     "Zum Übernehmen der Zugangsdaten"):
                store_creds = True
            elif not messagebox.askyesno(
                    "Import",
                    "Der Tresor ist gesperrt. Ohne Übernahme der Zugangsdaten "
                    "fortfahren?", parent=self):
                return

        self._apply_import(result, store_creds)

    def _find_or_create_group(self, name):
        """Gruppe gleichen Namens finden (außer 'Alle Kameras') oder neu anlegen."""
        for gid, g in self.store.groups.items():
            if gid not in VIRTUAL_GROUP_IDS and g.name == name:
                return gid
        return self.store.create_group(name).id

    def _apply_import(self, result, store_creds):
        self._log_import(f"— Import gestartet (Format {result.version}) —")
        # 1) Geräte in den Roster (merge erhält vorhandene Firmware/Modell)
        for cam in result.cameras:
            self.store.remember(cam)
        self._log_import(f"Geräte übernommen: {result.n_cameras}")

        # 2) Gruppen anlegen/ergänzen und Mitglieder zuweisen
        groups_new = 0
        for name, keys in result.groups.items():
            existed = any(gid not in VIRTUAL_GROUP_IDS and g.name == name
                          for gid, g in self.store.groups.items())
            gid = self._find_or_create_group(name)
            if not existed:
                groups_new += 1
            self.store.assign(gid, keys)
        self._log_import(f"Gruppen: {result.n_groups} verarbeitet "
                         f"({groups_new} neu, {result.n_groups - groups_new} ergänzt)")

        # 3) Zugangsdaten in den Tresor (ein Schreibvorgang)
        if store_creds:
            try:
                n = self.vault.set_many(result.credentials)
                self._log_import(f"Zugangsdaten im Tresor gespeichert: {n}")
            except VaultError as exc:
                self._log_import(f"Zugangsdaten NICHT gespeichert: {exc}")
        elif result.n_credentials:
            self._log_import("Zugangsdaten übersprungen.")

        self.store.save()
        for w in result.warnings:
            self._log_import("Hinweis: " + w)
        self._log_import("— Fertig —")
        self.data_changed = True
        messagebox.showinfo(
            "Import",
            f"Import abgeschlossen:\n{result.n_cameras} Geräte, "
            f"{result.n_groups} Gruppen.", parent=self)
