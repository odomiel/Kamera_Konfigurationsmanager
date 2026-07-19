# Recherche: ACTi-Plugin

*Stand: 2026-07-19. Machbarkeits- und Aufwandsanalyse, noch keine Umsetzung.*

Ziel: Ein Hersteller-Plugin für **ACTi**-Kameras (taiwanischer Hersteller
professioneller IP-Kameras), das wie das Axis- und das (experimentelle)
Hikvision-Plugin die Kern-Funktionen anbietet. Dieses Dokument hält fest, **was der
Code verlangt**, **was ACTi technisch liefert** und **wo die Haken liegen.**

> Kurzfazit vorweg: ACTi liegt **zwischen Hikvision und Hanwha**. Die API ist
> CGI-/URL-basiert und damit `vapix.py` sehr ähnlich (vertrautes Muster, halb-
> öffentlich dokumentiert), **aber**: das Authentifizierungsmodell ist schwächer
> (Zugangsdaten teils als Klartext-Query-Parameter, HTTP-Basic, Digest unsicher/
> firmwareabhängig), es gibt **kein ACTi-eigenes Discovery-Protokoll** wie
> Hikvisions SADP (man muss auf ONVIF-WS-Discovery aufsetzen) und wie bei den
> anderen fehlen ein offenes Firmware-Repo und eine Fleet-Konfigurationsvorlage.

---

## 1. Was das Programm von einem Plugin verlangt

(wie in der Hanwha-/Hikvision-Notiz — hier nur kurz)

Ein neues Plugin = **ein neues Paket `kkm/plugins/acti/`** mit einer
`VendorPlugin`-Unterklasse, registriert in `build_registry()`
(`kkm/plugins/__init__.py`). **Nichts in `core` oder `gui` ändert sich.**

Pflicht: `discover(timeout)`, `check_online(camera, creds)`.
Optional je `Capability.*`: `device_info`, `set_static_ip`/`set_dhcp`,
`add_user`/`set_user_password`, `add_onvif_user`/…, `upgrade_firmware`,
`firmware_updates`/…, `parse_config_file`/`import_config`/…, `factory_reset`.
Klassen-Attribute `USER_ROLES` / `ONVIF_LEVELS` für die Dialoge, `experimental =
True` bis zur Verifikation an echter Hardware (Plugin-Manager kennzeichnet es dann,
ab Werk aus — genau wie beim Hikvision-Plugin).

Vorlagen im Baum: **Axis-Plugin** (Wrapper um `vapix.py`, CGI/URL wie ACTi),
**Hikvision-Plugin** (`isapi.py` + eigene Discovery, Digest-Client, experimentell)
und **ONVIF-Plugin** (`onvif/discovery.py` + `onvif/soap.py` — für ACTi sowohl als
Discovery- als auch als ONVIF-Benutzer-Weg wiederverwendbar).

---

## 2. Was ACTi technisch anbietet — CGI-/URL-Kommandos

ACTi-Geräte werden über **URL-Kommandos** unter `/cgi-bin/` gesteuert — sehr nah an
Axis VAPIX.

| Aspekt | ACTi CGI-API |
|---|---|
| Transport | HTTP(S), URL-Kommandos (`?PARAM=WERT` setzt, `?PARAM` liest) |
| Basis-Pfad | `/cgi-bin/<cgi>` (**Typ 1**) bzw. `/cgi-bin/cmd/<cgi>` (**Typ 2**, „sicherer") |
| Datenformat | `KEY=VALUE`-Zeilen (Klartext, wie Axis `param.cgi`) |
| Auth | **HTTP Basic** *oder* Zugangsdaten als Query-Parameter `USER=…&PWD=…` (Typ 1) — **Klartext**; Digest firmwareabhängig/unsicher |
| Ports | 80 (Default; RTSP oft 7070), konfigurierbar |
| Discovery | **kein offenes ACTi-Protokoll** — Standard-**ONVIF-WS-Discovery** (UDP 3702); ACTi-Geräte sind ONVIF-konform |
| Default-Login | `192.168.0.100`, `admin`/`123456` (bzw. `Admin`/`123456`) |

CGI-Programme (Auswahl): **`system`** (Geräte-/Netzwerk-/System-Einstellungen),
`encoder`/`mpeg4` (Videoeinstellungen), **`update`** (Firmware). Aktions-Kommandos:
**`SAVE`**, **`REBOOT`**, **`FACTORY_DEFAULT`**.

Belegte/plausible Aufrufe (Feinnamen aus dem PDF zu bestätigen, siehe Haken):
- Geräteinfo: `GET /cgi-bin/system?SYSTEM_INFO` → `KEY=VALUE`-Dump (Modell,
  Firmware, MAC). `SYSTEM_INFO` listet zugleich die verfügbaren Parameter auf.
- Netzwerk/IP: `system`-Parameter für IP-Adresse, Subnetzmaske, Gateway,
  DHCP-Schalter, gefolgt von `SAVE` (+ ggf. `REBOOT`).
- Benutzer: `account`/`system`-Parameter für Konto anlegen/Passwort setzen.
- Firmware: `update`-CGI (Datei-Upload).
- Werksreset: `system?FACTORY_DEFAULT` (+ `REBOOT`).

Die Spezifikation **„ACTi Camera API and URL Commands"** (Ausgaben 2012–2025)
kursiert halb-öffentlich (Scribd/Studocu) sowie in ACTis „Firmware User's Manual" —
der Endpunktsatz ist also praktisch einsehbar, aber die **modernen Parameternamen
für Netzwerk und Konten** müssen aus dem aktuellen PDF gezogen und an Hardware
gegengeprüft werden.

---

## 3. Capability-Mapping — was realistisch geht

| Capability | Weg | Machbarkeit |
|---|---|---|
| `DISCOVER` | **ONVIF-WS-Discovery** (`onvif/discovery.py` wiederverwenden), Treffer auf ACTi filtern (ONVIF-Scope `manufacturer`/`hardware` oder Nachprobe `/cgi-bin/system`) | ✅ machbar, aber kein MAC aus der Discovery (ONVIF-UUID) → MAC nachträglich aus `SYSTEM_INFO` lesen und umschlüsseln |
| `ONLINE_CHECK` | HTTP-Probe auf `/cgi-bin/system` (401/Antwort = online) oder ONVIF `GetSystemDateAndTime` | ✅ leicht |
| `DEVICE_INFO` | `GET /cgi-bin/system?SYSTEM_INFO`, `KEY=VALUE` parsen | ✅ belegt |
| `SET_IP` | `system`-Netzwerkparameter + `SAVE`/`REBOOT` | ⚠ machbar, exakte Parameternamen aus PDF/Hardware |
| `USERS` | `account`/`system`-Kontoparameter | ⚠ Parameternamen unsicher |
| `ONVIF_USERS` | ONVIF-SOAP (`onvif/soap.py` wiederverwenden) | ✅ |
| `FACTORY_RESET` | `system?FACTORY_DEFAULT` (+ `REBOOT`) | ✅ belegt |
| `FIRMWARE` (Upload) | `update`-CGI | ⚠ Upload-Mechanismus (Multipart?) unbestätigt → 2. Phase |
| `FIRMWARE_CHECK` | — | ❌ kein offenes Repo; Firmware hinter dem ACTi-Downloadportal, modellspezifisch |
| `CONFIG` (Vorlage) | — | ❌ `SYSTEM_INFO` liefert zwar `KEY=VALUE` wie `param.cgi`, aber es gibt kein Fleet-Vorlagenformat (wie Axis-ADM `.cfg`); Parametersatz modellspezifisch |

**Empfohlener Zuschnitt** (1. Phase, wie Hikvision experimentell):
`DISCOVER, ONLINE_CHECK, DEVICE_INFO, SET_IP, USERS, ONVIF_USERS, FACTORY_RESET`.
`FIRMWARE` erst nach Bestätigung des Upload-Wegs; kein `FIRMWARE_CHECK`, kein
`CONFIG`.

---

## 4. Die Haken

1. **Schwache Authentifizierung.** Typ-1-URLs übergeben `USER=/PWD=` als
   **Query-Parameter im Klartext** (landen in Proxy-/Server-Logs); HTTP-Basic ist
   ohne HTTPS ebenfalls Klartext, Digest ist firmwareabhängig und bei ACTi
   historisch schwach/uneinheitlich. Der Typ-2-Weg (`/cgi-bin/cmd/…`) nutzt eine
   proprietäre, undokumentierte Verschlüsselung. → Das Plugin sollte **HTTPS + Basic**
   bevorzugen und Zugangsdaten **nie in der URL** senden (Basic-Header statt
   `USER=/PWD=`), soweit die Firmware das mitmacht.
2. **Kein herstellereigenes Discovery-Protokoll.** Anders als Hikvision (SADP) gibt
   es kein offen dokumentiertes ACTi-UDP-Discovery. Man setzt auf **ONVIF-WS-
   Discovery** auf und muss die Treffer **auf ACTi filtern** (ONVIF-Scope oder
   `/cgi-bin/system`-Nachprobe) — sonst fände das ACTi-Plugin dieselben Geräte wie
   das generische ONVIF-Plugin. Zudem fehlt die MAC in der Discovery (ONVIF liefert
   nur die UUID); für eine stabile Identität (`camera_key`) muss die MAC nachträglich
   aus `SYSTEM_INFO` gelesen und die Kamera umgeschlüsselt werden
   (`GroupStore.rekey_camera`).
3. **Firmware-Zersplitterung.** ACTi hat mehrere Firmware-Generationen/Plattformen
   (z. B. die „A1D-500"-Reihe) mit teils abweichenden CGI-Sätzen (älter vs. neuer,
   `encoder` vs. `mpeg4` vs. `system`). Ein Plugin muss defensiv parsen und darf sich
   nicht auf einen einzigen Parametersatz verlassen.
4. **Kein offenes Firmware-Verzeichnis.** Firmware liegt hinter ACTis Downloadportal,
   modellspezifisch — der *Upload* einer lokalen Datei ist machbar, die automatische
   *Update-Suche* nicht. → `FIRMWARE` (später), kein `FIRMWARE_CHECK`.
5. **Keine Konfigurations-Vorlage.** `SYSTEM_INFO` ist ein Modell-spezifischer
   Parameter-Dump ohne standardisiertes Austauschformat → kein `CONFIG` (gleiche
   Begründung wie bei ONVIF/Hikvision).
6. **Testhardware nötig.** Wie bei ONVIF/Hanwha/Hikvision müssen die genauen
   Parameternamen (v. a. `SET_IP`, `USERS`), der Firmware-Upload und das
   Reset-Verhalten an einer echten ACTi-Kamera verifiziert werden, bevor man das
   `experimental`-Flag entfernt.

**Wege an die genauen Aufrufe:** aktuelles „ACTi Camera API and URL Commands"-PDF
(halb-öffentlich) + Gegencheck an echter Kamera (Web-UI im Browser-DevTools
mitschneiden, wie seinerzeit bei `vapix.py`); `system?SYSTEM_INFO` listet die
verfügbaren Parameter des jeweiligen Modells selbst auf.

---

## 5. Fazit

ACTi ist ein **realistischer, aber nachrangiger** Kandidat: Das CGI-/URL-Muster
gleicht VAPIX, die Doku ist halb-öffentlich und der Code-Aufwand ist gering (ein
Paket wie `axis/`/`hikvision/` im Kleinen, ~400–600 Zeilen, kein Eingriff in
`core`/`gui`; ONVIF-Discovery und ONVIF-Benutzer sind wiederverwendbar). Gegenüber
Hikvision ist ACTi aber **weniger attraktiv**, weil (a) das Authentifizierungsmodell
schwächer und heikler ist, (b) es kein eigenes Discovery-Protokoll gibt (ONVIF-
Aufsatz + Filter + MAC-Nachlesen) und (c) Firmware/Config genauso zu bzw. weg fallen.
Der Aufwand steckt im **Feinschliff der Parameternamen**, in der **sauberen
Auth-/Discovery-Behandlung** und im **Testen an echter Hardware** — nicht in der
Architektur.

Nächste Schritte, sobald gewünscht:
- **A** — CGI-Grundgerüst bauen (`acti/` mit Basic-Client über HTTPS,
  ONVIF-Discovery-Wiederverwendung + ACTi-Filter, `SYSTEM_INFO`-Parser für
  `device_info` + `check_online` als belegter Erstaufruf, MAC-Umschlüsselung),
  Schreib-Aktionen als TODO bis Hardware vorliegt — analog zum Hikvision-Start.
  Plugin `experimental = True`, ab Werk aus.
- **B** — Warten auf ACTi-Kamera, dann `SET_IP`/`USERS`/`FACTORY_RESET` (und ggf.
  `FIRMWARE`) verifiziert ergänzen, Flag entfernen.

---

## Quellen

- ACTi Camera API and URL Commands (halb-öffentliche Spiegel, Ausgaben 2012–2025):
  https://www.scribd.com/document/618101800/ACTi-Camera-API-and-URL-Commands-20220803
- ACTi Camera URL Commands (offizielles ACTi-PDF, 2012):
  https://www2.acti.com/getfile/KnowledgeBase_UploadFile/ACTi_Camera_URL_Commands_20120327_002.pdf
- ACTi URL-Commands-Notizen (CGI-Typen, `SYSTEM_INFO`, `SAVE`/`REBOOT`/`FACTORY_DEFAULT`):
  https://cubevic.github.io/My_notes/CCTV/ACTi/ACTi_URL_Commands.html
- ACTi Firmware User's Manual (A1D-500-Reihe, CGI/Parameter):
  https://download.acti.com/?id=16579
- ACTi Default-IP/-Login/-Port:
  https://www.videoexpertsgroup.com/glossary/acti-default-ip-username-password-port
- ACTi über ONVIF (WS-Discovery, RTSP/HTTP, Port 7070):
  https://www.ispyconnect.com/camera/acti
