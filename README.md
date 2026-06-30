# Kamera_Konfigurationsmanager

Plattformübergreifendes Desktop-Tool zum Verwalten und Konfigurieren von
Netzwerkkameras — Aufbau grob wie der AXIS Device Manager, **ohne Live-Überwachung**.
Windows portabel (`.exe`) und Linux (AppImage), gleicher Stack wie das
Axis_Kamera_Discovery-Tool (Python 3.13 + Tkinter/Tk9).

## Funktionen (Zielbild)

- **Gerätesuche** im LAN (mDNS), Zuweisung zu Gruppen.
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
*Konfiguration* (Axis `.cfg` Import auf alle ausgewählten Kameras + Export der
ersten Kamera mit durchsuchbarer Parameter-Auswahl, v1+v2) — auf gemeinsamer
Dialog-Basis (`kkm/gui/dialogs/base.py`: Zugangsdaten, Hintergrund-Threads,
Ergebnis-Log, Tresor-Vorbefüllung). **Firmware-Dialog fertig:** aktualisiert
mehrere Kameras *verschiedener Modelle gleichzeitig* — pro Modell eine eigene
`.bin` zuweisen, Update parallel mit Ergebnis-Log; nicht zugewiesene Modelle
werden übersprungen; factory-default-Option; langer Upload-Timeout. **Offen:** die
drei weiteren Aktions-Dialoge (IP/Benutzer/ONVIF), die Einstellungen
(Plugin-Manager, Spalten, Online-Prüfung-je-Gruppe, Tresor-UI) und die
Build-Skripte.

## Aus dem Quellcode starten

```bash
pip install -r requirements.txt   # zeroconf, cryptography
python3 main.py
```
