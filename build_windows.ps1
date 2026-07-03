# Baut die portable Windows-.exe des Kamera_Konfigurationsmanagers.
# Muss AUF Windows mit Python 3.13 laufen (PyInstaller cross-kompiliert nicht).
#
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#
$ErrorActionPreference = "Stop"

Write-Host "==== Abhaengigkeiten sicherstellen ===="
py -3.13 -m pip install --upgrade pip pyinstaller
# Laufzeit-Abhaengigkeiten aus requirements.txt: zeroconf, cryptography UND sv-ttk
# (das Sun-Valley-Theme fuer Hell/Dunkel). Fehlte sv-ttk hier, buendelte PyInstaller
# es nicht -> die .exe blieb ohne Dark-Mode beim hellen Windows-Standard-Theme.
py -3.13 -m pip install -r requirements.txt

Write-Host "==== PyInstaller-Build ===="
py -3.13 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec

Write-Host ">> Fertig: dist\Kamerakonfigurationsmanager.exe"
