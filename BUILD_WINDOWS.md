# Windows-Build (portable .exe)

Der Kamera_Konfigurationsmanager wird unter Windows als **portable One-File-.exe**
gebaut (keine Installation noetig). PyInstaller cross-kompiliert nicht — der Build
muss **auf Windows** laufen.

## Voraussetzungen

- Windows 10/11 (x64)
- **Python 3.14** (von python.org; bringt Tkinter/Tcl-Tk mit)
- Paketabhaengigkeiten:

```powershell
py -3.14 -m pip install --upgrade pip pyinstaller
py -3.14 -m pip install -r requirements.txt
```

**Warum Python 3.14?** Es haelt die Python-Version zur Linux-AppImage konsistent
und ist die aktuelle Reihe. **Hinweis zur Tk-Version:** Der python.org-**Windows**-
Installer von 3.14 buendelt weiterhin **Tcl/Tk 8.6.15** — nur der *macOS*-Installer
wurde ab 3.14.5 auf Tk 9.0 umgestellt (CPythons `PCbuild/get_externals.bat` pinnt
fuer Windows `tk-8.6.15.0`). Da PyInstaller die Tk-Version des bauenden
Interpreters uebernimmt, hat die `.exe` folglich **Tk 8.6, nicht Tk 9**. Tk 9 gibt
es nur in der Linux-AppImage, weil diese Tcl/Tk 9 selbst aus dem Quelltext baut.
Das ist unkritisch: der Dunkelmodus (`sv-ttk`) laeuft auf Tk 8.6 unveraendert.
`--upgrade pyinstaller` haelt PyInstaller aktuell.

`tkinter` ist im offiziellen Windows-Python bereits enthalten. `cryptography`
liefert ein fertiges Wheel inkl. Krypto-Backend (fuer den Passwort-Tresor).
`requirements.txt` bringt ausserdem **`sv-ttk`** mit — ohne dieses Wheel fehlt in
der `.exe` das Sun-Valley-Theme und der **Dunkelmodus funktioniert nicht**
(die App bleibt beim hellen Windows-Standard-Theme).

## Bauen

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Bump   # Version vorher erhoehen

# oder direkt, ohne das Skript:
py -3.14 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec
```

Ergebnis: `dist\Kamerakonfigurationsmanager-<Version>.exe` (z. B.
`Kamerakonfigurationsmanager-26.07.11b2.exe`) — eine eigenstaendige, portable Datei,
die ohne Installation gestartet werden kann. Die Version im Dateinamen kommt wie beim
AppImage aus `kkm/version.py`; die Spec liest sie selbst, ein direkter
PyInstaller-Aufruf benennt die Datei also genauso.

## Hinweise

- Funktionsgleich zur Linux-AppImage-Variante: es wird dasselbe `kkm`-Paket
  gebuendelt (`main.py` als Einstieg).
- Die App legt ihre Einstellungen unter `%APPDATA%\kamera_konfigurationsmanager`
  ab (Gruppen, Einstellungen, verschluesselter Passwort-Tresor).
- Ein optionales Icon kann unter `assets\Kamerakonfigurationsmanager.ico`
  hinterlegt werden; fehlt es, baut PyInstaller ohne eigenes Icon.
