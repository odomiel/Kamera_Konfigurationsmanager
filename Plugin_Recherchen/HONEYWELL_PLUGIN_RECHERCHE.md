# Recherche: Honeywell-Plugin

*Stand: 2026-07-19. Machbarkeits- und Aufwandsanalyse, noch keine Umsetzung.*

Ziel: Ein Hersteller-Plugin für **Honeywell**-Netzwerkkameras (Reihen equIP,
Performance Series, HQA/„30 Series"; MAXPRO-Ökosystem).

> Kurzfazit vorweg: Wie ABUS ist Honeywell im API-Sinn **kein einheitlicher
> Hersteller, sondern mehrere OEM-Plattformen unter einer Marke.** Die **Performance
> Series** ist **Dahua-OEM** (→ Dahua HTTP API), die **equIP Series** ist bewusst
> **ONVIF-offen**, ältere Reihen stammen von weiteren OEMs. Der praktische Nutzen
> entsteht daher über ein **Dahua-Plugin** (Performance) plus das generische
> **ONVIF-Plugin** (equIP/Rest) — ein *eigenständiges* Honeywell-Plugin lohnt kaum.

---

## 1. Was das Programm von einem Plugin verlangt

(wie in den anderen Notizen) Ein neues Plugin = ein Paket `kkm/plugins/honeywell/`
mit `VendorPlugin`-Unterklasse, registriert in `build_registry()`. **Aber:** Bei
OEM-Ware gibt es keine eigene API zu kapseln — das Plugin wäre nur eine Weiche auf
Dahua- bzw. ONVIF-Protokolle.

---

## 2. Was Honeywell technisch anbietet — je nach Reihe fremde Protokolle

| Reihe | Tatsächliche Herkunft | Protokoll |
|---|---|---|
| **Performance Series** (H4W/H4L/HBW…) | **Dahua-OEM** | **Dahua HTTP API** (`/cgi-bin/…`, Digest) + ONVIF |
| **equIP Series** | Honeywell, bewusst offen | **ONVIF** (+ RTSP/HTTP), CGI-Anteile Dahua-nah |
| ältere Reihen (HD3, CADVR-OEMs, „30 Series"/HQA) | diverse OEMs | überwiegend **ONVIF** |
| MAXPRO NVR/VMS-Ökosystem | Honeywell | proprietär (für dieses Tool irrelevant — wir konfigurieren Kameras, kein VMS) |

Belege: Honeywell-Doku führt die Performance-/equIP-Reihen durchgängig als
**ONVIF/RTSP/HTTP**; die Performance-CGIs entsprechen der Dahua-Implementierung
(Honeywell-Kameras sind „generally OEM'd by Dahua"). Eine offene, Honeywell-*eigene*
HTTP-API-Referenz existiert **nicht**.

---

## 3. Capability-Mapping — der realistische Weg

Kein sinnvoller Honeywell-eigener Endpunktsatz zu kapseln. Bedienung über die
tatsächliche Plattform:

| Fall | Bedienung im Programm mit Plugins |
|---|---|
| Honeywell Performance = Dahua-OEM | **Dahua-Plugin** (sobald gebaut, siehe `DAHUA_PLUGIN_RECHERCHE.md`) — deckt `SET_IP`, `USERS`, `FIRMWARE`, `FACTORY_RESET` über die Dahua HTTP API ab |
| equIP / ältere / nur ONVIF | **generisches ONVIF-Plugin** — `DISCOVER, ONLINE_CHECK, DEVICE_INFO, SET_IP, ONVIF_USERS, FACTORY_RESET` |

Ein *dediziertes* `honeywell/`-Plugin könnte höchstens „ist das ein Dahua-OEM?"
erkennen und dann die Dahua-Aufrufe verwenden — also genau das, was ein Dahua-Plugin
ohnehin tut. Mehrwert ≈ null.

---

## 4. Die Haken

1. **Kein einheitliches Honeywell-Protokoll.** „Honeywell" spannt über mindestens
   drei OEM-Plattformen (Dahua + equIP + ältere). Laufzeit-Erkennung der Herkunft
   ohne eigenen Ertrag.
2. **Keine offene API-Doku unter dem Namen Honeywell.** Man landet bei der Dahua
   HTTP API (Performance) oder ONVIF — beides separat abgedeckt (bzw. abdeckbar).
3. **Dahua-Discovery/-Digest gelten auch hier.** Uhrzeit-/Lockout-Empfindlichkeit und
   das UDP-37810-Discovery aus der Dahua-Notiz treffen 1:1 auf die Performance-Reihe
   zu.
4. **Namens-/Modellwirrwarr.** Über die Jahre wechselnde OEMs (auch Nicht-Dahua) —
   eine „Honeywell erkannt → so bedienen"-Logik wäre fragil.

---

## 5. Fazit

**Ein eigenständiges Honeywell-Plugin lohnt sich nicht.** Der praktische Nutzen
entsteht über zwei andere Wege:

- **Honeywell Performance Series (Dahua-OEM):** über das **Dahua-Plugin** (sobald
  gebaut). Das ist die eigentliche Empfehlung — **ein Dahua-Plugin schlägt zwei
  Fliegen** (Dahua *und* Honeywell Performance, dazu Amcrest u. a.).
- **equIP / ältere / nur ONVIF:** über das **generische ONVIF-Plugin**.

Empfehlung: **kein Honeywell-Code.** Priorität stattdessen auf das **Dahua-Plugin**
legen (siehe `DAHUA_PLUGIN_RECHERCHE.md`); danach in Doku/HILFE vermerken, dass
Honeywell-Performance-Kameras über das Dahua-Plugin und equIP/ältere über das
ONVIF-Plugin laufen. Der Architektur-Aufbau bliebe unverändert möglich, falls je eine
Honeywell-Reihe mit eigener, offener API auftaucht.

---

## Quellen

- Honeywell IP-Kamera-Setup (ONVIF/RTSP/HTTP, Performance/equIP):
  https://www.ispyconnect.com/camera/honeywell
- Honeywell Performance Series IP Camera User Guide (ONVIF-Konfiguration):
  https://prod-edam.honeywell.com/content/dam/honeywell-edam/hbt/en-us/documents/manuals-and-guides/user-manuals/HBT-SEC-PerformanceSeriesCamera-UserGuide-UG-EN.pdf
- Honeywell = Dahua-OEM (Performance Series), IPVM/Community:
  https://ipcamtalk.com/threads/anyone-experienced-with-non-honeywell-ip-cams-on-a-honeywell-nvr.62534/
- Dahua HTTP API (die tatsächliche Schnittstelle der Performance Series) — siehe
  `DAHUA_PLUGIN_RECHERCHE.md`.
