# Recherche: Hikvision-Plugin

*Stand: 2026-07-17. Machbarkeits- und Aufwandsanalyse, noch keine Umsetzung.*

Ziel: Ein Hersteller-Plugin für Hikvision-Kameras, das (wie das Axis-Plugin) die
Kern-Funktionen anbietet. Dieses Dokument hält fest, **was der Code verlangt**, **was
Hikvision technisch liefert** und **wo die Haken liegen.**

> Kurzfazit vorweg: Von den bisher betrachteten Fremdherstellern ist Hikvision der
> **am besten geeignete** — ISAPI ist REST-artig, HTTP-Digest, halb-öffentlich
> dokumentiert und deckt sogar den Firmware-Upload ab. Es fehlt (wie bei Hanwha) nur
> ein offenes Firmware-Repo für die *Update-Suche* und eine Parameter-Vorlage für
> `CONFIG`.

---

## 1. Was das Programm von einem Plugin verlangt

(identisch zur Hanwha-Notiz — hier nur kurz)

Ein neues Plugin = **ein neues Paket `kkm/plugins/hikvision/`** mit einer
`VendorPlugin`-Unterklasse, registriert in `build_registry()`
(`kkm/plugins/__init__.py`). **Nichts in `core` oder `gui` ändert sich.**

Pflicht: `discover(timeout)`, `check_online(camera, creds)`.
Optional je `Capability.*`: `device_info`, `set_static_ip`/`set_dhcp`,
`add_user`/`set_user_password`, `add_onvif_user`/…, `upgrade_firmware`,
`firmware_updates`/…, `parse_config_file`/`import_config`/…, `factory_reset`.
Klassen-Attribute `USER_ROLES` / `ONVIF_LEVELS` für die Dialoge.

Vorlagen im Baum: **ONVIF-Plugin** (`kkm/plugins/onvif/`) und **Axis-Plugin**
(Wrapper um `vapix.py`). Für Hikvision passt das Axis-Muster gut, weil ISAPI wie
VAPIX HTTP-CGI/REST mit Digest ist.

---

## 2. Was Hikvision technisch anbietet — ISAPI

Hikvision-Geräte sprechen **ISAPI** (Intelligent Security API) — ein HTTP-/REST-
Protokoll, das VAPIX sehr ähnlich ist.

| Aspekt | Hikvision ISAPI |
|---|---|
| Transport | HTTP(S), REST (GET liest, PUT/POST schreibt) |
| Basis-Pfad | `/ISAPI/…` |
| Datenformat | XML; viele Endpunkte auch JSON via `?format=json` |
| Auth | **HTTP Digest** (uhrzeitempfindlich: >5 min Drift → 401; NTP wichtig) |
| Sperre | 5 Fehlversuche → Admin 30 min gesperrt (`<lockStatus>locked</lockStatus>`) |
| Ports | 80 / 443 (Default), konfigurierbar |
| Discovery | **SADP** (UDP-Multicast `239.255.255.250:37020`, ONVIF-nah) *oder* Standard-ONVIF-WS-Discovery |

Belegte Endpunkte:
- Geräteinfo: `GET /ISAPI/System/deviceInfo` (`?format=json` möglich)
- Netzwerk: `GET/PUT /ISAPI/System/Network/interfaces`, `.../interfaces/1/ipAddress`
- Benutzer: `GET/POST/PUT/DELETE /ISAPI/Security/users`, Prüfung `/ISAPI/Security/userCheck`
- Werksreset: `PUT /ISAPI/System/factoryReset`
- Firmware-Upload: `PUT /ISAPI/System/updateFirmware` (Datei `*.dav`), Fortschritt
  `GET /ISAPI/System/upgradeStatus`
- Fähigkeiten/Modell: `.../capabilities`-Endpunkte je Modul

Die ISAPI-Spezifikation ist offiziell über das Hikvision TPP (Technology Partner
Portal, License Agreement) erhältlich, kursiert aber auch als **halb-öffentliches
PDF** (SDK-Spiegel auf GitHub, „IP Surveillance API User Guide") — anders als Hanwha
SUNAPI ist der Endpunktsatz also praktisch frei einsehbar.

---

## 3. Capability-Mapping — was realistisch geht

| Capability | Weg | Machbarkeit |
|---|---|---|
| `DISCOVER` | SADP-UDP-Multicast oder WS-Discovery (`onvif/discovery.py` wiederverwendbar) | ✅ machbar |
| `ONLINE_CHECK` | HTTP-Probe auf `/ISAPI/System/deviceInfo` (401 = online) | ✅ leicht |
| `DEVICE_INFO` | `GET /ISAPI/System/deviceInfo` | ✅ belegt |
| `SET_IP` | `PUT /ISAPI/System/Network/interfaces/1/ipAddress` (+ DHCP-Umschaltung) | ✅ belegt |
| `USERS` | `POST/PUT /ISAPI/Security/users` | ✅ belegt |
| `ONVIF_USERS` | ONVIF-SOAP (`onvif/soap.py` wiederverwendbar) | ✅ |
| `FIRMWARE` (Upload) | `PUT /ISAPI/System/updateFirmware` + `upgradeStatus` | ✅ belegt (`.dav`) |
| `FACTORY_RESET` | `PUT /ISAPI/System/factoryReset` | ✅ belegt |
| `FIRMWARE_CHECK` | — | ❌ kein offenes Repo wie `ftp.axis.com`; Firmware hinter Regional-Portalen, teils Ticket |
| `CONFIG` (Vorlage) | — | ❌ `/ISAPI/System/configurationData` ist opaker, geräte-/verschlüsselter Blob, keine Fleet-Vorlage |

**Empfohlener Zuschnitt** — größer als bei Hanwha, weil ISAPI den Firmware-Upload
sauber standardisiert:
`DISCOVER, ONLINE_CHECK, DEVICE_INFO, SET_IP, USERS, ONVIF_USERS, FIRMWARE,
FACTORY_RESET`. Kein `FIRMWARE_CHECK`, kein `CONFIG`.

---

## 4. Die Haken

Weniger als bei Hanwha, aber vorhanden:

1. **Keine automatisierbare Update-Suche.** Es gibt kein offen browsebares
   Firmware-Verzeichnis wie `ftp.axis.com`. Firmware liegt hinter Regional-Portalen
   (EU/UK/US), modellspezifisch, teils nur per Support-Ticket. Der *Upload* einer
   lokal vorliegenden `.dav` funktioniert per ISAPI — die *Suche* nach neuen
   Versionen lässt sich nicht seriös automatisieren. → `FIRMWARE`, aber kein
   `FIRMWARE_CHECK`.
2. **Keine Konfigurations-Vorlage.** `configurationData` ist ein opaker, oft
   verschlüsselter Geräte-Blob — nichts, was man wie die Axis-ADM-Vorlage über eine
   Flotte ausrollt. → kein `CONFIG` (gleiche Begründung wie beim ONVIF-Plugin).
3. **Digest ist uhrzeitempfindlich + Lockout.** >5 min Uhr-Drift → Auth scheitert;
   5 Fehlversuche → 30 min Sperre. Das Plugin muss saubere Fehlermeldungen liefern
   (Lockout ≠ falsches Passwort) und darf nicht blind retry-en.
4. **Testhardware nötig.** Wie bei ONVIF/Hanwha: die genauen XML-Payloads (v. a.
   `SET_IP`, `USERS`) und das Reset-/Firmware-Verhalten sollten an einer echten
   Hikvision-Kamera verifiziert werden, bevor man sie als „unterstützt" ausweist.

**Wege an die genauen Aufrufe:** ISAPI-PDF (TPP oder halb-öffentlicher Spiegel) +
Gegencheck der XML-Struktur an echter Kamera (Web-UI im Browser-DevTools mitschneiden,
wie seinerzeit bei `vapix.py`).

---

## 5. Fazit

Hikvision ist der **naheliegendste nächste Hersteller** nach Axis: ISAPI ist REST +
Digest wie VAPIX, halb-öffentlich dokumentiert, und deckt sogar den Firmware-Upload
ab. Der Code-Aufwand ist gering (ein Paket wie `axis/` im Kleinen, ~400–700 Zeilen,
kein Eingriff in `core`/`gui`). Aufwand steckt im **Feinschliff der XML-Payloads** und
im **Testen an echter Hardware** — nicht in der Architektur.

Nächste Schritte, sobald gewünscht:
- **A** — ISAPI-Grundgerüst bauen (`hikvision/` mit Digest-Client,
  Discovery-Wiederverwendung, `deviceInfo` + `check_online` als belegter Erstaufruf),
  Schreib-Aktionen als TODO bis Hardware vorliegt.
- **B** — Warten auf Hikvision-Kamera, dann `SET_IP`/`USERS`/`FIRMWARE`/`FACTORY_RESET`
  verifiziert ergänzen.

---

## Quellen

- Intelligent Security API (ISAPI) – SDK/Guide (halb-öffentlicher Spiegel):
  https://raw.githubusercontent.com/loozhengyuan/hikvision-sdk/master/resources/isapi.pdf
- ISAPI & OTAP Developer Guide – Hikvision TPP:
  https://tpp.hikvision.com/download/ISAPI_OTAP
- Hikvision ISAPI Best-Practices (Digest, Endpunkte, Lockout):
  https://github.com/uchkunr/hikvision-best-practices
- Reverse Engineering des SADP-Tools (Discovery, UDP 37020):
  https://sergei.nz/reverse-engineering-hikvision-sadp-tool/
- Firmware-Upgrade per ISAPI (`updateFirmware`, `.dav`):
  https://bytefreaks.net/howtos/upgrading-your-hikvision-dvr-firmware-using-the-api-a-step-by-step-guide
- Firmware-Download (Regional-Portal, modellspezifisch):
  https://www.hikvision.com/en/support/download/firmware/
