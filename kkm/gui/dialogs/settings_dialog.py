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

import os
import platform
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from kkm.gui import filedialogs as filedialog   # feste Dialoggröße

from kkm.core import (VIRTUAL_GROUP_IDS, VaultError, Capability,
                      t, LANGUAGES, get_language, language_label)
from kkm.core.backup import create_backup, restore_backup, BackupError
from kkm.core import updates
from kkm.gui.dialogs.vault_access import ensure_vault_unlocked
from kkm.version import __version__, APP_NAME, PROJECT_URL


def _dep_version(dist_name: str, module_name: str | None = None) -> str:
    """Version einer Abhängigkeit ermitteln (Paket-Metadaten, dann Modul-Attribut)."""
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version(dist_name)
        except PackageNotFoundError:
            pass
    except Exception:
        pass
    try:
        mod = __import__(module_name or dist_name)
        return getattr(mod, "__version__", "unbekannt")
    except Exception:
        return "nicht installiert"


class _CredentialsViewer(tk.Toplevel):
    """Read-only Ansicht der im Tresor gespeicherten Kamera-Zugangsdaten.

    Bekommt die bereits entschlüsselten Einträge (der Tresor ist entsperrt) als
    Liste ``(camera_key, username, password)``. Passwörter sind zunächst maskiert
    und lassen sich per Checkbox einblenden; ``Filter`` grenzt nach Schlüssel oder
    Benutzer ein; „Passwort kopieren" legt das Passwort der markierten Zeile in die
    Zwischenablage.
    """

    def __init__(self, parent, entries):
        super().__init__(parent)
        self.title(t("Gespeicherte Zugangsdaten"))
        self.transient(parent)
        self._entries = list(entries)          # [(key, user, password)]
        self._reveal = tk.BooleanVar(value=False)

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frame)
        top.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(top, text=t("Filter:")).pack(side=tk.LEFT)
        self._filter = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self._filter)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))
        self._filter.trace_add("write", lambda *_a: self._populate())
        ttk.Checkbutton(top, text=t("Passwörter anzeigen"), variable=self._reveal,
                        command=self._populate).pack(side=tk.LEFT)

        box = ttk.Frame(frame)
        box.pack(fill=tk.BOTH, expand=True)
        cols = ("key", "user", "pw")
        self._tree = ttk.Treeview(box, columns=cols, show="headings", height=12)
        self._tree.heading("key", text=t("Kamera (Schlüssel)"))
        self._tree.heading("user", text=t("Benutzer"))
        self._tree.heading("pw", text=t("Passwort"))
        self._tree.column("key", width=240)
        self._tree.column("user", width=120)
        self._tree.column("pw", width=160)
        scroll = ttk.Scrollbar(box, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.config(yscrollcommand=scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)
        self._tree.bind("<Double-Button-1>", lambda _e: self._reveal.set(True) or self._populate())

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(row, text=t("Passwort kopieren"),
                   command=self._copy_pw).pack(side=tk.LEFT)
        ttk.Button(row, text=t("Schließen"), command=self.destroy).pack(side=tk.RIGHT)

        self._populate()
        ent.focus_set()
        self.grab_set()

    def _populate(self):
        needle = self._filter.get().strip().casefold()
        reveal = self._reveal.get()
        self._tree.delete(*self._tree.get_children())
        for key, user, pw in self._entries:
            if needle and needle not in key.casefold() and needle not in user.casefold():
                continue
            shown = pw if reveal else ("•" * len(pw) if pw else "")
            self._tree.insert("", tk.END, values=(key, user, shown))

    def _copy_pw(self):
        sel = self._tree.selection()
        if not sel:
            return
        key = self._tree.item(sel[0], "values")[0]
        for k, _user, pw in self._entries:
            if k == key:
                self.clipboard_clear()
                self.clipboard_append(pw)
                self.update()          # Zwischenablage sofort wirksam
                break


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, *, vault, registry, settings, store, current_gid,
                 columns, fixed_columns=(), apply_columns=None,
                 theme_mode="dark", on_theme_change=None):
        super().__init__(parent)
        self.title(t("Einstellungen"))
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
        nb.add(self._build_appearance_tab(nb), text=t("Darstellung"))
        nb.add(self._build_vault_tab(nb), text=t("Tresor"))
        nb.add(self._build_plugins_tab(nb), text=t("Plugins"))
        nb.add(self._build_online_tab(nb), text=t("Online-Prüfung"))
        nb.add(self._build_columns_tab(nb), text=t("Spalten"))
        nb.add(self._build_firmware_tab(nb), text=t("Firmwareupdates"))
        nb.add(self._build_import_tab(nb), text=t("Import und Sicherung"))
        nb.add(self._build_about_tab(nb), text=t("Über"))
        nb.add(self._build_licenses_tab(nb), text=t("Lizenzen"))

        ttk.Button(self, text=t("Schließen"), command=self.destroy).pack(
            anchor=tk.E, padx=8, pady=(0, 8))

    # -------------------------------------------------------------- appearance
    def _build_appearance_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text=t("Erscheinungsbild:"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))
        self._theme_var = tk.StringVar(value=self.theme_mode)
        for val, text in (("dark", t("Dunkel")), ("light", t("Hell"))):
            ttk.Radiobutton(tab, text=text, value=val, variable=self._theme_var,
                            command=self._on_theme).pack(anchor=tk.W, pady=1)
        ttk.Label(tab, text=t("Modernes Sun-Valley-Design. Wirkt sofort.")).pack(
            anchor=tk.W, pady=(6, 0))

        # --- Sprache / Language ---
        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        ttk.Label(tab, text=t("Sprache / Language:"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        row = ttk.Frame(tab)
        row.pack(anchor=tk.W)
        # Anzeige = native Bezeichnung ("Deutsch"/"English"), intern der Code.
        self._lang_labels = {language_label(code): code for code, _ in LANGUAGES}
        self._lang_var = tk.StringVar(value=language_label(get_language()))
        ttk.Combobox(row, textvariable=self._lang_var, state="readonly", width=16,
                     values=[language_label(code) for code, _ in LANGUAGES]).pack(side=tk.LEFT)
        self._lang_var.trace_add("write", lambda *_: self._save_language())
        ttk.Label(tab, text=t("Wirkt beim nächsten Programmstart.")).pack(
            anchor=tk.W, pady=(4, 0))

        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        ttk.Label(tab, text=t("Fenster:"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self._start_max_var = tk.BooleanVar(
            value=bool(self.settings.get("start_maximized", False)))
        ttk.Checkbutton(tab, text=t("Beim Start maximiert öffnen"),
                        variable=self._start_max_var,
                        command=self._save_start_maximized).pack(anchor=tk.W)
        ttk.Label(tab, text=t("Wirkt beim nächsten Programmstart.")).pack(
            anchor=tk.W, pady=(2, 0))
        return tab

    def _on_theme(self):
        if self.on_theme_change:
            self.on_theme_change(self._theme_var.get())

    def _save_start_maximized(self):
        self.settings.set("start_maximized", bool(self._start_max_var.get()))

    def _save_language(self):
        code = self._lang_labels.get(self._lang_var.get(), "de")
        if code != self.settings.get("language", "de"):
            self.settings.set("language", code)
            messagebox.showinfo(
                t("Sprache / Language"),
                t("Die Sprache wird beim nächsten Programmstart übernommen."),
                parent=self)

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
            self._vault_status.config(text=t("Tresor nicht verfügbar."))
            return

        if not self.vault.exists:
            self._vault_status.config(text=t("Status: noch nicht angelegt"))
            self._pw_fields(self._vault_body,
                            [(t("Master-Passwort:"), "m1"), (t("Wiederholen:"), "m2")])
            ttk.Button(self._vault_body, text=t("Tresor anlegen"),
                       command=self._create_vault).grid(row=2, column=0, columnspan=2,
                                                        sticky=tk.W, pady=6)
        elif self.vault.is_locked:
            self._vault_status.config(text=t("Status: gesperrt 🔒"))
            self._pw_fields(self._vault_body, [(t("Master-Passwort:"), "m1")])
            ttk.Button(self._vault_body, text=t("Entsperren"),
                       command=self._unlock_vault).grid(row=1, column=0, columnspan=2,
                                                        sticky=tk.W, pady=6)
            self._autounlock_widgets(self._vault_body, start_row=2)
        else:
            self._vault_status.config(text=t("Status: entsperrt 🔓"))
            ttk.Button(self._vault_body, text=t("Sperren"),
                       command=self._lock_vault).grid(row=0, column=0, sticky=tk.W)
            ttk.Separator(self._vault_body, orient=tk.HORIZONTAL).grid(
                row=1, column=0, columnspan=2, sticky="ew", pady=8)
            ttk.Label(self._vault_body, text=t("Master-Passwort ändern:")).grid(
                row=2, column=0, columnspan=2, sticky=tk.W)
            self._pw_fields(self._vault_body,
                            [(t("Aktuell:"), "old"), (t("Neu:"), "m1"), (t("Wiederholen:"), "m2")],
                            start_row=3)
            ttk.Button(self._vault_body, text=t("Ändern"),
                       command=self._change_master).grid(row=6, column=0, columnspan=2,
                                                         sticky=tk.W, pady=6)
            ttk.Separator(self._vault_body, orient=tk.HORIZONTAL).grid(
                row=7, column=0, columnspan=2, sticky="ew", pady=8)
            self._autounlock_widgets(self._vault_body, start_row=8)
            ttk.Separator(self._vault_body, orient=tk.HORIZONTAL).grid(
                row=10, column=0, columnspan=2, sticky="ew", pady=8)
            ttk.Button(self._vault_body, text=t("Gespeicherte Zugangsdaten anzeigen…"),
                       command=self._show_stored_credentials).grid(
                row=11, column=0, columnspan=2, sticky=tk.W, pady=6)

    def _autounlock_widgets(self, parent, start_row):
        """Checkbox + Warnhinweis für die automatische Entsperrung beim Start."""
        from kkm.gui import theme
        self._auto_var = tk.BooleanVar(value=self.vault.autounlock_enabled)
        ttk.Checkbutton(parent, text=t("Tresor beim Programmstart automatisch entsperren"),
                        variable=self._auto_var,
                        command=self._toggle_autounlock).grid(
            row=start_row, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        ttk.Label(parent, wraplength=380, justify=tk.LEFT,
                  foreground=theme.CURRENT.get("warn", "#c0392b"),
                  text=t("Hinweis: Speichert das Master-Passwort gerätegebunden auf "
                         "diesem Rechner. Bequem, aber weniger sicher — wer als dieser "
                         "Benutzer Zugriff hat, kann den Tresor öffnen.")).grid(
            row=start_row + 1, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))

    def _toggle_autounlock(self):
        if self._auto_var.get():
            pw = simpledialog.askstring(
                t("Auto-Entsperrung"), t("Master-Passwort zur Bestätigung:"),
                show="*", parent=self)
            if not pw:
                self._auto_var.set(False)
                return
            try:
                self.vault.enable_autounlock(pw)
            except VaultError as exc:
                messagebox.showerror(t("Tresor"), str(exc), parent=self)
                self._auto_var.set(False)
                return
            messagebox.showinfo(
                t("Tresor"), t("Auto-Entsperrung aktiviert — der Tresor wird beim Start "
                "automatisch entsperrt."), parent=self)
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
            messagebox.showinfo(t("Tresor"), t("Bitte ein Master-Passwort eingeben."), parent=self)
            return
        if m1 != m2:
            messagebox.showerror(t("Tresor"), t("Die Passwörter stimmen nicht überein."), parent=self)
            return
        try:
            self.vault.create(m1)
        except VaultError as exc:
            messagebox.showerror(t("Tresor"), str(exc), parent=self)
            return
        messagebox.showinfo(t("Tresor"), t("Tresor angelegt und entsperrt."), parent=self)
        self._render_vault()

    def _unlock_vault(self):
        try:
            self.vault.unlock(self._pw_vars["m1"].get())
        except VaultError as exc:
            messagebox.showerror(t("Tresor"), str(exc), parent=self)
            return
        self._render_vault()

    def _lock_vault(self):
        self.vault.lock()
        self._render_vault()

    def _change_master(self):
        old, m1, m2 = (self._pw_vars["old"].get(), self._pw_vars["m1"].get(),
                       self._pw_vars["m2"].get())
        if m1 != m2:
            messagebox.showerror(t("Tresor"), t("Die neuen Passwörter stimmen nicht überein."),
                                 parent=self)
            return
        try:
            self.vault.change_master(old, m1)
        except VaultError as exc:
            messagebox.showerror(t("Tresor"), str(exc), parent=self)
            return
        messagebox.showinfo(t("Tresor"), t("Master-Passwort geändert."), parent=self)
        self._render_vault()

    def _show_stored_credentials(self):
        """Read-only Ansicht aller im Tresor gespeicherten Kamera-Zugangsdaten."""
        if self.vault is None or self.vault.is_locked:
            return
        entries = sorted(
            ((key, cred.get("username", ""), cred.get("password", ""))
             for key, cred in self.vault.all_entries().items()),
            key=lambda e: e[0].casefold())
        if not entries:
            messagebox.showinfo(t("Tresor"),
                                t("Es sind keine Zugangsdaten gespeichert."), parent=self)
            return
        _CredentialsViewer(self, entries)

    # ----------------------------------------------------------------- plugins
    def _build_plugins_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text=t("Hersteller-Plugins aktivieren/deaktivieren:")).pack(anchor=tk.W)
        self._plugin_vars = {}
        has_experimental = False
        for plugin in self.registry.all():
            var = tk.BooleanVar(value=self.registry.is_enabled(plugin.id))
            self._plugin_vars[plugin.id] = var
            label = plugin.name
            if getattr(plugin, "experimental", False):
                label += t("  (experimentell)")
                has_experimental = True
            ttk.Checkbutton(tab, text=label, variable=var,
                            command=self._save_plugins).pack(anchor=tk.W, pady=2)
        if has_experimental:
            from kkm.gui import theme
            ttk.Label(
                tab, wraplength=460, justify=tk.LEFT,
                foreground=theme.CURRENT.get("warn", "#c0392b"),
                text=t("⚠ Experimentelle Plugins sind noch nicht an echter Hardware "
                       "geprüft — Schreib-Aktionen (IP, Benutzer, Firmware, Reset) auf "
                       "eigene Gefahr verwenden."),
            ).pack(anchor=tk.W, pady=(8, 0))

        from kkm.gui import theme
        ttk.Separator(tab).pack(fill=tk.X, pady=10)
        ttk.Label(tab, text=t("Verbindungssicherheit:")).pack(anchor=tk.W)
        self._basic_http_var = tk.BooleanVar(
            value=bool(self.settings.get("allow_basic_over_http", False)))
        ttk.Checkbutton(tab, text=t("Basic-Anmeldung über unverschlüsseltes HTTP erlauben "
                                    "(unsicher)"),
                        variable=self._basic_http_var,
                        command=self._save_basic_http).pack(anchor=tk.W, pady=2)
        ttk.Label(
            tab, wraplength=460, justify=tk.LEFT,
            foreground=theme.CURRENT.get("warn", "#c0392b"),
            text=t("Bei Basic-Anmeldung über HTTP geht das Kamera-Passwort im Klartext "
                   "über das Netz. Ohne Haken wird über HTTP nur Digest verwendet; nur "
                   "für alte Geräte aktivieren, die weder HTTPS noch Digest können."),
        ).pack(anchor=tk.W, pady=(2, 0))

        self._pinning_var = tk.BooleanVar(value=bool(self.settings.get("cert_pinning", True)))
        ttk.Checkbutton(tab, text=t("Kamera-Zertifikate beim ersten Kontakt merken und bei "
                                    "Änderung nachfragen (empfohlen)"),
                        variable=self._pinning_var,
                        command=self._save_pinning).pack(anchor=tk.W, pady=(10, 2))
        ttk.Label(
            tab, wraplength=460, justify=tk.LEFT,
            text=t("Schützt vor dem Abfangen der Verbindung (Man-in-the-Middle): Ändert "
                   "sich das HTTPS-Zertifikat einer bekannten Kamera, werden keine "
                   "Zugangsdaten gesendet und das Programm fragt nach. Nach Werksreset "
                   "und Firmware-Update über das Programm wird das neue Zertifikat "
                   "automatisch übernommen."),
        ).pack(anchor=tk.W, pady=(2, 0))
        row = ttk.Frame(tab)
        row.pack(anchor=tk.W, pady=(6, 0))
        self._pinned_label = ttk.Label(row)
        self._pinned_label.pack(side=tk.LEFT)
        ttk.Button(row, text=t("Alle vergessen"), command=self._forget_all_certs).pack(
            side=tk.LEFT, padx=8)
        self._render_pinned()
        return tab

    def _save_pinning(self):
        from kkm.core import certpin
        enabled = self._pinning_var.get()
        self.settings.set("cert_pinning", enabled)
        certpin.set_enabled(enabled)

    def _render_pinned(self):
        from kkm.core import certpin
        self._pinned_label.config(
            text=t("Gespeicherte Zertifikate: {n}", n=len(certpin.STORE.keys())))

    def _forget_all_certs(self):
        from kkm.core import certpin
        if not messagebox.askyesno(
                t("Einstellungen"),
                t("Alle gespeicherten Kamera-Zertifikate vergessen? Sie werden beim "
                  "nächsten Kontakt neu gespeichert (ohne Prüfung)."), parent=self):
            return
        certpin.STORE.clear()
        self._render_pinned()

    def _save_plugins(self):
        for pid, var in self._plugin_vars.items():
            self.registry.set_enabled(pid, var.get())
        self.settings.set("enabled_plugins", self.registry.enabled_ids())

    def _save_basic_http(self):
        from kkm.plugins import set_basic_over_http
        allowed = self._basic_http_var.get()
        self.settings.set("allow_basic_over_http", allowed)
        set_basic_over_http(allowed)

    # ----------------------------------------------------------------- online
    def _build_online_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        g = self.store.groups.get(self.current_gid)
        name = g.name if g else "?"
        ttk.Label(tab, text=t("Online-Prüfung für Gruppe: {name}", name=name),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self._online_on = tk.BooleanVar(value=bool(g and g.online_check))
        ttk.Checkbutton(tab, text=t("Automatische Online-Prüfung aktiv"),
                        variable=self._online_on,
                        command=self._save_online).pack(anchor=tk.W)
        row = ttk.Frame(tab)
        row.pack(anchor=tk.W, pady=4)
        ttk.Label(row, text=t("Intervall (Sekunden):")).pack(side=tk.LEFT)
        self._online_interval = tk.IntVar(value=(g.online_interval if g else 60))
        sp = ttk.Spinbox(row, from_=5, to=3600, width=7,
                         textvariable=self._online_interval, command=self._save_online)
        sp.pack(side=tk.LEFT, padx=4)
        sp.bind("<FocusOut>", lambda _e: self._save_online())
        ttk.Label(tab, text=t("Gilt je Gruppe; im Hauptfenster wird die jeweils "
                              "gewählte Gruppe automatisch geprüft.")).pack(anchor=tk.W, pady=(6, 0))
        return tab

    def _save_online(self):
        self.store.set_online_check(self.current_gid, self._online_on.get(),
                                    self._online_interval.get())

    # ----------------------------------------------------------------- columns
    def _build_columns_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text=t("Sichtbare Spalten der Geräteliste:")).pack(anchor=tk.W)
        hidden = set(self.settings.get("hidden_columns", []))
        self._col_vars = {}
        for col in self.columns:
            var = tk.BooleanVar(value=col not in hidden)
            self._col_vars[col] = var
            state = tk.DISABLED if col in self.fixed_columns else tk.NORMAL
            ttk.Checkbutton(tab, text=t(col), variable=var, state=state,
                            command=self._save_columns).pack(anchor=tk.W, pady=1)
        return tab

    def _save_columns(self):
        hidden = [c for c, v in self._col_vars.items()
                  if not v.get() and c not in self.fixed_columns]
        self.settings.set("hidden_columns", hidden)
        if self.apply_columns:
            self.apply_columns(hidden)

    # -------------------------------------------------------------- firmwareupdates
    def _build_firmware_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text=t("Firmware-Updates"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self._fw_parallel = tk.BooleanVar(
            value=bool(self.settings.get("firmware_parallel", True)))
        ttk.Checkbutton(
            tab, text=t("Firmware-Updates parallel ausführen (statt nacheinander)"),
            variable=self._fw_parallel, command=self._save_firmware).pack(anchor=tk.W)

        row = ttk.Frame(tab)
        row.pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(row, text=t("Maximal gleichzeitig:")).pack(side=tk.LEFT)
        self._fw_max = tk.IntVar(
            value=int(self.settings.get("firmware_max_parallel", 4) or 4))
        self._fw_max_spin = ttk.Spinbox(
            row, from_=1, to=32, width=5, textvariable=self._fw_max,
            command=self._save_firmware)
        self._fw_max_spin.pack(side=tk.LEFT, padx=6)
        self._fw_max_spin.bind("<FocusOut>", lambda _e: self._save_firmware())

        ttk.Label(
            tab, justify=tk.LEFT, wraplength=460,
            text=t("Ist die Option aktiv, werden mehrere ausgewählte Kameras "
                   "gleichzeitig aktualisiert (bis zur angegebenen Anzahl), statt eine "
                   "nach der anderen. Das verkürzt Sammel-Updates deutlich, da bei "
                   "jeder Kamera auf den Neustart gewartet wird.")).pack(
            anchor=tk.W, pady=(8, 0))

        # --- Online-Update-Suche ---
        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(tab, text=t("Update-Suche"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self._fw_online = tk.BooleanVar(
            value=bool(self.settings.get("firmware_check_online", True)))
        ttk.Checkbutton(
            tab, text=t("Im Firmware-Dialog online nach Updates suchen"),
            variable=self._fw_online, command=self._save_firmware).pack(anchor=tk.W)

        self._fw_track = tk.BooleanVar(
            value=bool(self.settings.get("firmware_prefer_track", True)))
        ttk.Checkbutton(
            tab, text=t("Vorschlag in der Hauptversion der Kamera belassen (LTS-treu)"),
            variable=self._fw_track, command=self._save_firmware).pack(anchor=tk.W)

        row2 = ttk.Frame(tab)
        row2.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row2, text=t("Firmware-Verzeichnis:")).pack(side=tk.LEFT)
        self._fw_url = tk.StringVar(value=self.settings.get("firmware_repo_url", "") or "")
        entry = ttk.Entry(row2, textvariable=self._fw_url, width=42)
        entry.pack(side=tk.LEFT, padx=6)
        entry.bind("<FocusOut>", lambda _e: self._save_firmware())

        row3 = ttk.Frame(tab)
        row3.pack(fill=tk.X, pady=(6, 0))
        self._fw_cache_btn = ttk.Button(row3, text=t("Firmware-Cache leeren"),
                                        command=self._clear_fw_cache)
        self._fw_cache_btn.pack(side=tk.LEFT)
        self._fw_cache_lbl = ttk.Label(row3, text="")
        self._fw_cache_lbl.pack(side=tk.LEFT, padx=8)
        self._update_cache_label()

        ttk.Label(
            tab, justify=tk.LEFT, wraplength=460,
            text=t("Die Suche liest das öffentliche Firmware-Verzeichnis des Herstellers "
                   "(Axis: ftp.axis.com) und vergleicht die dort liegenden Versionen mit "
                   "der Firmware der Kameras. Heruntergeladene Dateien landen in einem "
                   "Cache und werden dem Modell wie eine selbst gewählte Datei zugewiesen. "
                   "Leeres Verzeichnisfeld = Vorgabe des Plugins; hier lässt sich ein "
                   "interner Spiegel eintragen.")).pack(anchor=tk.W, pady=(8, 0))

        self._update_fw_state()
        return tab

    def _repo_plugins(self):
        """Plugins mit eigener Update-Suche — nur die haben einen Firmware-Cache."""
        return [p for p in self.registry.all()
                if p.supports(Capability.FIRMWARE_CHECK)]

    def _update_cache_label(self):
        try:
            size = sum(p.firmware_cache_size() for p in self._repo_plugins())
        except OSError:
            size = 0
        self._fw_cache_lbl.config(
            text=t("leer") if not size
            else t("{mb:.0f} MB belegt", mb=size / (1024 * 1024)))

    def _clear_fw_cache(self):
        for plugin in self._repo_plugins():
            plugin.clear_firmware_cache()
        self._update_cache_label()

    def _update_fw_state(self):
        state = "normal" if self._fw_parallel.get() else "disabled"
        self._fw_max_spin.config(state=state)

    def _save_firmware(self):
        self.settings.set("firmware_parallel", bool(self._fw_parallel.get()))
        try:
            n = max(1, min(32, int(self._fw_max.get())))
        except (tk.TclError, ValueError):
            n = 4
        self.settings.set("firmware_max_parallel", n)
        self.settings.set("firmware_check_online", bool(self._fw_online.get()))
        self.settings.set("firmware_prefer_track", bool(self._fw_track.get()))
        self.settings.set("firmware_repo_url", self._fw_url.get().strip())
        self._update_fw_state()

    # ------------------------------------------------------------------ import
    def _build_import_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        # Der ADM-Import ist eine reine Axis-Sache (Exportformat des AXIS Device
        # Manager) — ohne Axis-Plugin gibt es den Abschnitt schlicht nicht. Die
        # Sicherung darunter ist herstellerneutral und immer da.
        self._import_creds_var = tk.BooleanVar(value=True)
        if self.registry.get("axis") is not None:
            ttk.Label(tab, text=t("Import aus AXIS Device Manager"),
                      font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
            ttk.Label(tab, justify=tk.LEFT, text=t(
                "Übernimmt Geräte und Gruppen aus einer AXIS-Device-Manager-Export-"
                "datei (JSON, Format 1.x und 2.x). Vorhandene Gruppen gleichen Namens "
                "werden ergänzt, Geräte anhand ihrer MAC/Seriennummer zusammengeführt.\n"
                "Enthaltene Zugangsdaten werden — sofern vorhanden — in den Tresor "
                "übernommen (dazu muss er entsperrt sein).")
            ).pack(anchor=tk.W, pady=(2, 8), fill=tk.X)

            ttk.Checkbutton(tab, text=t("Zugangsdaten in den Tresor übernehmen"),
                            variable=self._import_creds_var).pack(anchor=tk.W)

            ttk.Button(tab, text=t("Export-Datei wählen und importieren…"),
                       command=self._run_import).pack(anchor=tk.W, pady=(8, 6))

        # --- Sicherung (Daten + Tresor) als eine verschlüsselte Datei ---------
        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        ttk.Label(tab, text=t("Sicherung (Daten + Passwort-Tresor)"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(tab, justify=tk.LEFT, text=t(
            "Sichert Gruppen, Geräte und den Passwort-Tresor in EINE verschlüsselte "
            "Datei (.kkmbackup, mit Backup-Passwort, plattformübergreifend). "
            "Wiederherstellen überschreibt die aktuellen Daten.")
        ).pack(anchor=tk.W, pady=(2, 8), fill=tk.X)
        brow = ttk.Frame(tab)
        brow.pack(anchor=tk.W, pady=(0, 6))
        ttk.Button(brow, text=t("Sicherung exportieren…"),
                   command=self._run_backup_export).pack(side=tk.LEFT)
        ttk.Button(brow, text=t("Sicherung wiederherstellen…"),
                   command=self._run_backup_restore).pack(side=tk.LEFT, padx=6)

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
            parent=self, title=t("AXIS-Device-Manager-Export wählen"),
            filetypes=[(t("AXIS-Export (JSON)"), "*.json"), (t("Alle Dateien"), "*.*")])
        if not path:
            return
        # Import-Parser erst hier laden (zieht das axis-Paket / zeroconf nach).
        from kkm.plugins.axis.adm_import import parse_export, AdmImportError
        try:
            result = parse_export(path)
        except AdmImportError as exc:
            messagebox.showerror(t("Import"), str(exc), parent=self)
            return

        summary = (t("Datei-Format {version}", version=result.version) + "\n"
                   + t("  Geräte: {n}", n=result.n_cameras) + "\n"
                   + t("  Gruppen: {n}", n=result.n_groups) + "\n"
                   + t("  Zugangsdaten: {n}", n=result.n_credentials))
        if not messagebox.askyesno(
                t("Import bestätigen"),
                summary + "\n\n" + t("Jetzt importieren?"), parent=self):
            return

        # Zugangsdaten -> Tresor entsperren (wenn gewünscht und vorhanden)
        want_creds = self._import_creds_var.get() and result.n_credentials > 0
        store_creds = False
        if want_creds:
            if ensure_vault_unlocked(self, self.vault,
                                     t("Zum Übernehmen der Zugangsdaten")):
                store_creds = True
            elif not messagebox.askyesno(
                    t("Import"),
                    t("Der Tresor ist gesperrt. Ohne Übernahme der Zugangsdaten "
                      "fortfahren?"), parent=self):
                return

        self._apply_import(result, store_creds)

    def _find_or_create_group(self, name):
        """Gruppe gleichen Namens finden (außer 'Alle Kameras') oder neu anlegen."""
        for gid, g in self.store.groups.items():
            if gid not in VIRTUAL_GROUP_IDS and g.name == name:
                return gid
        return self.store.create_group(name).id

    def _apply_import(self, result, store_creds):
        self._log_import(t("— Import gestartet (Format {version}) —", version=result.version))
        # 1) Geräte in den Roster (merge erhält vorhandene Firmware/Modell)
        for cam in result.cameras:
            self.store.remember(cam)
        self._log_import(t("Geräte übernommen: {n}", n=result.n_cameras))

        # 2) Gruppen anlegen/ergänzen und Mitglieder zuweisen
        groups_new = 0
        for name, keys in result.groups.items():
            existed = any(gid not in VIRTUAL_GROUP_IDS and g.name == name
                          for gid, g in self.store.groups.items())
            gid = self._find_or_create_group(name)
            if not existed:
                groups_new += 1
            self.store.assign(gid, keys)
        self._log_import(t("Gruppen: {n} verarbeitet ({new} neu, {merged} ergänzt)",
                           n=result.n_groups, new=groups_new,
                           merged=result.n_groups - groups_new))

        # 3) Zugangsdaten in den Tresor (ein Schreibvorgang)
        if store_creds:
            try:
                n = self.vault.set_many(result.credentials)
                self._log_import(t("Zugangsdaten im Tresor gespeichert: {n}", n=n))
            except VaultError as exc:
                self._log_import(t("Zugangsdaten NICHT gespeichert: {err}", err=exc))
        elif result.n_credentials:
            self._log_import(t("Zugangsdaten übersprungen."))

        self.store.save()
        for w in result.warnings:
            self._log_import(t("Hinweis: ") + w)
        self._log_import(t("— Fertig —"))
        self.data_changed = True
        messagebox.showinfo(
            t("Import"),
            t("Import abgeschlossen:\n{cams} Geräte, {groups} Gruppen.",
              cams=result.n_cameras, groups=result.n_groups), parent=self)

    # ------------------------------------------------------------- backup (7z-Ersatz)
    def _config_dir(self) -> str:
        """Verzeichnis mit groups.json / settings.json / vault.enc."""
        return os.path.dirname(self.store.path)

    def _ask_new_password(self, title: str) -> str | None:
        """Backup-Passwort zweimal abfragen (Bestätigung). None bei Abbruch."""
        pw = simpledialog.askstring(title, t("Backup-Passwort:"), show="*", parent=self)
        if not pw:
            if pw == "":
                messagebox.showinfo(title, t("Kein Passwort eingegeben — abgebrochen."),
                                    parent=self)
            return None
        again = simpledialog.askstring(title, t("Passwort wiederholen:"), show="*",
                                       parent=self)
        if again != pw:
            messagebox.showerror(title, t("Die Passwörter stimmen nicht überein."),
                                 parent=self)
            return None
        return pw

    def _run_backup_export(self):
        path = filedialog.asksaveasfilename(
            parent=self, title=t("Sicherung speichern"),
            defaultextension=".kkmbackup",
            filetypes=[(t("KKM-Sicherung"), "*.kkmbackup"), (t("Alle Dateien"), "*.*")])
        if not path:
            return
        pw = self._ask_new_password(t("Sicherung exportieren"))
        if pw is None:
            return
        try:
            included = create_backup(path, pw, self._config_dir())
        except BackupError as exc:
            messagebox.showerror(t("Sicherung"), str(exc), parent=self)
            return
        self._log_import(t("Sicherung exportiert: {file} ({parts})",
                           file=os.path.basename(path), parts=", ".join(included)))
        messagebox.showinfo(
            t("Sicherung"),
            t("Sicherung erstellt:\n{path}\n\nEnthalten: {parts}\n\n"
              "Bewahre die Datei und das Backup-Passwort sicher auf.",
              path=path, parts=", ".join(included)), parent=self)

    def _run_backup_restore(self):
        if not messagebox.askyesno(
                t("Sicherung wiederherstellen"),
                t("Die aktuellen Gruppen, Geräte und der Passwort-Tresor werden durch "
                  "den Inhalt der Sicherung ERSETZT.\n\nFortfahren?"), parent=self):
            return
        path = filedialog.askopenfilename(
            parent=self, title=t("Sicherung wählen"),
            filetypes=[(t("KKM-Sicherung"), "*.kkmbackup"), (t("Alle Dateien"), "*.*")])
        if not path:
            return
        pw = simpledialog.askstring(t("Sicherung wiederherstellen"),
                                    t("Backup-Passwort:"), show="*", parent=self)
        if not pw:
            return
        try:
            restored = restore_backup(path, pw, self._config_dir())
        except BackupError as exc:
            messagebox.showerror(t("Sicherung"), str(exc), parent=self)
            return

        # In-Memory-Objekte an die neuen Dateien angleichen (sonst würde ein späterer
        # save() die gerade eingespielten Daten wieder überschreiben).
        self.store.load()
        self.settings.load()
        # Verbindungssicherheit aus der Sicherung sofort wirksam machen.
        from kkm.core import certpin
        from kkm.plugins import set_basic_over_http
        self._basic_http_var.set(bool(self.settings.get("allow_basic_over_http", False)))
        self._pinning_var.set(bool(self.settings.get("cert_pinning", True)))
        set_basic_over_http(self._basic_http_var.get())
        certpin.set_enabled(self._pinning_var.get())
        self._render_pinned()        # known_certs.json liest der CertStore ohnehin frisch
        if self.vault is not None:
            self.vault.lock()   # neuer Tresor -> mit Backup-Master-Passwort entsperren
            if "vault.enc" in restored:
                # Altes, gerätegebundenes Auto-Entsperr-Token passt nicht mehr zum
                # eingespielten Tresor -> entfernen (sonst stiller Fehlversuch).
                self.vault.disable_autounlock()
        # Sichtbare Einstellungen sofort übernehmen.
        if self.apply_columns:
            self.apply_columns(self.settings.get("hidden_columns", []))
        new_theme = self.settings.get("theme", "dark")
        if self.on_theme_change and new_theme != self.theme_mode:
            self.on_theme_change(new_theme)
            self.theme_mode = new_theme
        self.data_changed = True

        self._log_import(t("Sicherung wiederhergestellt: {parts}",
                           parts=", ".join(restored)))
        note = ""
        if "vault.enc" in restored:
            note = "\n\n" + t("Der Tresor ist jetzt gesperrt — mit dem Master-Passwort "
                              "aus der Sicherung entsperren.")
        messagebox.showinfo(
            t("Sicherung"),
            t("Wiederherstellung abgeschlossen ({parts}).", parts=", ".join(restored))
            + note + "\n\n"
            + t("Hinweis: Bei geänderter Plugin-Auswahl das Programm neu starten."),
            parent=self)

    # -------------------------------------------------------------------- über
    def _build_about_tab(self, parent):
        tab = ttk.Frame(parent, padding=12)

        ttk.Label(tab, text=APP_NAME.replace("_", " "),
                  font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(tab, text=t("Version {v}", v=__version__)).pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(tab, text=t("Erstellt von Mirik · GPL-3.0-or-later")).pack(anchor=tk.W)

        prow = ttk.Frame(tab)
        prow.pack(anchor=tk.W, pady=(2, 0))
        ttk.Label(prow, text=t("Projektseite:")).pack(side=tk.LEFT, padx=(0, 6))
        plink = ttk.Label(prow, text=PROJECT_URL)
        plink.pack(side=tk.LEFT)
        self._make_link(plink, PROJECT_URL)

        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        ttk.Label(tab, text=t("Verwendete Komponenten"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))

        try:
            tcltk = self.tk.call("info", "patchlevel")
        except tk.TclError:
            tcltk = t("unbekannt")
        components = [
            ("Python", platform.python_version()),
            ("Tcl/Tk", str(tcltk)),
            ("zeroconf", _dep_version("zeroconf")),
            ("cryptography", _dep_version("cryptography")),
            ("sv-ttk", _dep_version("sv-ttk", "sv_ttk")),
        ]
        grid = ttk.Frame(tab)
        grid.pack(anchor=tk.W)
        for i, (name, ver) in enumerate(components):
            ttk.Label(grid, text=name + ":").grid(row=i, column=0, sticky=tk.W,
                                                  padx=(0, 12), pady=1)
            ttk.Label(grid, text=ver).grid(row=i, column=1, sticky=tk.W, pady=1)

        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        ttk.Label(tab, text=t("Updates"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self._check_updates_var = tk.BooleanVar(
            value=bool(self.settings.get("check_updates", True)))
        ttk.Checkbutton(tab, text=t("Beim Programmstart nach Updates suchen (fragt GitHub)"),
                        variable=self._check_updates_var,
                        command=self._save_check_updates).pack(anchor=tk.W)
        urow = ttk.Frame(tab)
        urow.pack(anchor=tk.W, pady=(4, 0))
        self._update_btn = ttk.Button(urow, text=t("Jetzt nach Updates suchen"),
                                      command=self._check_updates_now)
        self._update_btn.pack(side=tk.LEFT)
        self._update_status = ttk.Label(tab, wraplength=460, justify=tk.LEFT)
        self._update_status.pack(anchor=tk.W, pady=(4, 0))

        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        from kkm.gui import theme
        from kkm.gui.dialogs.disclaimer import DISCLAIMER_TEXT
        ttk.Label(tab, justify=tk.LEFT, wraplength=460, text=t(DISCLAIMER_TEXT),
                  foreground=theme.CURRENT.get("warn", "#c0392b"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)

        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        ttk.Label(tab, justify=tk.LEFT, wraplength=460, text=t(
            "Dieses Programm wurde mit Unterstützung von künstlicher Intelligenz "
            "(Claude von Anthropic) entwickelt.")).pack(anchor=tk.W)
        return tab

    # ------------------------------------------------------------- links/updates
    @staticmethod
    def _open_url(url: str) -> None:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - Browser-Start darf nie zum Absturz fuehren
            pass

    def _make_link(self, label: tk.Widget, url: str) -> None:
        """Ein Label wie einen Link aussehen und beim Klick den Browser oeffnen lassen."""
        label.configure(foreground="#2f81f7", cursor="hand2",
                        font=("TkDefaultFont", 10, "underline"))
        label.bind("<Button-1>", lambda _e: self._open_url(url))

    def _save_check_updates(self) -> None:
        self.settings.set("check_updates", bool(self._check_updates_var.get()))

    def _check_updates_now(self) -> None:
        self._update_btn.config(state=tk.DISABLED)
        self._update_status.config(text=t("Suche nach Updates …"))
        # Netzabfrage im Hintergrund, Ergebnis ueber after() zurueck in den UI-Thread.
        threading.Thread(target=self._worker_check_updates, daemon=True).start()

    def _worker_check_updates(self) -> None:
        rel = updates.latest_release()
        self.after(0, lambda: self._show_update_result(rel))

    def _show_update_result(self, rel: dict | None) -> None:
        if not self.winfo_exists():
            return
        self._update_btn.config(state=tk.NORMAL)
        lbl = self._update_status
        lbl.unbind("<Button-1>")
        lbl.configure(foreground="", cursor="", font=("TkDefaultFont", 10))
        if rel is None:
            lbl.config(text=t("Keine Verbindung zu GitHub — bitte später erneut versuchen."))
        elif updates.is_newer(rel["version"]):
            lbl.config(text=t("Neue Version verfügbar: {v} — hier herunterladen.",
                              v=rel["version"]))
            self._make_link(lbl, rel.get("url", PROJECT_URL))
        else:
            lbl.config(text=t("Sie verwenden die aktuelle Version ({v}).", v=__version__))

    # ---------------------------------------------------------------- lizenzen
    @staticmethod
    def _read_doc(name: str) -> str | None:
        """Datei aus dem Programmwurzel-Verzeichnis lesen (LICENSE etc.).

        Neben ``main.py`` gebündelt: im AppImage/Quelllauf im Wurzelverzeichnis,
        im PyInstaller-Build unter ``sys._MEIPASS`` (vgl. ``_open_help``)."""
        import sys
        from pathlib import Path
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", "."))
        else:
            base = Path(__file__).resolve().parents[3]   # <root>/ bzw. AppImage app/
        try:
            return (base / name).read_text(encoding="utf-8")
        except OSError:
            return None

    def _build_licenses_tab(self, parent):
        tab = ttk.Frame(parent, padding=10)
        ttk.Label(tab, text=t("Lizenzen der verwendeten Komponenten"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(tab, justify=tk.LEFT, wraplength=460, text=t(
            "Der eigene Programmcode steht unter der GPL-3.0-or-later. Das "
            "ausgelieferte Programm bündelt zusätzlich die unten aufgeführten "
            "Komponenten mit ihren jeweiligen Lizenzen.")).pack(anchor=tk.W, pady=(0, 6))

        box = ttk.Frame(tab)
        box.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(box, orient=tk.VERTICAL)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(box, wrap=tk.WORD, yscrollcommand=scroll.set,
                      padx=8, pady=8, height=18, width=70)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=txt.yview)

        missing = t("(Datei nicht gefunden.)")
        third = self._read_doc("THIRD_PARTY_LICENSES.md") or missing
        gpl = self._read_doc("LICENSE") or missing
        sep = "=" * 70
        content = (third + "\n\n" + sep + "\n"
                   + t("Vollständiger Lizenztext dieses Programms (GNU GPL v3):")
                   + "\n" + sep + "\n\n" + gpl)
        txt.insert("1.0", content)
        txt.config(state=tk.DISABLED)
        return tab
