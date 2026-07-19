# Recherche: ABUS-Plugin

*Stand: 2026-07-19. Machbarkeits- und Aufwandsanalyse, noch keine Umsetzung.*

Ziel: Ein Hersteller-Plugin für **ABUS**-Netzwerkkameras (deutscher Anbieter, u. a.
Reihen TVIP / IPCB / IPCS / „PPIC").

> Kurzfazit vorweg: **ABUS ist kein eigener Kamera-Hersteller im API-Sinn — es ist
> überwiegend OEM-Ware.** Die meisten ABUS-Netzwerkkameras sind **rebrandete
> Hikvision-Geräte** (belegbar am Hikvision-typischen RTSP-Pfad
> `/Streaming/Channels/1` und an ISAPI-Endpunkten); ältere/kleinere Reihen stammen von
> anderen OEMs und können praktisch nur **ONVIF**. Ein *eigenständiges* ABUS-Plugin
> lohnt daher kaum — der Nutzen entsteht über das (experimentelle) **Hikvision-Plugin**
> plus das generische **ONVIF-Plugin**.

---

## 1. Was das Programm von einem Plugin verlangt

(wie in den anderen Notizen) Ein neues Plugin = ein Paket `kkm/plugins/abus/` mit
`VendorPlugin`-Unterklasse, registriert in `build_registry()`. **Aber:** Bei einem
reinen OEM-Rebrand gibt es **keine eigene API** zu kapseln — das Plugin wäre nur eine
Weiche auf schon vorhandene Protokolle.

---

## 2. Was ABUS technisch anbietet — meist fremde Protokolle

| Reihe / Typ | Tatsächliche Herkunft | Protokoll |
|---|---|---|
| Neuere IP-Kameras (TVIP-4/5, IPCS/IPCB, PPIC) | **Hikvision-OEM** | **ISAPI** (`/ISAPI/…`, HTTP-Digest) + ONVIF; RTSP `/Streaming/Channels/1` |
| Ältere/kleinere Reihen, PIR-Cams | diverse OEMs (u. a. TVT/„IPC"-Chinaplattform) | überwiegend nur **ONVIF** (+ herstellerspezifisches Web-UI) |
| Alle unterstützten | — | **ONVIF** (Auto-Discovery), RTSP 554, HTTP 80 |

Belege: ABUS-RTSP-Beispiel `rtsp://admin:admin@…:554/Streaming/Channels/1` = exakt der
**Hikvision**-Pfad; Setup-Guides führen ABUS durchgängig als **ONVIF/RTSP**-Gerät.
Eine offene, ABUS-*eigene* HTTP-API-Referenz existiert **nicht** — ABUS liefert das
Windows-Tool „IP Installer"/„ABUS IPCManager" (Discovery + IP-Vergabe), keine
dokumentierte Programmierschnittstelle.

---

## 3. Capability-Mapping — der realistische Weg

Es gibt **keinen sinnvollen ABUS-eigenen Endpunktsatz** zu kapseln. Der Weg ist,
ABUS-Geräte über ihre **tatsächliche** Plattform zu bedienen:

| Fall | Bedienung im Programm heute/mit Plugins |
|---|---|
| ABUS = Hikvision-OEM | **Hikvision-Plugin** (experimentell) — ISAPI deckt `SET_IP`, `USERS`, `FIRMWARE`, `FACTORY_RESET` ab; SADP-Discovery findet auch die ABUS-Rebrands |
| ABUS = anderer OEM / nur ONVIF | **generisches ONVIF-Plugin** — `DISCOVER, ONLINE_CHECK, DEVICE_INFO, SET_IP, ONVIF_USERS, FACTORY_RESET` |

Ein *dediziertes* `abus/`-Plugin könnte höchstens die Erkennung „ist das ein
Hikvision-OEM?" bündeln und dann intern die ISAPI-Aufrufe aufrufen — das ist aber
genau das, was das Hikvision-Plugin schon tut. Mehrwert ≈ null.

---

## 4. Die Haken

1. **Kein einheitliches ABUS-Protokoll.** „ABUS" ist ein Label über mindestens zwei
   verschiedenen OEM-Plattformen (Hikvision + diverse). Ein Plugin müsste zur Laufzeit
   erst die Herkunft erkennen — Aufwand ohne eigenen Ertrag.
2. **Keine offene API-Doku.** Es gibt keine „ABUS HTTP API"; man landet zwangsläufig
   bei ISAPI (Hikvision) oder ONVIF — beides schon abgedeckt.
3. **SADP findet die Hikvision-OEMs bereits.** Die Hikvision-SADP-Discovery
   (`kkm/plugins/hikvision/discovery.py`) antwortet auch bei ABUS-Rebrands; die
   Geräteinfo meldet dann Hikvision-typische Felder.
4. **Rechtsklick-Öffnen/Weboberfläche** funktioniert ohnehin herstellerunabhängig.

---

## 5. Fazit

**Ein eigenständiges ABUS-Plugin lohnt sich nicht.** ABUS ist OEM-Ware; der praktische
Nutzen entsteht über zwei bereits vorhandene Wege:

- **ABUS = Hikvision-OEM (Mehrzahl der aktuellen IP-Kameras):** das **Hikvision-Plugin**
  (experimentell) einschalten — SADP-Discovery + ISAPI decken die Kernfunktionen ab.
- **ABUS = anderer OEM / nur ONVIF:** das **generische ONVIF-Plugin** einschalten.

Empfehlung: **kein Code.** Stattdessen — sobald das Hikvision-Plugin an echter Hardware
verifiziert ist — in der Doku/HILFE vermerken, dass ABUS-Kameras je nach Modell über
das Hikvision- oder das ONVIF-Plugin laufen. Sollte künftig eine ABUS-Reihe mit
*eigener*, offener API auftauchen, ist der Architektur-Aufbau (ein Paket unter
`kkm/plugins/`) unverändert möglich.

---

## Quellen

- ABUS IP-Kamera-Setup (ONVIF/RTSP, `/Streaming/Channels/1` = Hikvision-Pfad):
  https://www.ispyconnect.com/camera/abus
- „IPC"-Sammelprofil (China-OEM-Plattform, viele Rebrands inkl. ABUS-Teilen):
  https://www.ispyconnect.com/camera/ipc
- Hikvision-OEM-Verzeichnis (Rebrand-Praxis, verdeckte OEMs):
  https://ipvm.com/reports/hik-oems-dir
- ABUS-Kamera-Handbuch (TVIP-Reihe, ONVIF/RTSP):
  https://c1.abus.com/var/ImagesPIM/d110001/medias/docus/19/ABUS-TVIPxxxxx_BDA_US_1.0.pdf
- ABUS über VMS/ONVIF anbinden:
  https://smartvision.dev/vms-software/how-to-connect-to-abus-ip-cameras.htm
