# Baut die portable Windows-.exe des Kamera_Konfigurationsmanagers.
# Muss AUF Windows mit Python 3.14 laufen (PyInstaller cross-kompiliert nicht).
#
# Python 3.14 wird bewusst genutzt: sein Windows-Installer bringt Tcl/Tk 9.0 mit
# (Python 3.13 buendelt noch Tk 8.6). PyInstaller nimmt die Tk-Version des
# bauenden Interpreters -> so entspricht die .exe der Linux-AppImage (ebenfalls Tk 9).
# Eine aktuelle PyInstaller-Version (>= 6.10, unterstuetzt Tk 9) wird per --upgrade
# sichergestellt.
#
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#
$ErrorActionPreference = "Stop"

Write-Host "==== Abhaengigkeiten sicherstellen (Python 3.14, Tcl/Tk 9) ===="
py -3.14 -m pip install --upgrade pip pyinstaller
# Laufzeit-Abhaengigkeiten aus requirements.txt: zeroconf, cryptography UND sv-ttk
# (das Sun-Valley-Theme fuer Hell/Dunkel). Fehlte sv-ttk hier, buendelte PyInstaller
# es nicht -> die .exe blieb ohne Dark-Mode beim hellen Windows-Standard-Theme.
py -3.14 -m pip install -r requirements.txt

Write-Host "==== PyInstaller-Build ===="
py -3.14 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec

Write-Host ">> Fertig: dist\Kamerakonfigurationsmanager.exe"
