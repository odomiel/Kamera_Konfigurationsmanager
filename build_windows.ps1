# Baut die portable Windows-.exe des Kamera_Konfigurationsmanagers.
# Muss AUF Windows mit Python 3.14 laufen (PyInstaller cross-kompiliert nicht).
#
# Python 3.14 haelt die Python-Version zur Linux-AppImage konsistent.
# ACHTUNG: Der python.org-WINDOWS-Installer von 3.14 buendelt weiterhin Tcl/Tk
# 8.6.15 (nur der macOS-Installer wurde auf Tk 9.0 umgestellt; CPythons
# PCbuild/get_externals.bat pinnt fuer Windows tk-8.6.15.0). PyInstaller nimmt
# die Tk-Version des bauenden Interpreters -> die .exe hat daher Tk 8.6, NICHT
# Tk 9. Tk 9 gibt es nur in der AppImage, die Tcl/Tk 9 selbst kompiliert. Der
# Dunkelmodus (sv_ttk) laeuft auf Tk 8.6 unveraendert.
#
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Bump   # Version vorher erhoehen
#
# Die fertige .exe traegt die Versionsnummer im Namen (wie die AppImage):
#   dist\Kamerakonfigurationsmanager-<Version>.exe
#
param([switch]$Bump)

$ErrorActionPreference = "Stop"

if ($Bump) {
    Write-Host "==== Version erhoehen ===="
    py -3.14 bump_version.py
}
# Einzige Quelle der Wahrheit: kkm/version.py (dieselbe, die auch die Spec liest).
$Version = (py -3.14 bump_version.py --print).Trim()

Write-Host "==== Abhaengigkeiten sicherstellen (Python 3.14, Tcl/Tk 8.6) ===="
py -3.14 -m pip install --upgrade pip pyinstaller
# Laufzeit-Abhaengigkeiten aus requirements.txt: zeroconf, cryptography UND sv-ttk
# (das Sun-Valley-Theme fuer Hell/Dunkel). Fehlte sv-ttk hier, buendelte PyInstaller
# es nicht -> die .exe blieb ohne Dark-Mode beim hellen Windows-Standard-Theme.
py -3.14 -m pip install -r requirements.txt

Write-Host "==== PyInstaller-Build ($Version) ===="
py -3.14 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec

$Exe = "dist\Kamerakonfigurationsmanager-$Version.exe"
if (-not (Test-Path $Exe)) { throw "Erwartete Datei fehlt: $Exe" }
Write-Host ">> Fertig: $Exe"
