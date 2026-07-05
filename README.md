# Kamera_Konfigurationsmanager

Plattformübergreifendes Desktop-Tool zum Verwalten und Konfigurieren von
Netzwerkkameras — Aufbau grob wie der AXIS Device Manager, **ohne Live-Überwachung**.
Windows portabel (`.exe`) und Linux (AppImage), gleicher Stack wie das
Axis_Kamera_Discovery-Tool (Python 3.14 + Tkinter/Tk9).

## Funktionen (Zielbild)

- **Gerätesuche** im LAN (mDNS); Kameras per **Rechtsklick** einer oder mehreren
  Gruppen zuweisen (additiv), aus der aktuellen Gruppe entfernen oder **vollständig
  entfernen**. Eigene Spalte **„Gruppe(n)"** zeigt die Zugehörigkeit.
- **Gruppen ohne Datenbank** (JSON): nicht löschbare Gruppe „Alle Kameras“,
  darunter eigene Gruppen (anlegen/bearbeiten/löschen).
- **Online-Status** als eigene Spalte, manueller Prüf-Button + konfigurierbare
  Online-Prüfung je Gruppe.
- **Kamera-Aktionen** als eigene Buttons in der Vorderansicht (wie ADM):
  IP-Adresse, Benutzer, ONVIF-Benutzer, Firmware (mehrere Typen gleichzeitig),
  Konfiguration (Axis `.cfg` Im-/Export v1+v2).
- **Passwort-Tresor**: Master-Passwort → PBKDF2 → AES-256-GCM (eine Datei,
  portabel, kein OS-Keyring, keine DB).
- **Plugin-System** je Hersteller, an-/abschaltbar — derzeit nur **Axis**.

## Architektur

```
kkm/
  core/                 vendor-neutral
    plugins.py          VendorPlugin-Interface + Registry, Credentials, Capability
    groups.py           GroupStore (JSON), "Alle Kameras", Online-Prüfung je Gruppe
    vault.py            PasswordVault (PBKDF2 + AES-256-GCM)
  plugins/
    axis/
      vapix.py          VAPIX/ONVIF-Client (kopiert aus Discovery, stdlib-only)
      discovery.py      mDNS-Discovery + FIELD_NAMES + Export
      plugin.py         AxisPlugin: adaptiert vapix/discovery an VendorPlugin
  gui/
    app.py              Hauptfenster: Gruppen-Baum + Tabelle + Aktions-Toolbar
main.py                 Startpunkt (GUI)
```

Der gesamte herstellerspezifische Code liegt hinter `VendorPlugin`. Ein neuer
Hersteller = ein neues Plugin-Paket unter `kkm/plugins/`; `core` und `gui` bleiben
unverändert.

## Stand

Gerüst. Funktionsfähig: Paketstruktur, Plugin-Interface, Gruppen-Store,
Passwort-Tresor, Axis-Plugin (Discovery + VAPIX gewrappt), GUI-Schale mit Suche,
Gruppen, Tabelle und Online-Prüfung. **Erster Aktions-Dialog fertig:**
*Konfiguration* (Axis `.cfg` Im-/Export auf alle ausgewählten Kameras — inkl.
Bewegungserkennung/VMD4 — Export der ersten Kamera mit durchsuchbarer
Parameter-Auswahl, v1+v2) — auf gemeinsamer
Dialog-Basis (`kkm/gui/dialogs/base.py`: Zugangsdaten, Hintergrund-Threads,
Ergebnis-Log, Tresor-Vorbefüllung). **Firmware-Dialog fertig:** aktualisiert
mehrere Kameras *verschiedener Modelle gleichzeitig* — pro Modell eine eigene
`.bin` zuweisen, Update parallel mit Ergebnis-Log; nicht zugewiesene Modelle
werden übersprungen; factory-default-Option; langer Upload-Timeout.
**Benutzer-Dialog fertig:** anlegen (mit Rolle + factory) / Passwort ändern /
Stapel-Import aus `Name,Passwort[,Rolle]`-Datei (einmal validiert, je Kamera ×
Benutzer); optional Speichern ins Tresor. **ONVIF-Benutzer-Dialog fertig:**
gleicher Aufbau mit ONVIF-Stufen (Administrator/Operator/User), ohne factory.
**IP-Adresse-Dialog fertig:** DHCP / feste IP fortlaufend ab Start-IP / pro Kamera
einzeln (Ziel-IPs werden vor dem Zugriff validiert). **Alle fünf Aktions-Dialoge
stehen damit.** **Einstellungen-Dialog fertig:** Tresor-Verwaltung (Master-Passwort
anlegen/entsperren/sperren/ändern), Plugin-Manager (Hersteller an/aus, persistent),
Online-Prüfung je Gruppe (an/aus + Intervall, mit automatischer Prüfung der
gewählten Gruppe im Hauptfenster) und Spalten-Sichtbarkeit; Tresor ist ins
Hauptfenster eingebunden (Aktions-Dialoge füllen gespeicherte Passwörter vor).
Ein Reiter **„Über"** zeigt Programm- und Komponentenversionen, Ersteller/Lizenz
sowie den Hinweis auf die KI-gestützte Entwicklung.
**Build-Skripte fertig:** Linux-AppImage und Windows-`.exe` (siehe unten). Die
Programm-Features sind damit vollständig.

## Aus dem Quellcode starten

```bash
pip install -r requirements.txt   # zeroconf, cryptography
python3 main.py
```

## Bauen

**Linux (AppImage)** — baut Tcl/Tk 9 + Python 3.14 + OpenSSL aus dem Quelltext
und vendort `zeroconf` + `cryptography` als Wheels (kein pip im Ergebnis nötig):

```bash
./build_appimage.sh            # -> Kamerakonfigurationsmanager-<version>-x86_64.AppImage
./build_appimage.sh --bump     # Version vorher hochzählen, dann bauen
```

**Windows (portable .exe)** — muss auf Windows mit **Python 3.14** laufen
(PyInstaller cross-kompiliert nicht; 3.14 bringt Tcl/Tk 9 mit — wie die AppImage),
Details in `BUILD_WINDOWS.md`. Die `.exe` legt ihre Konfiguration (Gruppen,
Einstellungen, Passwort-Tresor) **neben sich selbst** im Ordner
`kamera_konfigurationsmanager` ab (mitnehmbar); die Linux-AppImage nutzt weiterhin
`~/.config`:

```powershell
py -3.14 -m PyInstaller --noconfirm Kamerakonfigurationsmanager.spec
# oder: powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

**Version** (Schema `JJ.MM.TT[bN]`, in `kkm/version.py`):

```bash
python3 bump_version.py --print    # aktuelle Version
python3 bump_version.py            # nächste Version setzen
```

## Lizenz

GPL-3.0-or-later. Siehe `LICENSE`. Dieses Projekt enthält den VAPIX-Client aus
dem ebenfalls GPL-3.0 lizenzierten Axis_Kamera_Discovery-Tool; der gesamte
Quelltext steht daher unter der GNU General Public License v3 (oder neuer).
