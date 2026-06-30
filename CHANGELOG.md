# Änderungsverlauf

Versionsschema: `JJ.MM.TT[bN]` (zweistelliges Jahr; mehrere Releases am selben Tag
erhalten ein hochzählendes `bN`-Suffix). Die aktuelle Version steht in
`kkm/version.py`.

## 26.06.30b5 — 2026-06-30

- **Firmware/Modell nach der Suche auslesen**: Da mDNS keine Firmware liefert,
  werden Firmware und Modell nach der Suche per VAPIX nachgelesen
  (`get_device_info` liest jetzt auch `Properties.Firmware.Version`).
- **Zugangsdaten-Abfrage bei der Suche**: Für Kameras mit unbekannten
  Zugangsdaten wird nach Benutzer/Passwort gefragt; Option „dieses Passwort bei
  allen Kameras mit unbekannten Zugangsdaten ausprobieren". Funktionierende
  Zugangsdaten werden automatisch gespeichert (Tresor, sonst Sitzung). Kameras mit
  bekannten Zugangsdaten werden still im Hintergrund ausgelesen.
- **Status bei der Suche**: gefundene Kameras werden online gesetzt, bekannte aber
  nicht mehr gefundene offline. Statusspalte farblich: online grün, offline rot.

## 26.06.30b4 — 2026-06-30

- **Hilfe-Seite**: „Hilfe"-Button (oben rechts) öffnet eine Beschreibung aller
  Funktionen (`HILFE.md`), in AppImage und Windows-`.exe` mitgebündelt.

## 26.06.30b3 — 2026-06-30

- **Spalte „Gruppe(n)"** in der Geräteliste: zeigt, in welchen Gruppen eine Kamera
  ist (ohne „Alle Kameras"), per Spalten-Einstellung aus-/einblendbar.
- **Kamera vollständig entfernen** (Rechtsklick-Kontextmenü): löscht die Kamera aus
  der Geräteliste und allen Gruppen sowie ihr gespeichertes Passwort (bei
  entsperrtem Tresor), mit Bestätigung.

## 26.06.30b2 — 2026-06-30

- **Kameras per Rechtsklick Gruppen zuweisen** (additiv): Kontextmenü auf der
  Geräte-Tabelle mit „Zu Gruppe hinzufügen ▸ <Gruppe>" (inkl. „Neue Gruppe…")
  und „Aus <Gruppe> entfernen". Eine Kamera kann in mehreren Gruppen sein;
  „Alle Kameras" bleibt unberührt.
- **Programm-Icon** (Bullet-/CCTV-Kamera + Konfigurations-Zahnrad) als PNG und
  Windows-`.ico` unter `assets/`; AppImage und Windows-Build nutzen es automatisch.

## 26.06.30b1 — 2026-06-30

Erste Fassung. Plugin-basierter Kamera-Konfigurationsmanager (Linux-AppImage +
portable Windows-`.exe`, Tkinter/Tk9), Aufbau grob wie der AXIS Device Manager,
ohne Live-Überwachung.

- **Architektur**: 3 Schichten — `kkm.core` (herstellerneutral: `VendorPlugin`-
  Interface + Registry, Gruppen-Store, Passwort-Tresor, App-Einstellungen),
  `kkm.plugins.axis` (VAPIX-Client aus dem Axis_Kamera_Discovery kopiert und
  eigenständig gepflegt + mDNS-Discovery + Plugin-Wrapper), `kkm.gui` (Tkinter).
- **Gruppen ohne Datenbank** (JSON): nicht löschbare Gruppe „Alle Kameras",
  darunter eigene Gruppen anlegen/umbenennen/löschen.
- **Gerätesuche** im LAN (mDNS) und **Online-Status** als Spalte: manueller
  Prüf-Button + automatische Online-Prüfung je Gruppe (an/aus + Intervall).
- **Fünf Aktions-Dialoge** als Buttons in der Vorderansicht (wirken auf die
  ausgewählten Kameras, Hintergrund-Threads mit Ergebnis-Log):
  - **Konfiguration**: Axis-`.cfg` (ADM) importieren auf alle ausgewählten
    Kameras + exportieren der ersten Kamera mit durchsuchbarer Parameter-Auswahl
    (Format v1+v2).
  - **Firmware**: mehrere Kameras verschiedener Modelle gleichzeitig — pro Modell
    eine eigene `.bin`, factory-default-Option.
  - **Benutzer**: anlegen (Rolle + factory) / Passwort ändern / Stapel-Import.
  - **ONVIF-Benutzer**: anlegen / Passwort ändern / Stapel-Import (Stufen
    Administrator/Operator/User).
  - **IP-Adresse**: DHCP / feste IP fortlaufend ab Start-IP / pro Kamera einzeln.
- **Passwort-Tresor**: Master-Passwort → PBKDF2-HMAC-SHA256 → AES-256-GCM, eine
  Datei; Aktions-Dialoge füllen gespeicherte Passwörter vor.
- **Einstellungen-Dialog**: Tresor-Verwaltung, Plugin-Manager (Hersteller an/aus),
  Online-Prüfung je Gruppe, Spalten-Sichtbarkeit.
- **Plugin-System**: Hersteller an-/abschaltbar; derzeit nur **Axis**.
- **Export** der Geräteliste (CSV/Text).
- **Build**: `build_appimage.sh` (Tcl/Tk 9 + Python 3.13 + OpenSSL aus Quelltext,
  vendort zeroconf + cryptography), `Kamerakonfigurationsmanager.spec` /
  `build_windows.ps1` für die Windows-`.exe`, `bump_version.py`.
- **Lizenz**: GPL-3.0-or-later (`LICENSE`) mit Datei-Headern; `THIRD_PARTY_LICENSES.md`
  für die gebündelten Komponenten.
