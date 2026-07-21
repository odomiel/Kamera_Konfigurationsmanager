# Recherche: Hanwha-(Wisenet-)Plugin

> **UMGESETZT (2026-07-21).** Das Plugin ist gebaut (`kkm/plugins/hanwha/`) und an
> echter Hardware (Wisenet QNO-6082R, Firmware 1.41.18) verifiziert — Discovery,
> Geräteinfo, IP (fest/DHCP), Benutzer und ONVIF-Benutzer. Der in Abschnitt 4 genannte
> Haupt-Haken („SUNAPI-Doku NDA-gebunden") entfiel: die Kamera **dokumentiert ihre
> eigene API** unter `/stw-cgi/attributes.cgi/<cgi>` (jedes Submenu/Action/Parameter
> mit Zugriffsstufe), woraus die exakten Endpunkte/Parameter gelesen wurden. Weiterhin
> `experimental` (nur ein Modell getestet). Firmware-Upload und Werksreset noch offen.
> Details unten sind der ursprüngliche Rechercheertrag (2026-07-17).

*Stand: 2026-07-17. Machbarkeits- und Aufwandsanalyse, noch keine Umsetzung.*

Ziel: Ein Hersteller-Plugin für Hanwha-/Wisenet-Kameras, das (wie das Axis-Plugin)
die Kern-Funktionen anbietet. Dieses Dokument hält fest, **was der Code verlangt**,
**was Hanwha technisch liefert** und **wo die Haken liegen**.

---

## 1. Was das Programm von einem Plugin verlangt

Architektonisch ist alles vorbereitet. Ein neues Plugin = **ein neues Paket
`kkm/plugins/hanwha/`** mit einer `VendorPlugin`-Unterklasse, registriert in
`build_registry()` (`kkm/plugins/__init__.py`). **Nichts in `core` oder `gui` ändert
sich.**

Pflicht (abstrakt in `VendorPlugin`, `kkm/core/plugins.py`):
- `discover(timeout)` → Liste von Kamera-Dicts (mit den Basisfeldern aus `FIELD_NAMES`)
- `check_online(camera, creds)` → bool

Optional, jeweils pro gemeldeter `Capability.*` freigeschaltet (die GUI grayt den
Rest selbst aus):
- `device_info`
- `set_static_ip` / `set_dhcp`
- `add_user` / `set_user_password` (+ `parse_user_list`)
- `add_onvif_user` / `set_onvif_user_password`
- `upgrade_firmware`
- `firmware_updates` / `firmware_release` / `download_firmware` (Update-Suche)
- `parse_config_file` / `write_config_file` / `import_config` (Konfig-Vorlage)
- `factory_reset`

Klassen-Attribute für die Dialoge: `USER_ROLES`, `ONVIF_LEVELS` (höchstes Recht zuerst).

Vorlagen im Baum: das **ONVIF-Plugin** (`kkm/plugins/onvif/`, 4 Dateien, stdlib-only)
und das **Axis-Plugin** (dünner Wrapper um `kkm/plugins/axis/vapix.py`).

---

## 2. Was Hanwha technisch anbietet — SUNAPI

Hanwha-Kameras (Wisenet X/P/Q/A/L, „Wisenet 7") sprechen **SUNAPI** — HTTP-CGI,
zustandslos, im Aufbau sehr ähnlich zu Axis VAPIX.

| Aspekt | Hanwha SUNAPI |
|---|---|
| Transport | HTTP(S)-GET/POST, Query-String-basiert |
| Basis-Pfad | `/stw-cgi/` |
| Auth | **HTTP Digest** (stdlib `urllib` beherrscht das — wie VAPIX) |
| Ports | 80 / 443 (Default), konfigurierbar |
| Default-IP werksneu | 192.168.1.100 |
| Discovery | **ONVIF WS-Discovery + mDNS + UPnP** (offiziell unterstützt) |

Bekannte CGI-Module: `system.cgi` (Geräteinfo, Reset, Firmware), `network.cgi` (IP),
`users.cgi` (Benutzer), `security.cgi`, `attributes.cgi` (Fähigkeiten/Modell).

Belegtes Beispiel (Geräteinfo):
`http://<ip>/stw-cgi/system.cgi?msubmenu=deviceinfo&action=view`

---

## 3. Capability-Mapping — was realistisch geht

| Capability | Weg | Machbarkeit |
|---|---|---|
| `DISCOVER` | WS-Discovery (unsere `onvif/discovery.py` wiederverwendbar) oder mDNS | ✅ leicht |
| `ONLINE_CHECK` | HTTP-Probe auf `/stw-cgi/…` oder ONVIF `GetSystemDateAndTime` | ✅ leicht |
| `DEVICE_INFO` | `system.cgi?msubmenu=deviceinfo` | ✅ (Beispiel belegt) |
| `SET_IP` | `network.cgi` (Interface/DHCP) | ⚠️ Parameter aus SUNAPI-Ref nötig |
| `USERS` | `users.cgi` | ⚠️ dito |
| `ONVIF_USERS` | ONVIF-SOAP (`onvif/soap.py` wiederverwendbar) | ✅ |
| `FACTORY_RESET` | `system.cgi` oder ONVIF `SetSystemFactoryDefault` | ⚠️/✅ |
| `FIRMWARE` (Upload) | `system.cgi` Multipart-Upload | ⚠️ riskant, undokumentiert |
| `FIRMWARE_CHECK` | — | ❌ kein öffentliches Repo wie `ftp.axis.com`; Firmware hinter Login |
| `CONFIG` (Vorlage) | — | ❌ nur opaker Backup-Blob (gleiche Begründung wie ONVIF-Plugin) |

**Empfohlener Zuschnitt** (analog ONVIF-Plugin, aber mit SUNAPI-Extras):
`DISCOVER, ONLINE_CHECK, DEVICE_INFO, SET_IP, USERS, ONVIF_USERS, FACTORY_RESET`.
Kein `FIRMWARE_CHECK`, kein `CONFIG`.

---

## 4. Die Haken

Zwei Dinge fehlen, die bei Axis vorhanden waren:

1. **Die vollständige SUNAPI-Referenz ist nicht öffentlich.** Anders als VAPIX (frei
   im Web) ist das komplette SUNAPI-PDF **NDA-/vertriebsgebunden** (über einen
   Hanwha-Vertriebskontakt). Öffentlich belegt sind Endpunkt-Form und einzelne
   Beispiele — nicht der genaue Parametersatz für „IP setzen", „Benutzer anlegen"
   usw. Genau den brauchen wir wortgenau.
2. **Zum Verifizieren braucht es eine echte Hanwha-Kamera.** Das ONVIF-Plugin wurde
   gegen eine reale AXIS P3245-V geprüft. Für Hanwha-SUNAPI (Digest-Details, exakte
   CGI-Strings, Reset-Verhalten) ist eine Testkamera praktisch unverzichtbar.

**Wege an die genauen Aufrufe:**
- (a) SUNAPI-Doku über Hanwha anfragen.
- (b) An einer echten Kamera die Web-UI im Browser-DevTools mitschneiden und die
  CGI-Strings ableiten (so entstand seinerzeit auch `vapix.py`).
- (c) Für die standardisierbaren Teile einfach **ONVIF** nutzen — dann ist das
  „Hanwha-Plugin" aber fast identisch zum generischen ONVIF-Plugin und lohnt kaum.

---

## 5. Fazit

Der **Code-seitige Aufwand ist gering** (ein Paket wie `onvif/`, ~300–500 Zeilen,
kein Eingriff in `core`/`gui`). Der **eigentliche Aufwand liegt im Beschaffen der
genauen SUNAPI-Aufrufe** und im Testen an echter Hardware — nicht im Programmieren.

Nächste Schritte, sobald gewünscht:
- **A** — SUNAPI-Grundgerüst bauen (`hanwha/` mit Digest-Client,
  WS-Discovery-Wiederverwendung, `deviceinfo` als belegtem Erstaufruf), Rest als TODO
  bis Hardware/Doku vorliegt.
- **B** — Warten auf Hanwha-Kamera und/oder SUNAPI-Doku, dann verifiziert bauen.

---

## Quellen

- Genetec – Integrating Hanwha units using SUNAPI:
  https://techdocs.genetec.com/r/en-US/Security-Center-Video-Unit-Configuration-Guide-5.12.1.0/Notes-about-integrating-Hanwha-units-using-SUNAPI
- Hanwha Vision Support – Sending SUNAPI CGI Commands:
  https://support.hanwhavisionamerica.com/hc/en-us/articles/39885595955227-HealthPro-Sending-SUNAPI-CGI-Commands-from-HealthPro
- Hanwha Vision Support – Factory reset a Hanwha camera:
  https://support.hanwhavisionamerica.com/hc/en-us/articles/4416795059483-How-do-I-factory-reset-a-Hanwha-camera
- Wisenet WAVE – Advanced Camera Settings via ONVIF:
  https://wavevms.com/wavefeatures/advanced-camera-settings-via-onvif/
- Wisenet (Hanwha) Default IP, Login, Port:
  https://www.videoexpertsgroup.com/glossary/wisenet-default-ip-login-password
