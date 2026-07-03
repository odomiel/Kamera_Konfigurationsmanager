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

"""Datei-Dialoge — nach Möglichkeit der **native System-Dialog**.

Unter Linux verwendet Tk einen eigenen, in Tcl geschriebenen Dateidialog, der seine
Größe an den Ordnerpfad anpasst (unruhig, nicht vom Nutzer fixierbar). Ist ein
natives Werkzeug vorhanden (``zenity`` für GTK/GNOME, ``kdialog`` für KDE), wird
stattdessen der **System-Dateidialog** genutzt — der sich normal verhält und seine
Größe merkt.

- Auf **Windows/macOS** verwendet ``tkinter.filedialog`` ohnehin den nativen Dialog;
  dort (und wenn kein zenity/kdialog gefunden wird) fallen wir auf ``tkinter``
  zurück und fixieren dessen Größe wenigstens beim Öffnen.
- Beim Start des externen Programms aus einem **AppImage** wird die vom AppImage
  gesetzte ``LD_LIBRARY_PATH``/``PYTHON*`` aus der Umgebung entfernt, damit das
  System-Werkzeug seine eigenen (System-)Bibliotheken lädt.

Die Rückgabewerte entsprechen ``tkinter.filedialog`` (Pfad-String, ``""`` bei
Abbruch).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog

# --------------------------------------------------------------------- native tool
def _find_native() -> str | None:
    if not sys.platform.startswith("linux"):
        return None            # Windows/macOS: tkinter ist bereits nativ
    for tool in ("zenity", "qarma", "kdialog"):
        path = shutil.which(tool)
        if path:
            return tool
    return None


_NATIVE = _find_native()


def _clean_env() -> dict:
    """Umgebung für das externe Programm: AppImage-spezifische Bibliothekspfade
    entfernen, damit das System-Werkzeug seine eigenen Bibliotheken lädt."""
    env = dict(os.environ)
    for var in ("LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONHOME", "PYTHONPATH",
                "GTK_PATH", "GDK_PIXBUF_MODULE_FILE", "GIO_MODULE_DIR",
                "GSETTINGS_SCHEMA_DIR"):
        env.pop(var, None)
    # Falls das AppImage die Originalwerte gesichert hat, wiederherstellen.
    for var in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"):
        orig = os.environ.get(var + "_ORIG")
        if orig:
            env[var] = orig
    return env


def _initial_filename(initialdir, initialfile) -> str:
    if initialfile:
        return os.path.join(initialdir or "", initialfile)
    if initialdir:
        return os.path.join(initialdir, "")   # Ordner (trailing slash)
    return ""


# ----------------------------------------------------------------------- zenity
def _zenity_filters(filetypes):
    args = []
    for entry in filetypes or ():
        try:
            label, patterns = entry
        except (ValueError, TypeError):
            continue
        pats = patterns if isinstance(patterns, (list, tuple)) else [patterns]
        norm = ["*" if str(p).strip() in ("*.*", "") else str(p).strip()
                for p in pats]
        args.append(f"--file-filter={label} | {' '.join(norm)}")
    return args


def _zenity(save, title, initialdir, initialfile, filetypes, defaultextension):
    cmd = ["zenity" if _NATIVE == "zenity" else _NATIVE, "--file-selection"]
    if save:
        cmd += ["--save", "--confirm-overwrite"]
    if title:
        cmd.append(f"--title={title}")
    fn = _initial_filename(initialdir, initialfile)
    if fn:
        cmd.append(f"--filename={fn}")
    cmd += _zenity_filters(filetypes)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=_clean_env())
    except (OSError, ValueError):
        return None            # Start fehlgeschlagen -> Fallback auf tkinter
    if proc.returncode != 0:   # 1 = Abbruch, 5 = Timeout, o. Ä.
        return ""
    path = (proc.stdout or "").strip().splitlines()
    path = path[0].strip() if path else ""
    if path and save and defaultextension and not os.path.splitext(path)[1]:
        path += defaultextension
    return path


# ----------------------------------------------------------------------- kdialog
def _kdialog_filter(filetypes):
    parts = []
    for entry in filetypes or ():
        try:
            label, patterns = entry
        except (ValueError, TypeError):
            continue
        pats = patterns if isinstance(patterns, (list, tuple)) else [patterns]
        norm = ["*" if str(p).strip() in ("*.*", "") else str(p).strip()
                for p in pats]
        parts.append(f"{' '.join(norm)}|{label}")
    return "\n".join(parts)


def _kdialog(save, title, initialdir, initialfile, filetypes, defaultextension):
    start = _initial_filename(initialdir, initialfile) or os.path.expanduser("~")
    cmd = ["kdialog",
           "--getsavefilename" if save else "--getopenfilename",
           start, _kdialog_filter(filetypes)]
    if title:
        cmd += ["--title", title]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=_clean_env())
    except (OSError, ValueError):
        return None
    if proc.returncode != 0:
        return ""
    path = (proc.stdout or "").strip().splitlines()
    path = path[0].strip() if path else ""
    if path and save and defaultextension and not os.path.splitext(path)[1]:
        path += defaultextension
    return path


def _native(save, *, title=None, initialdir=None, initialfile=None,
            filetypes=(), defaultextension=None):
    if _NATIVE in ("zenity", "qarma"):
        return _zenity(save, title, initialdir, initialfile, filetypes,
                       defaultextension)
    if _NATIVE == "kdialog":
        return _kdialog(save, title, initialdir, initialfile, filetypes,
                        defaultextension)
    return None


# ------------------------------------------------------------- tkinter fallback
_DIALOG = ".__tk_filedialog"
_SIZE = "780x520"


def _pin_size(parent) -> None:
    """Fixiert die Größe des nicht-nativen Tk-Dateidialogs beim Öffnen (Fallback)."""
    if parent is None:
        return
    state = {"n": 0}

    def tick():
        state["n"] += 1
        try:
            if parent.tk.call("winfo", "exists", _DIALOG):
                parent.tk.call("wm", "geometry", _DIALOG, _SIZE)
        except tk.TclError:
            return
        if state["n"] < 8:
            try:
                parent.after(50, tick)
            except tk.TclError:
                pass

    try:
        parent.after(20, tick)
    except tk.TclError:
        pass


# ------------------------------------------------------------------- public API
def askopenfilename(*, parent=None, title=None, filetypes=(), initialdir=None,
                    initialfile=None, **kwargs):
    """Wie :func:`tkinter.filedialog.askopenfilename`, nutzt aber – wenn möglich –
    den nativen System-Dateidialog."""
    if _NATIVE:
        res = _native(False, title=title, initialdir=initialdir,
                      initialfile=initialfile, filetypes=filetypes)
        if res is not None:
            return res
    _pin_size(parent)
    return filedialog.askopenfilename(parent=parent, title=title,
                                      filetypes=filetypes, initialdir=initialdir,
                                      initialfile=initialfile, **kwargs)


def asksaveasfilename(*, parent=None, title=None, filetypes=(), initialdir=None,
                      initialfile=None, defaultextension=None, **kwargs):
    """Wie :func:`tkinter.filedialog.asksaveasfilename`, nutzt aber – wenn möglich –
    den nativen System-Dateidialog."""
    if _NATIVE:
        res = _native(True, title=title, initialdir=initialdir,
                      initialfile=initialfile, filetypes=filetypes,
                      defaultextension=defaultextension)
        if res is not None:
            return res
    _pin_size(parent)
    return filedialog.asksaveasfilename(
        parent=parent, title=title, filetypes=filetypes, initialdir=initialdir,
        initialfile=initialfile, defaultextension=defaultextension, **kwargs)
