# Recherche: Dahua-Plugin

*Stand: 2026-07-19. Machbarkeits- und Aufwandsanalyse, noch keine Umsetzung.*

Ziel: Ein Hersteller-Plugin für **Dahua**-Kameras (und die zahlreichen Dahua-OEMs —
u. a. Amcrest, Honeywell Performance, teils Lorex), das wie das Axis- und das
Hikvision-Plugin die Kern-Funktionen anbietet.

> Kurzfazit vorweg: Dahua ist **nach Axis der zweitbeste Kandidat — gleichauf mit
> oder besser als Hikvision.** Die HTTP-API ist REST-/CGI-artig (`/cgi-bin/…`),
> HTTP-Digest, **sehr gut halb-öffentlich dokumentiert** („Dahua HTTP API"-PDF,
> mehrere Versionen frei im Netz), hat ein **eigenes Discovery-Protokoll** (UDP
> 37810, liefert MAC) und deckt Firmware-Upload **und** — anders als Hikvision — eine
> brauchbare Konfigurations-Schnittstelle (`configManager`, `KEY=VALUE` wie Axis
> `param.cgi`) ab. Es fehlt nur ein offenes Firmware-Repo für die *Update-Suche*.

---

## 1. Was das Programm von einem Plugin verlangt

(wie in den anderen Notizen — kurz)

Ein neues Plugin = **ein neues Paket `kkm/plugins/dahua/`** mit einer
`VendorPlugin`-Unterklasse, registriert in `build_registry()`. **Nichts in `core`
oder `gui` ändert sich.** Bis zur Verifikation an echter Hardware `experimental =
True` (Plugin-Manager kennzeichnet es, ab Werk aus — wie beim Hikvision-Plugin).

Vorlagen im Baum: **Hikvision-Plugin** (`isapi.py` + SADP-Discovery + Digest-Client,
experimentell) ist die nächstliegende Blaupause — Dahuas UDP-Discovery und
CGI/Digest sind strukturell fast identisch. Zusätzlich **Axis-Plugin** (CGI-Muster,
`configManager` ähnelt `param.cgi`) und **ONVIF-Plugin** (ONVIF-Benutzer via
`onvif/soap.py`).

---

## 2. Was Dahua technisch anbietet — HTTP API

Dahua-Geräte sprechen die **Dahua HTTP API** — HTTP-CGI unter `/cgi-bin/`, sehr nah
an Axis VAPIX / Hikvision ISAPI.

| Aspekt | Dahua HTTP API |
|---|---|
| Transport | HTTP(S), CGI (`?action=getConfig` liest, `?action=setConfig` schreibt) |
| Basis-Pfad | `/cgi-bin/…` |
| Datenformat | `KEY=VALUE`-Zeilen (wie Axis `param.cgi`), teils JSON |
| Auth | **HTTP Digest** (Basic als Rückfall) — stdlib `urllib` beherrscht das |
| Sperre | Konto-Lockout nach zu vielen Fehlversuchen (uhrzeitempfindlich, wie ISAPI) |
| Ports | 80 / 443 (Default), konfigurierbar |
| Discovery | **eigenes Protokoll** (UDP-Multicast **37810**, liefert MAC/Modell/IP) *oder* ONVIF-WS-Discovery |
| Default-Login | `192.168.1.108`, `admin` (Aktivierungs-/Passwortzwang wie Hikvision) |

Belegte Endpunkte (aus dem halb-öffentlichen „Dahua HTTP API"-PDF):
- Geräteinfo: `GET /cgi-bin/magicBox.cgi?action=getDeviceType`,
  `.../getSystemInfo`, `.../getMachineName`, `.../getHardwareVersion`,
  Seriennummer `GET /cgi-bin/magicBox.cgi?action=getSerialNo`,
  Firmware `GET /cgi-bin/magicBox.cgi?action=getSoftwareVersion`
- Konfiguration lesen/schreiben: `GET /cgi-bin/configManager.cgi?action=getConfig&name=Network`,
  `GET /cgi-bin/configManager.cgi?action=setConfig&Network.eth0.IPAddress=…` (u. a.
  `Network.eth0.{IPAddress,SubnetMask,DefaultGateway}`, `Network.eth0.DhcpEnable=true`)
- Benutzer: `GET /cgi-bin/userManager.cgi?action=addUser&user.Name=…&user.Password=…&user.Group=admin`,
  `.../modifyPassword`, `.../getUserInfoAll`
- Werksreset: `GET /cgi-bin/configManager.cgi?action=restoreExcept&names[0]=Network`
  (Netzwerk behalten) bzw. `.../configManager.cgi?action=restore` (alles)
- Neustart: `GET /cgi-bin/magicBox.cgi?action=reboot`
- Firmware-Upload: `POST /cgi-bin/upgrade.cgi` (Multipart), Fortschritt
  `GET /cgi-bin/upgrader.cgi?action=getState`

---

## 3. Capability-Mapping — was realistisch geht

| Capability | Weg | Machbarkeit |
|---|---|---|
| `DISCOVER` | Dahua-UDP-Discovery (37810, liefert MAC → stabile Identität) oder ONVIF | ✅ machbar (eigenes Protokoll wie Hikvision-SADP) |
| `ONLINE_CHECK` | HTTP-Probe auf `/cgi-bin/magicBox.cgi?action=getDeviceType` (401 = online) | ✅ leicht |
| `DEVICE_INFO` | `magicBox.cgi` (Typ/Serie/Version) | ✅ belegt |
| `SET_IP` | `configManager.cgi?action=setConfig&Network.eth0.…` (+ DHCP-Schalter) | ✅ belegt |
| `USERS` | `userManager.cgi?action=addUser/modifyPassword` | ✅ belegt |
| `ONVIF_USERS` | ONVIF-SOAP (`onvif/soap.py` wiederverwenden) | ✅ |
| `FIRMWARE` (Upload) | `POST /cgi-bin/upgrade.cgi` + `upgrader.cgi?action=getState` | ✅ belegt (Multipart) |
| `FACTORY_RESET` | `configManager.cgi?action=restore[Except]` (+ `reboot`) | ✅ belegt |
| `FIRMWARE_CHECK` | — | ❌ kein offenes Repo wie `ftp.axis.com`; Firmware hinter Portal/Distributor |
| `CONFIG` (Vorlage) | ggf. `configManager.cgi?action=getConfig` (KEY=VALUE-Dump) | ⚠️ technisch möglich (wie `param.cgi`), aber kein Fleet-Standardformat → 2. Phase, sonst weglassen wie ONVIF/Hikvision |

**Empfohlener Zuschnitt** — der **größte** unter den Fremdherstellern, weil die
Dahua-API den Firmware-Upload und die Konfiguration sauber abbildet:
`DISCOVER, ONLINE_CHECK, DEVICE_INFO, SET_IP, USERS, ONVIF_USERS, FIRMWARE,
FACTORY_RESET`. Kein `FIRMWARE_CHECK`. `CONFIG` optional als spätere Ausbaustufe
(param-basierter Export/Import über `configManager`), zunächst weglassen.

---

## 4. Die Haken

Weniger als bei allen anderen bisher betrachteten Fremdherstellern:

1. **Keine automatisierbare Update-Suche.** Firmware liegt bei Distributoren/hinter
   Portalen, kein offen browsebares Verzeichnis. Der *Upload* per `upgrade.cgi`
   funktioniert; die *Suche* lässt sich nicht seriös automatisieren. → `FIRMWARE`,
   kein `FIRMWARE_CHECK`.
2. **Digest-Lockout + Uhrzeit.** Wie ISAPI: Konto-Sperre nach zu vielen
   Fehlversuchen, Uhr-Drift kann die Anmeldung kippen. Das Plugin braucht saubere
   Fehlermeldungen (Lockout ≠ falsches Passwort) und darf nicht blind retry-en —
   die Logik aus dem Hikvision-`isapi.py` (`_isapi_error`, `IsapiConnectError`) lässt
   sich fast 1:1 übertragen.
3. **Aktivierungszustand werksneu.** Neuere Dahua-Kameras kommen wie Hikvision
   „inaktiv" und verlangen zuerst ein Admin-Passwort — `is_unconfigured` sollte das
   erkennen (analog zur Hikvision-Aktivierungsprüfung).
4. **Testhardware nötig.** Die genauen `setConfig`-Feldnamen (v. a. Netzwerk,
   Benutzergruppen) und das Firmware-/Reset-Verhalten an echter Hardware verifizieren,
   bevor das `experimental`-Flag entfällt. (Die Doku ist gut, aber modellabhängig.)
5. **CVE-Historie.** Dahua hatte mehrere Auth-Bypass-CVEs — kein Problem fürs Plugin,
   aber ein Grund, HTTPS + Digest zu bevorzugen und keine Alt-Endpunkte anzusprechen.

**Wege an die genauen Aufrufe:** „Dahua HTTP API"-PDF (halb-öffentlich, mehrere
Versionen) + Gegencheck an echter Kamera (Web-UI im Browser-DevTools). Referenz-
Client `BourgeoisBear/amdacli` (Amcrest/Dahua) zeigt viele Aufrufe belegt.

---

## 5. Fazit

Dahua ist **der stärkste Fremdhersteller-Kandidat**: eigenes Discovery-Protokoll (mit
MAC), sehr gut halb-öffentlich dokumentierte CGI/Digest-API, Firmware-Upload **und**
eine param-artige Konfigurations-Schnittstelle. Der Code-Aufwand ist gering und die
**Hikvision-Blaupause passt fast 1:1** (Digest-Client, eigenes UDP-Discovery,
Lockout-/Aktivierungs-Behandlung, ONVIF-Benutzer wiederverwendet). Aufwand steckt im
**Feinschliff der `setConfig`-Felder** und im **Testen an echter Hardware** — nicht in
der Architektur.

> **Bonus:** Ein Dahua-Plugin deckt zugleich einen großen Teil der **Honeywell
> Performance Series** (Dahua-OEM) ab — siehe `HONEYWELL_PLUGIN_RECHERCHE.md`.

Nächste Schritte, sobald gewünscht:
- **A** — Grundgerüst bauen (`dahua/` mit Digest-Client nach Hikvision-Vorbild,
  UDP-37810-Discovery, `magicBox`-Parser für `device_info` + `check_online`),
  Schreib-Aktionen nach der HTTP-API-Doku, `experimental = True`, ab Werk aus.
- **B** — an echter Dahua-Kamera `SET_IP`/`USERS`/`FIRMWARE`/`FACTORY_RESET`
  verifizieren, Flag entfernen; optional `CONFIG` (param-basiert) ergänzen.

---

## Quellen

- Dahua HTTP API (halb-öffentliche Spiegel, mehrere Versionen):
  https://wiki.dno-it.ru/wp-content/uploads/2023/06/dahua_http_api_for_ipcsd-v1.40.pdf
- Dahua HTTP API v2 (Scribd-Spiegel):
  https://www.scribd.com/document/634233019/DAHUA-HTTP-API-V2-841-pdf
- Dahua ConfigTool / Discovery (UDP 37810, Geräte-Suche, IP/Firmware):
  https://dahuawiki.com/ConfigTool
- `configManager.cgi` (getConfig/setConfig, Netzwerk/Multicast):
  https://dahuawiki.com/IPCMulticast
- Referenz-Client Amcrest/Dahua HTTP API (belegte Aufrufe):
  https://github.com/BourgeoisBear/amdacli
