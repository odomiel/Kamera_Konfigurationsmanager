# AXIS OS 13 — VAPIX-Änderungen und Auswirkung auf den Kamera_Konfigurationsmanager

**Stand der Recherche:** 2026-08-09. AXIS OS 13 ist noch nicht offiziell veröffentlicht.
Zeitplan lt. Axis: **Preview mit allen Breaking Changes seit April 2026** zum Testen
verfügbar, **finale Auslieferung September 2026**. Treiber der Änderungen sind
Sicherheits-/Regulierungsvorgaben (EU Cyber Resilience Act, ANSSI, JC-Star) — Axis
entfernt gezielt Alt-APIs, um Komplexität und Angriffsfläche zu senken.

> Diese Notiz ist eine **Recherche**, keine Umsetzung. Der einzig verlässliche Test ist
> die offizielle **OS-13-Preview an echter Hardware** — Axis stellt sie genau dafür bereit.

## Was AXIS OS 13 an VAPIX ändert (bestätigt aus mehreren Quellen)

- **`param.cgi` bleibt** die aktive Parameter-Management-Schnittstelle. Entfernt/deprecatet
  werden **einzelne** Parameter/Funktionen, nicht das CGI als Ganzes:
  - Overlay-Änderung über `param.cgi` → **deprecated**.
  - `root.StreamCache.Size` → auf Produkten ohne Video **entfernt**.
  - diverse „obsolete" Parameter (u. a. `audiooutput` → `audiodeviceid`/`audioouputid`).
- **> 50 VAPIX-APIs entfernt**: legacy **PTZ**-Endpunkte, ältere **Streaming**-Parameter,
  **SNMP**-Konfiguration, **„file upload functionality"**.
- **`time.cgi` deprecated** → neue **Time API**.
- **SNMP-Teil der Network-Settings-API deprecated** → Device-Configuration-SNMP-API.
- **Trigger-Data** (in H.264/MJPEG-Headern) deprecated → Event-Data-Streaming.
- **Authentifizierung:** neu **OAuth 2.0 (RFC 6749 Client Credentials)** für M2M;
  **HTTP-Digest bleibt**. Unabhängig davon härtet Axis seit OS 11/12 zunehmend, dass
  **Basic-Auth deaktiviert** ist (nur Digest).
- **Neue „Param API" (REST/JSON):** `/config/rest/param/v2beta` (GET/PATCH), gleiche
  `/config/rest/`-Familie wie die schon genutzte Geräte-Sicherung (`$export`/`$import`).
  **Noch BETA**, „backward-incompatible changes" möglich; `param.cgi` bleibt vorerst die
  maßgebliche Quelle. → Das ist die „neue Version", der langfristige Nachfolger von
  `param.cgi`, aber **noch nicht** produktiv einsetzbar.

## Ist-Nutzung im Programm (`kkm/plugins/axis/vapix.py`) → OS-13-Status

| Endpunkt / Nutzung | Wofür | OS-13-Status | Handlungsbedarf |
| --- | --- | --- | --- |
| `param.cgi?action=list/update`, `Network.*` (`BootProto`/`IPAddress`/`SubnetMask`/`DefaultRouter`) | IP/DHCP setzen | Kern-Parameter, **kein** Removal angekündigt | An Preview verifizieren |
| `param.cgi?action=list` `Properties.Firmware.Version`, `StreamProfile.S#`, Geräteinfo | Info, Stream-Profile | Standard-Parameter, kein Removal angekündigt | An Preview verifizieren |
| `param.cgi?action=update` **beliebige Parameter aus `.cfg`** (ADM-Import) | Konfig-Import | **Risiko**: eine Quell-`.cfg` kann in OS 13 entfernte/obsolete Parameter enthalten → Gerät lehnt sie ab | **Robustheit erhöhen** (s. u.) |
| `pwdgrp.cgi` | Benutzerverwaltung | kein Deprecation-Hinweis | An Preview verifizieren |
| `basicdeviceinfo.cgi` (JSON) | Geräteinfo | modern, empfohlen | keiner |
| `firmwaremanagement.cgi` (JSON) | Firmware (primär) | **empfohlene** API | keiner |
| `firmwareupgrade.cgi` (Legacy) | Firmware (nur Fallback) | evtl. unter „file upload" betroffen; auf OS-13-Geräten aber **nie erreicht** (firmwaremanagement vorhanden) | unkritisch |
| `factorydefault.cgi` / `hardfactorydefault.cgi` | Werksreset | kein Deprecation-Hinweis | An Preview verifizieren |
| `applications/control.cgi`, `/local/vmd/control.cgi` | VMD4-App/-Konfig | kein direkter Hinweis; „ältere Streaming-Parameter" beobachten | An Preview verifizieren |
| `/config/rest/$export` / `$import` (DCA) | Konfig-Backup | modern, **zukunftssicher** | keiner |
| `/onvif/device_service`, `/vapix/services` (SOAP) | ONVIF-Suche/-Info/-User | Standard | keiner |
| HTTP-Digest (mit Basic-Fallback) | Auth aller Aufrufe | Digest bleibt; Basic evtl. wirkungslos | Digest-first ist bereits korrekt; Fallback belassen (harmlos) |

## Bewertung

**Entwarnung im Kern:** Nichts von dem, was das Programm nutzt, steht auf der bekannten
OS-13-Removal-Liste (PTZ, SNMP, `time.cgi`, Trigger-Data, Overlay-über-param, alte
Streaming-Parameter, `audiooutput`). Die genutzten `param.cgi`-Gruppen (`Network.*`,
`Properties.*`, `StreamProfile.*`), `pwdgrp.cgi`, `basicdeviceinfo.cgi`,
`firmwaremanagement.cgi`, DCA und ONVIF sind Kern-/Modern-APIs ohne angekündigtes Removal.

**Reale Risiken (an der Preview zu verifizieren):**
1. **ADM-Konfig-Import** überträgt beliebige Parameter aus einer `.cfg`. Enthält die
   Quelldatei (von einer OS-≤12-Kamera oder ADM-Export) einen in OS 13 entfernten
   Parameter, lehnt das Zielgerät ihn ab. Das Programm überspringt bisher nur
   `Properties.*` (read-only) — sonstige abgelehnte Parameter könnten den Import stören.
2. **`firmwareupgrade.cgi` (Legacy-Upload)** könnte unter „file upload" fallen. Auf
   OS-13-Geräten ist der Pfad ohnehin tot (firmwaremanagement.cgi vorhanden) — nur den
   Legacy-Zweig nicht als primär betrachten.
3. **Basic-Auth-Fallback** ist auf gehärteten Geräten wirkungslos (nur Digest). Da das
   Programm Digest zuerst versucht, funktioniert es; der Fallback ist harmlos.

## Empfohlene Schritte (priorisiert)

1. **Jetzt, risikolos:** ADM-Import robuster machen — vom Gerät **abgelehnte Einzel-
   Parameter tolerant überspringen und im Ergebnis-Log ausweisen**, statt den ganzen
   Import scheitern zu lassen. Nützt heute schon bei Modell-/Firmware-Unterschieden und
   deckt künftige OS-13-Parameter-Removals ab.
2. **Ab der Preview (seit April 2026):** Alle Axis-Aktionen gegen ein OS-13-Preview-Gerät
   testen — IP/DHCP, Benutzer, ONVIF-Benutzer, Konfig-Ex/Import, Konfig-Backup, Firmware,
   Werksreset, Geräteinfo, Werkszustandserkennung. Nur so zeigen sich echte Auswirkungen.
3. **Mittelfristig:** Migration der `param.cgi`-Nutzung auf die **Param API
   `/config/rest/param/v2beta`** bzw. die Network-Settings-API vormerken — **erst wenn
   nicht mehr Beta**. Das Programm hat mit dem DCA-Konfig-Backup bereits einen Fuß in der
   `/config/rest/`-Familie.
4. **Kein Handlungsbedarf:** OAuth 2.0 ist für dieses Konfig-Tool nicht nötig
   (interaktives Digest genügt).

## Quellen

- [AXIS OS 13 breaking changes (Axis)](https://www.axis.com/for-developers/news/AXIS-OS-13-breaking-changes)
- [AXIS OS 13 lands in September … breaking changes (Analyse)](https://www.securitystandards.ca/news/axis-os-13-breaking-changes/)
- [Param API (REST, /config/rest/param/v2beta)](https://developer.axis.com/vapix/device-configuration/param-api/)
- [Parameter management (param.cgi)](https://developer.axis.com/vapix/network-video/parameter-management/)
- [Network settings API](https://developer.axis.com/vapix/network-video/network-settings-api/)
- [Firmware management API](https://developer.axis.com/vapix/network-video/firmware-management-api/)
- [Authentication (VAPIX)](https://developer.axis.com/vapix/authentication/)
- [AXIS OS Lifecycle guide](https://help.axis.com/en-us/axis-os)
