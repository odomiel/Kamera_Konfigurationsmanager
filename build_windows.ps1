# Baut die portable Windows-.exe des Kamera_Konfigurationsmanagers.
# Muss AUF Windows mit Python 3.14 laufen (PyInstaller cross-kompiliert nicht).
#
# Python 3.14 haelt die Python-Version zur Linux-AppImage konsistent.
# ACHTUNG: Der python.org-WINDOWS-Installer von 3.14 buendelt inzwischen
# ebenfalls Tcl/Tk 9.0 (frueher noch 8.6.15 -> dieser Kommentar war veraltet).
# Die Tk-Version folgt weiterhin dem bauenden Interpreter, also hat die .exe
# jetzt Tk 9, so wie auch die AppImage. Der Dunkelmodus (sv_ttk) laeuft auf
# Tk 9 unveraendert.
#
# WICHTIG (Tk 9 + PyInstaller): Der Windows-Installer liefert die Tcl/Tk-9-
# Bibliotheksdateien nicht mehr als lose Dateien, sondern in zwei ZIPs
# (<PythonRoot>\tcl\libtcl9.x.zip / libtk9.x.zip), die Tcl zur Laufzeit ueber
# sein eingebautes zipfs moundet. PyInstaller 6.21 erkennt das nicht (prueft
# nur os.path.isdir() auf dem echten Dateisystem) und sammelt dadurch 0
# Tcl/Tk-Dateien ein -> die gebaute .exe stirbt sofort mit "FileNotFoundError:
# Tcl data directory ..._tcl_data not found". Kamerakonfigurationsmanager.spec
# enthaelt deshalb einen Workaround, der diese beiden ZIPs selbst entpackt und
# als datas einspeist. Bei einer PyInstaller-Version, die zipfs-Tcl/Tk nativ
# unterstuetzt, kann dieser Workaround wieder entfernt werden.
#
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Bump   # Version vorher erhoehen
#
# Die fertige .exe traegt die Versionsnummer im Namen:
#   dist\Kamerakonfigurationsmanager_<Version>.exe
#
param([switch]$Bump)

$ErrorActionPreference = "Stop"

if ($Bump) {
    Write-Host "==== Version erhoehen ===="
    py -3.14 bump_version.py
}
# Einzige Quelle der Wahrheit: kkm/version.py (dieselbe, die auch die Spec liest).
$Version = (py -3.14 bump_version.py --print).Trim()

Write-Host "==== Abhaengigkeiten sicherstellen (Python 3.14, Tcl/Tk 9.0) ===="
py -3.14 -m pip install --upgrade pip pyinstaller
# Laufzeit-Abhaengigkeiten aus requirements.txt: zeroconf, cryptography UND sv-ttk
# (das Sun-Valley-Theme fuer Hell/Dunkel). Fehlte sv-ttk hier, buendelte PyInstaller
# es nicht -> die .exe blieb ohne Dark-Mode beim hellen Windows-Standard-Theme.
py -3.14 -m pip install -r requirements.txt

Write-Host "==== PyInstaller-Build ($Version) ===="
py -3.14 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec

$Exe = "dist\Kamerakonfigurationsmanager_$Version.exe"
if (-not (Test-Path $Exe)) { throw "Erwartete Datei fehlt: $Exe" }
Write-Host ">> Fertig: $Exe"
