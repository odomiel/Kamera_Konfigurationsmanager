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

"""Tresor bei Bedarf einsatzbereit machen.

Wird aufgerufen, wenn Passwörter gespeichert werden sollen, der Tresor aber noch
gesperrt oder gar nicht angelegt ist. Bietet an, ihn jetzt anzulegen (Master-
Passwort festlegen) bzw. zu entsperren. Muss auf dem Main-Thread laufen (öffnet
Tk-Dialoge). Gibt True zurück, wenn der Tresor danach nutzbar (entsperrt) ist.
"""

from __future__ import annotations

from tkinter import simpledialog, messagebox

from kkm.core import VaultError


def ensure_vault_unlocked(parent, vault, reason: str = "Zum Speichern der Passwörter") -> bool:
    if vault is None:
        return False
    if not vault.is_locked:
        return True

    if not vault.exists:
        if not messagebox.askyesno(
                "Passwort-Tresor",
                f"{reason} muss der Tresor zuerst angelegt werden.\n"
                "Jetzt ein Master-Passwort festlegen?", parent=parent):
            return False
        pw1 = simpledialog.askstring("Tresor anlegen", "Master-Passwort:",
                                     show="*", parent=parent)
        if not pw1:
            return False
        pw2 = simpledialog.askstring("Tresor anlegen", "Master-Passwort wiederholen:",
                                     show="*", parent=parent)
        if pw1 != pw2:
            messagebox.showerror("Tresor", "Die Passwörter stimmen nicht überein.",
                                 parent=parent)
            return False
        try:
            vault.create(pw1)
        except VaultError as exc:
            messagebox.showerror("Tresor", str(exc), parent=parent)
            return False
        return True

    # existiert, aber gesperrt
    if not messagebox.askyesno(
            "Passwort-Tresor",
            f"{reason} muss der Tresor entsperrt werden.\nJetzt entsperren?",
            parent=parent):
        return False
    pw = simpledialog.askstring("Tresor entsperren", "Master-Passwort:",
                                show="*", parent=parent)
    if not pw:
        return False
    try:
        vault.unlock(pw)
    except VaultError as exc:
        messagebox.showerror("Tresor", str(exc), parent=parent)
        return False
    return True
