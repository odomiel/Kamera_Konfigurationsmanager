# Windows-Build (portable .exe)

Der Kamera_Konfigurationsmanager wird unter Windows als **portable One-File-.exe**
gebaut (keine Installation noetig). PyInstaller cross-kompiliert nicht — der Build
muss **auf Windows** laufen.

## Voraussetzungen

- Windows 10/11 (x64)
- Python 3.13 (von python.org; bringt Tkinter/Tcl-Tk mit)
- Paketabhaengigkeiten:

```powershell
py -3.13 -m pip install --upgrade pip pyinstaller zeroconf cryptography
```

`tkinter` ist im offiziellen Windows-Python bereits enthalten. `cryptography`
liefert ein fertiges Wheel inkl. Krypto-Backend (fuer den Passwort-Tresor).

## Bauen

```powershell
py -3.13 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec
```

Ergebnis: `dist\Kamerakonfigurationsmanager.exe` — eine eigenstaendige,
portable Datei, die ohne Installation gestartet werden kann.

## Hinweise

- Funktionsgleich zur Linux-AppImage-Variante: es wird dasselbe `kkm`-Paket
  gebuendelt (`main.py` als Einstieg).
- Die App legt ihre Einstellungen unter `%APPDATA%\kamera_konfigurationsmanager`
  ab (Gruppen, Einstellungen, verschluesselter Passwort-Tresor).
- Ein optionales Icon kann unter `assets\Kamerakonfigurationsmanager.ico`
  hinterlegt werden; fehlt es, baut PyInstaller ohne eigenes Icon.
