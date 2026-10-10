# Kamera_Konfigurationsmanager

Plattformübergreifendes Desktop-Tool zum Verwalten und Konfigurieren von
Netzwerkkameras — Aufbau Inspiriert vom AXIS Device Manager.
Windows portabel (`.exe`) und Linux (AppImage), gleicher Stack wie das
Axis_Kamera_Discovery-Tool (Python 3.14 + Tkinter; Tk 9 im Linux-AppImage
selbst kompiliert, die Windows-`.exe` nutzt das Tk 9 des python.org-Installers).

## Funktionen (Zielbild)

- **Gerätesuche** im LAN (mDNS); Kameras per **Rechtsklick** einer oder mehreren
  Gruppen zuweisen (additiv), aus der aktuellen Gruppe entfernen oder **vollständig
  entfernen**. Eigene Spalte **„Gruppe(n)"** zeigt die Zugehörigkeit. Nicht gefundene
  Kameras (anderes Subnetz o. Ä.) lassen sich über den Pfeil am *Suchen*-Button
  **manuell** per IP-Adresse und Hersteller hinzufügen.
- **Gruppen ohne Datenbank** (JSON): nicht löschbare Gruppe „Alle Kameras“,
  darunter eigene Gruppen (anlegen/bearbeiten/löschen).
- **Online-Status** als eigene Spalte, manueller Prüf-Button + konfigurierbare
  Online-Prüfung je Gruppe.
- **Kamera-Aktionen** als eigene Buttons in der Vorderansicht:
  IP-Adresse, Benutzer, ONVIF-Benutzer, Firmware (mehrere Typen gleichzeitig,
  mit Online-Update-Suche), Konfiguration (Axis `.cfg` Im-/Export v1+v2),
  Konfig-Backup (Komplett-Sicherung: Axis via Device-Configuration-API `.json`,
  Hikvision/Dahua/Hanwha als `.bin`), Zeitzone (Axis Time API, IANA).
- **Passwort-Tresor**: Master-Passwort → PBKDF2 → AES-256-GCM (eine Datei,
  portabel, kein OS-Keyring, keine DB). Iterationszahl wird mit gespeichert und beim
  Öffnen geprüft; Konfig-Ordner/-Dateien unter Linux nur für den Besitzer lesbar
  (`0700`/`0600`).
- **Kein Klartext-Passwort über HTTP**: über HTTP nur Digest-Anmeldung, Basic nur über
  HTTPS (für Altgeräte in den Einstellungen abschaltbar).
- **Zertifikats-Merken (Trust-on-First-Use)**: HTTPS-Zertifikat je Kamera beim ersten
  Kontakt speichern; bei Änderung keine Zugangsdaten senden, sondern nachfragen; kein
  HTTP-Rückfall bei bekanntem Zertifikat (abschaltbar, ab Werk an).
- **Plugin-System** je Hersteller, an-/abschaltbar — **Axis** (voller Funktionsumfang),
  ein generisches **ONVIF**-Plugin (Standard-Geräte: Suche, Info, IP, ONVIF-Benutzer,
  Werksreset; ab Werk ausgeschaltet) und **Hikvision** (ISAPI/SADP; Suche, Info, IP,
  Benutzer, ONVIF-Benutzer, Firmware-Upload, Werksreset — **experimentell**, noch nicht
  an echter Hardware verifiziert, ab Werk ausgeschaltet) sowie **Dahua** (HTTP-API/DHIP;
  gleicher Funktionsumfang, deckt auch Dahua-OEMs wie die Honeywell Performance Series
  und Amcrest ab — ebenfalls **experimentell**, ab Werk ausgeschaltet) sowie
  **Hanwha/Wisenet** (SUNAPI; Suche über ONVIF, Geräteinfo, IP, Benutzer, ONVIF-Benutzer,
  Firmware, Werksreset — **experimentell**, an einer Wisenet-Kamera verifiziert, ab Werk
  ausgeschaltet).

## Architektur

```
kkm/
  core/                 vendor-neutral
    plugins.py          VendorPlugin-Interface + Registry, Credentials, Capability
    camera.py           Form des Kamera-Dicts (FIELD_NAMES) + Helfer darauf
    groups.py           GroupStore (JSON), "Alle Kameras", Online-Prüfung je Gruppe
    vault.py            PasswordVault (PBKDF2 + AES-256-GCM)
  plugins/
    axis/
      vapix.py          VAPIX/ONVIF-Client (kopiert aus Discovery, stdlib-only)
      discovery.py      mDNS-Discovery
      firmware_repo.py  Firmware-Verzeichnis (Update-Suche + Download)
      plugin.py         AxisPlugin: adaptiert vapix/discovery an VendorPlugin
    onvif/
      soap.py           ONVIF Device Management (WS-Security, stdlib-only)
      discovery.py      WS-Discovery (UDP-Multicast)
      plugin.py         OnvifPlugin: generisch, kann weniger als ein Hersteller-Plugin
    hikvision/
      isapi.py          ISAPI-Client (HTTP-Digest, XML, stdlib-only)
      discovery.py      SADP-Discovery (UDP-Multicast 37020)
      plugin.py         HikvisionPlugin: experimentell, ONVIF-Benutzer via onvif/soap
    hanwha/
      sunapi.py         SUNAPI-Client (HTTP-Digest, KEY=VALUE, stdlib-only)
      discovery.py      ONVIF-WS-Discovery, auf Hanwha gefiltert
      plugin.py         HanwhaPlugin: experimentell, ONVIF-Benutzer via onvif/soap
    dahua/
      httpapi.py        Dahua HTTP API (HTTP-Digest, KEY=VALUE, stdlib-only)
      discovery.py      DHIP-Discovery (UDP 37810)
      plugin.py         DahuaPlugin: experimentell, ONVIF-Benutzer via onvif/soap
  gui/
    app.py              Hauptfenster: Gruppen-Baum + Tabelle + Aktions-Toolbar
main.py                 Startpunkt (GUI)
```

Der gesamte herstellerspezifische Code liegt hinter `VendorPlugin`. Ein neuer
Hersteller = ein neues Plugin-Paket unter `kkm/plugins/`; `core` und `gui` bleiben
unverändert.

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

**Release** — nach `bump_version.py` + CHANGELOG-Eintrag den kompletten Vorgang
(AppImage bauen falls nötig, Smoke-Test, Forgejo-Release mit Notes aus CHANGELOG.md
und AppImage als Asset) in einem Schritt:

```bash
./release.sh                   # bauen (falls nötig) + testen + Release anlegen
./release.sh --no-build        # vorhandenes AppImage der Version verwenden
./release.sh --dry-run         # nur anzeigen, nichts hochladen
```

**Windows (portable .exe)** — muss auf Windows mit **Python 3.14** laufen
(PyInstaller cross-kompiliert nicht). Anders als die AppImage nutzt die `.exe`
das **Tcl/Tk 8.6** des python.org-Windows-Installers (dessen 3.14 bringt auf
Windows weiterhin Tk 8.6, nicht Tk 9); Details in `BUILD_WINDOWS.md`. Die `.exe` legt ihre Konfiguration (Gruppen,
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

Dieses Projekt wurde zu großen teilen mit Hilfe von Ki (Claud Code) erstellt

GPL-3.0-or-later. Siehe `LICENSE`. Dieses Projekt enthält den VAPIX-Client aus
dem ebenfalls GPL-3.0 lizenzierten Axis_Kamera_Discovery-Tool; der gesamte
Quelltext steht daher unter der GNU General Public License v3 (oder neuer).
