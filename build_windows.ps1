# Baut die portable Windows-.exe des Kamera_Konfigurationsmanagers.
# Muss AUF Windows mit Python 3.13 laufen (PyInstaller cross-kompiliert nicht).
#
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#
$ErrorActionPreference = "Stop"

Write-Host "==== Abhaengigkeiten sicherstellen ===="
py -3.13 -m pip install --upgrade pip pyinstaller zeroconf cryptography

Write-Host "==== PyInstaller-Build ===="
py -3.13 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec

Write-Host ">> Fertig: dist\Kamerakonfigurationsmanager.exe"
