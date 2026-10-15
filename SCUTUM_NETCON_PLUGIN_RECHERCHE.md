# Recherche: Scutum/Inform Netcon-Plugin (Schwerpunkt Netcon 3)

**Kurzfassung.** Die **Netcon 3** (Scutum/Inform) ist ein **I/O-Modul** mit zusätzlich
**8 seriellen Schnittstellen** — **keine Kamera, keine Weboberfläche**. Umgesetzt als
eigenes, experimentelles Plugin `kkm/plugins/scutum/` — vorerst **nur Anzeige** (Stufe 1):
das Gerät taucht in der Liste auf, eine Konfiguration ist über die öffentlich
zugänglichen Schnittstellen nicht möglich. Der **Nachfolger Netcon 4** (Raspberry-Pi-Basis)
wird vom selben Plugin **ohne Änderung** abgedeckt (siehe Abschnitt 0).

---

## 0. Befunde am echten Gerät (2026-10-15)

Ein Netcon 3 lag auf **192.168.0.236** vor und wurde **read-only** sondiert (keine
Login-Versuche — keine Passwörter raten, Sperrgefahr).

**Offene Ports (TCP, 1–1024 + Industrie-/Hersteller-Ports):** **nur 22 (SSH)**.
- SSH-Kennung: `SSH-2.0-OpenSSH_6.7` (Debian-8-Ära), Hostkey nur `ssh-rsa`,
  Standard-OpenSSH-6.7-Algorithmen (nichts Herstellerspezifisches).
- **Kein** HTTP/HTTPS (80/443 zu) → **keine Weboberfläche** (vom Nutzer bestätigt).
- **Kein** SNMP (161/UDP, Community `public` ohne Antwort).
- **Kein** mDNS/Zeroconf, **kein** WS-Discovery → das ONVIF-Plugin sieht es nicht.
- **Keine** Industrie-/Gebäudeprotokolle auf den geprüften Ports (Modbus/BACnet/…).
  Die 8 seriellen Schnittstellen des Geräts werden über das Netz nicht als offener
  TCP-Dienst (Terminal-/Seriell-über-IP) sichtbar — zumindest nicht auf Standardports.

**Einziger herstellerspezifischer Marker ohne Login:** der **DHCP-/Reverse-DNS-Hostname**
`netcon3-<id>` — hier `netcon3-1436520562`. Das Gerät sendet diesen Default-Hostnamen im
DHCP-Request (Option 12); wo das Netz den Client-Namen im DNS registriert, ist er per
Reverse-DNS (PTR) lesbar. `<id>` (hier `1436520562`) ist geräteindividuell und dient als
**stabile Identität** (Seriennummer) über IP-Wechsel hinweg.

**Konsequenz:** Aus reiner Netzsicht ist das Gerät sonst „nur ein Linux mit SSH". Es gibt
**keinen** weiteren unauthentifizierten Fingerprint (keine Seite, kein SNMP-sysDescr).
Eine Konfiguration würde die **SSH-Zugangsdaten des Errichters** und
**Hersteller-Dokumentation** erfordern — beides ist nicht öffentlich verfügbar. Daher:
**nur Anzeige**.

### Netcon 4 (Nachfolger, 2026-10-15 am echten Gerät verifiziert)

Ein **Netcon 4** lag auf **192.168.0.164** vor und wird vom bestehenden Plugin **ohne
Änderung** erkannt und angezeigt (`discover`/`check_online`/`device_info` → „Netcon 4").
Gleiches Bild wie die Netcon 3: im Netz **nur SSH (Port 22)**, kein Web/SNMP/mDNS. Zwei
Unterschiede:
- Software-Basis ist **Raspberry Pi OS** (`SSH-2.0-OpenSSH_7.9p1 Raspbian-10+deb10u2+rpt1`,
  Debian Buster) statt der Netcon-3-Basis (OpenSSH 6.7, Debian 8) — die Netcon 4 läuft
  auf einem Raspberry Pi.
- Der Reverse-DNS-Hostname ist **`netcon4` ohne ID-Suffix** (die Netcon 3 hatte
  `netcon3-<id>`). Dadurch keine Seriennummer → Identität = Name+IP. Das
  Hostname-Muster (`netcon` + optionale Nummer + optionale ID) erkennt beide Modelle
  generisch; ein eigenes Modell-/Plugin-Handling ist nicht nötig.

---

## 1. Erkennung (wie das Plugin das Gerät findet)

Der einzige unauth-Marker ist der Hostname, also:

- **`discover()`** (`scutum/discovery.py`): Subnetz-Scan der lokalen `/24`(s) — schneller
  **TCP-Vortest auf Port 22**, dann **Reverse-DNS** (`session.kennung`) nur auf offenen
  Hosts. Gelistet wird nur, wessen PTR-Name den **`netcon`-Marker** trägt (konservativ,
  keine Fehltreffer auf beliebige SSH-Hosts). **Keine Loginversuche.**
- **Grenze:** Das greift nur in Netzen, die den DHCP-Client-Namen im DNS registrieren
  (beim Testaufbau der Fall). Anderswo findet der Scan das Gerät **nicht**.
- **Fallback (immer):** **manuelles Hinzufügen** über den Pfeil am *Suchen*-Button
  (IP + Hersteller „Scutum/Inform Netcon"); `check_online` prüft dann Port 22, der
  Reverse-DNS-Name liefert ggf. Modell/Seriennummer nach.

## 2. Plugin-Umfang (Capabilities)

| Capability      | Umsetzung                                                            |
|-----------------|---------------------------------------------------------------------|
| `DISCOVER`      | Subnetz-Scan Port 22 + Reverse-DNS-Marker `netcon…`                  |
| `ONLINE_CHECK`  | TCP-Connect auf Port 22 (Lebenszeichen, kein Login)                 |
| `DEVICE_INFO`   | Modell (`Netcon 3`) + Seriennummer (`<id>`) aus dem Hostnamen        |

**Nicht möglich** (ohne Errichter-SSH-Zugang + Hersteller-Doku): `SET_IP`, `USERS`,
`FIRMWARE`, `FACTORY_RESET`, `CONFIG` — es gibt keine offene Konfigurationsschnittstelle.
Eine Firmware-/Softwarefassung ist nicht unauth ermittelbar (die SSH-Version ist **nicht**
die Gerätefirmware) und bleibt leer.

Das Plugin ist `experimental = True` und **ab Werk ausgeschaltet** (`DEFAULT_OFF`).

## 3. Identität

`discover()` setzt die Geräte-ID aus dem Hostnamen als **Seriennummer**
(`MAC-Adresse/Seriennummer`), damit `camera_key` stabil ist und einen IP-Wechsel übersteht
(sonst Name+IP). Ohne Reverse-DNS (manuell, kein DNS) bleibt es bei Name+IP.

## 4. Offene Punkte / mögliche spätere Stufen

- **Konfiguration/Status** nur mit SSH-Login des Errichters denkbar; Befehls-/Dateipfade
  des Netcon sind undokumentiert (Hersteller-/Errichterwissen). Nicht ohne Freigabe und
  reale Zugangsdaten angehen (keine Passwörter raten).
- Die **8 seriellen Schnittstellen**: ob/wie sie über das Netz adressierbar sind
  (Seriell-über-IP/Terminalserver), war auf den geprüften Standardports nicht sichtbar.
  Falls ein herstellereigenes Tool oder eine Portliste bekannt wird, ließe sich das
  nachziehen (z. B. Status/Belegung anzeigen).
