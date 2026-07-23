# Recherche: Senstar-Plugin (Schwerpunkt Senstar AIM-A10D)

*Stand: 2026-07-23. Machbarkeits- und Aufwandsanalyse, noch keine Umsetzung.*

Ziel war zu prüfen, was nötig ist, um ein Hersteller-Plugin für Senstar zu schreiben,
insbesondere für den **Senstar AIM-A10D**. Das zentrale Ergebnis vorab, weil es die
ganze Bewertung prägt:

> **Der AIM-A10D ist keine Kamera.** Er ist ein **Thin Client / Netzwerk-Video-Decoder**
> (früher „Aimetis A10D") — eine PoE-Appliance mit Linux, die 1080p-Streams von 30+
> Herstellern **per ONVIF Profil S / RTSP entgegennimmt und über HDMI auf einem Monitor
> anzeigt**. Er *konsumiert* Kamerastreams, er *ist* keine Kamera. Damit passt er
> konzeptionell nur bedingt in einen „Kamera-Konfigurationsmanager" (siehe Abschnitt 4
> und 6).
>
> **Für echte Senstar-*Kameras* (z. B. TC200 thermisch+HD) braucht es gar kein eigenes
> Plugin:** Senstar ist ONVIF-first (Symphony-VMS spricht ONVIF Profil S/T), diese
> Kameras werden bereits vom **generischen ONVIF-Plugin** (`kkm/plugins/onvif/`)
> erfasst — Discovery, Info, IP, ONVIF-Benutzer, Werksreset.

Trotzdem lohnt die Analyse: der AIM-A10D hat eine **sauber dokumentierte REST-API**, und
technisch ließe sich ein Plugin dafür sogar leichter bauen als die CGI/Digest-Plugins.
Die eigentlichen Haken liegen woanders (Discovery, Benutzermodell, „keine Kamera").

---

## 1. Was das Programm von einem Plugin verlangt

Architektonisch ist alles vorbereitet. Ein neues Plugin = **ein neues Paket
`kkm/plugins/senstar/`** mit einer `VendorPlugin`-Unterklasse, registriert in
`build_registry()` (`kkm/plugins/__init__.py`). **Nichts in `core` oder `gui` ändert
sich.**

Pflicht (abstrakt in `VendorPlugin`, `kkm/core/plugins.py`):
- `discover(timeout)` → Liste von Kamera-Dicts (Basisfelder aus `FIELD_NAMES`)
- `check_online(camera, creds)` → bool

Optional, je gemeldeter `Capability.*` freigeschaltet (die GUI grayt den Rest aus):

| Capability | Methoden | Dialog |
|---|---|---|
| `SET_IP` | `set_static_ip` / `set_dhcp` | IP-Dialog |
| `USERS` | `add_user` / `set_user_password` (+ `parse_user_list`, `USER_ROLES`) | Benutzer |
| `ONVIF_USERS` | `add_onvif_user` / `set_onvif_user_password` (+ `ONVIF_LEVELS`) | ONVIF |
| `FIRMWARE` | `upgrade_firmware` | Firmware |
| `FIRMWARE_CHECK` | `firmware_updates` / `firmware_release` / `download_firmware` | Firmware (Online-Suche) |
| `CONFIG` | `parse_config_file` / `write_config_file` / `import_config` | Konfiguration |
| (immer) | `device_info`, `factory_reset` | — |

Zwei Rahmenbedingungen der App, die für Senstar besonders relevant sind:

1. **Die App ist rein Discovery-getrieben.** Geräte gelangen ausschließlich über
   `discover()` eines aktiven Plugins (oder den Axis-ADM-Import) in die Liste — es gibt
   **kein „Gerät manuell per IP hinzufügen"** in der GUI. Ein Plugin, dessen Gerät kein
   Discovery-Protokoll beherrscht, muss `discover()` selbst mit einem Subnetz-Scan füllen.
2. **Transport-Regel** (aus `vapix.py`, in allen Plugins gespiegelt): der
   `scheme="auto"`-HTTPS→HTTP-Rückfall darf **nur** bei Verbindungsfehlern greifen, nie
   bei HTTP 401 (sonst Klartext-Wiederholung + verdoppelte Fehlversuche → Geräte-Sperre).

Vorlagen im Baum: das **ONVIF-Plugin** (stdlib-only, 4 Dateien) und die CGI-Plugins
(Hikvision/Dahua/Hanwha) mit eigenem Client + Digest-Auth.

---

## 2. Was der AIM-A10D technisch anbietet — die Thin-Client-REST-API

Der Thin Client (Firmware/Software 3.x) hat eine **dokumentierte HTTP-REST-API**
(„Aimetis Thin Client API Reference", v2.2.1) sowie SSH- und SNMP-Zugang. Für ein Plugin
zählt die REST-API.

| Aspekt | Thin Client REST-API |
|---|---|
| Transport | **HTTP** (JSON), kein HTTPS in der Doku genannt |
| Auth | **Session-Token** (kein Basic/Digest): `POST /Session` mit Zugangsdaten → GUID im Response-Header `authtoken`; Token danach in jedem Request mitschicken; `DELETE /Session/{token}` beendet |
| Firmware werksneu | über Enterprise Manager / Web-UI konfiguriert; Default-Login nötig (an Hardware zu prüfen) |

**Relevante Endpunkte** (⭐ = deckt eine Capability):

| Zweck | Endpoint | Capability |
|---|---|---|
| Session anlegen/beenden | `POST /Session`, `DELETE /Session/{token}` | (Auth) |
| Alle Einstellungen lesen | `GET /Settings` | `device_info`, `CONFIG` |
| Einstellungen schreiben | `POST /Settings` (`NetworkIP`, `NetworkMask`, `NetworkGW`, `NetworkDNS`, `NetworkMode`, `AdminPassword`, `DeviceName`, `Date`/`Time`/`TimeZone`, `NTPServer`, …) | ⭐ `SET_IP`, teils `USERS`, `CONFIG` |
| Neustart | `GET /System/Restart` | `reboot` |
| Werksreset | `GET /System/Restore` | ⭐ `factory_reset` |
| Firmware online prüfen | `GET /System/Update` (neueste Version), `GET /System/Update/State` (Fortschritt) | ⭐ `FIRMWARE_CHECK` |
| Firmware online aktualisieren | `POST /System/Update` | ⭐ `FIRMWARE_CHECK` |
| Firmware-Datei hochladen | `POST /System/Upload` (Datei; Rückgabe-Code `0` = OK) | ⭐ `FIRMWARE` |

Dazu die Display-/VMS-Endpunkte (`/Panel`, `/Camera`, `/PTZ`) — für den
Konfigurationsmanager **irrelevant** (das ist die Anzeige-Funktion des Decoders, nicht
Geräte-Konfiguration).

Positiv gegenüber den CGI-Vendorn: **sauberes JSON-REST**, ein einziges Settings-Objekt
(read-modify-write, genau das Muster, das wir bei Hikvision/Hanwha ohnehin erzwingen),
und Firmware-Endpunkte inkl. **Online-Update-Prüfung** — Letzteres hat sonst nur Axis.

---

## 3. Capability-Matrix für den AIM-A10D

| Capability | Machbar? | Weg / Einschränkung |
|---|---|---|
| `discover` | ⚠️ **schwierig** | Kein Kamera-Discovery (kein WS-Discovery/mDNS als ONVIF-Gerät). Enterprise Manager findet Geräte zentral (Mechanismus undokumentiert, evtl. SNMP/Broadcast). Realistisch: **Subnetz-Scan** in `discover()` (z. B. Probe auf `POST /Session` bzw. einen leichten GET) — an Hardware zu verifizieren. |
| `check_online` | ✅ | GET auf einen leichten Endpoint / TCP-Probe auf Port 80. |
| `device_info` | ✅ | `GET /Settings` (DeviceName, Netz) + `GET /System/Update` (Version). |
| `SET_IP` | ✅ | `POST /Settings` mit `NetworkMode=Static` + `NetworkIP/Mask/GW/DNS`; DHCP über `NetworkMode`. Volles Settings-Objekt zurückschreiben (read-modify-write). |
| `USERS` | ❌/△ | Nur **ein** `AdminPassword` im Settings-Objekt — **kein** Mehrbenutzer, keine Rollen. Der Benutzer-Dialog (Name + Rolle) passt nicht; höchstens ein degeneriertes „Admin-Passwort ändern". Besser Capability **nicht** melden. |
| `ONVIF_USERS` | ❌ | Das Gerät ist ONVIF-**Client**, kein ONVIF-Server mit Benutzerverwaltung. Nicht zutreffend. |
| `FIRMWARE` | ✅ | `POST /System/Upload` (Datei), Rückgabe-Code auswerten (`0` = OK — gleiche Lektion wie Hikvision/Hanwha: Erfolg steht **im Body**, nicht im HTTP-Status). |
| `FIRMWARE_CHECK` | ✅ (bemerkenswert) | `GET /System/Update` liefert die neueste Version vom Hersteller-Dienst; `POST /System/Update` startet, `/System/Update/State` pollt den Fortschritt. Kein eigenes Repo-Parsing wie bei Axis nötig. |
| `CONFIG` | △ | `GET /Settings` ist ein vollständiges JSON-Objekt → ließe sich als **opakes Geräte-Backup** exportieren/importieren (wie ONVIF `GetSystemBackup`). Keine „Parameter-Vorlage" im Axis-Sinn, aber ein sinnvolles Sichern/Zurückspielen wäre machbar. |
| `factory_reset` | ✅ | `GET /System/Restore`. |
| `reboot` | ✅ | `GET /System/Restart`. |

Kurz: **SET_IP, FIRMWARE, FIRMWARE_CHECK, factory_reset, reboot, device_info** passen
sauber; **USERS/ONVIF_USERS** passen nicht; **CONFIG** nur als opakes Backup.

---

## 4. Haken & Risiken

1. **Konzeptbruch „keine Kamera".** Der AIM-A10D ist eine Anzeige-Appliance. Das Tool
   ist ein *Kamera*-Konfigurationsmanager; ein Decoder in der Geräteliste ist eine
   **Scope-Entscheidung**, keine rein technische. Alles Kamera-Spezifische (ONVIF-Nutzer,
   Bewegungserkennung, Stream-Profile) entfällt.
2. **Discovery ist der eigentliche Aufwand.** Kein Kamera-Discovery-Protokoll; die App
   kennt kein manuelles „per IP hinzufügen". Ein Plugin müsste in `discover()` selbst
   einen **Subnetz-Scan** fahren (Probe auf `/Session` o. Ä.). Alternativ wäre in der GUI
   ein generisches „Gerät per IP hinzufügen" nachzurüsten — das wäre aber eine
   Kern-Änderung außerhalb des Plugin-Seams (aktuell bewusst nicht vorhanden).
3. **Token-Auth statt Digest.** Neues Transport-Muster: erst `POST /Session` →
   `authtoken`-Header, dann Token an jeden Request hängen, am Ende `DELETE /Session`.
   `urllib` kann das problemlos, aber es ist ein eigener kleiner Client (nicht der
   Digest-`HTTPPasswordMgr`-Weg der anderen Plugins). Session-Lebensdauer/Logout beachten.
4. **HTTP-only.** Die Doku nennt kein HTTPS → Token und Admin-Passwort laufen im Klartext.
   Sicherheitshinweis für den Nutzer; wenn das Gerät HTTPS kann, zuerst probieren
   (aber **nicht** blind von 401 auf HTTP zurückfallen — Transport-Regel aus Abschnitt 1).
5. **Erfolg steht im Body, nicht im Status.** `/System/Upload` liefert einen Code
   (`0` = OK) — wie bei Hikvision (`statusCode`) und Hanwha (`OK`/`NG`) darf man dem
   nackten HTTP 200 nicht trauen.
6. **API-Versionierung.** Referenz ist v2.2.1 / Thin-Client-Software 3.x. Ältere/neuere
   Firmware kann Endpunkte verschieben. Nur **ein Modell** im Blick → Plugin würde
   `experimental = True` tragen (ab Werk aus, wie Hikvision/Dahua/Hanwha).
7. **Zugang zum Testgerät + Doku.** Die API-Referenz liegt hinter dem Senstar-xnet
   (Partnerportal); für eine belastbare Umsetzung braucht es das Dokument in Gänze und
   **ein echtes Gerät** (Login werksneu, genaues Settings-Schema, Upload-Format).

---

## 5. Senstar-Kameras statt Thin Client

Falls es eigentlich um Senstar-**Kameras** geht (z. B. TC200 thermisch+HD): Senstar ist
ONVIF-first (Symphony spricht Profil S/T). Solche Kameras deckt das **vorhandene
generische ONVIF-Plugin** bereits ab — Discovery (WS-Discovery), Info, IP, ONVIF-Benutzer,
Werksreset. Ein eigenes Senstar-Plugin lohnt nur, wenn eine konkrete Kamera eine
**proprietäre** Funktion über ONVIF hinaus bietet (Firmware-Upload, herstellerspezifische
Konfig). Das ist modellabhängig und müsste pro Modell geprüft werden; viele Senstar-Geräte
sind ONVIF-/OEM-basiert und brauchen daher kein eigenes Plugin (analog zu ABUS/Honeywell,
die über Hikvision/Dahua/ONVIF laufen).

---

## 6. Aufwand & Empfehlung

**Technischer Aufwand (falls gewünscht):** gering–mittel. Ein Paket
`kkm/plugins/senstar/` mit
- kleinem REST/Token-Client (`session.py`, stdlib `urllib`),
- `plugin.py` (Mapping auf `SET_IP`, `FIRMWARE`, `FIRMWARE_CHECK`, `CONFIG`-Backup,
  `factory_reset`, `device_info`),
- `discover()` per Subnetz-Scan.

Die REST-API ist angenehmer als die CGI-Vendoren; die eigentliche Arbeit steckt in
**Discovery** und der **Verifikation an echter Hardware**.

**Empfehlung:**
- **Geht es um den AIM-A10D als Gerät:** machbar, aber es ist ein **Decoder, kein Kamera**
  — erst die Scope-Frage klären. Wenn ja: als `experimental`-Plugin mit
  SET_IP/Firmware/Firmware-Check/Reset/Info; USERS/ONVIF_USERS weglassen; CONFIG nur als
  opakes Settings-Backup. Discovery per Subnetz-Scan, an Hardware verifizieren.
- **Geht es um Senstar-Kameras:** zuerst das **ONVIF-Plugin aktivieren** (deckt ONVIF
  Profil S/T ab) — vermutlich kein neues Plugin nötig.
- **Voraussetzung für eine Umsetzung:** vollständige Thin-Client-API-Referenz (v2.2.1) +
  ein Testgerät (Werkslogin, Settings-Schema, Upload-Format, tatsächlicher
  Discovery-/Broadcast-Mechanismus des Enterprise Managers).

---

## Quellen

- Senstar Thin Client (Produkt/Datenblatt/Guide):
  <https://senstar.com/products/video-management/thin-client/>,
  <https://senstar.com/wp-content/uploads/Thin_Client_Datasheet_EN.pdf>,
  <https://senstar.com/wp-content/uploads/Thin_Client_Product_Guide_EN.pdf>
- **Aimetis Thin Client API Reference v2.2.1** (Endpunkte /Session, /Settings, /System):
  <https://xnet.senstar.com/webhelp/ThinClient/api/2.2.1/en/docs.html>
- A10D Firmware-Upgrade (KB): <https://xnet.senstar.com/Support/kbarticle.aspx?ID=10347>
- Produkt/Händler AIM-A10D: <https://www.anixter.com/en_us/products/AIM-A10D/SENSTAR-CORP/Video-Transmission/p/598655>
- Senstar/ONVIF (Profil S/T, Symphony): <https://senstar.com/product-resources/symphony-supported-devices/>
