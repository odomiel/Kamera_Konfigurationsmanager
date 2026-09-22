# Änderungsverlauf

Versionsschema: `JJ.MM.TT[bN]` (zweistelliges Jahr; mehrere Releases am selben Tag
erhalten ein hochzählendes `bN`-Suffix). Die aktuelle Version steht in
`kkm/version.py`.

## 26.09.22b3 — 2026-09-22

- **Eigener Einstellungs-Reiter „Verbindungssicherheit".** Zertifikatsprüfung
  (Trust-on-First-Use, inkl. Zähler und „Alle vergessen") und der Schalter für
  Basic-Anmeldung über HTTP stehen jetzt gebündelt in einem eigenen Reiter direkt hinter
  „Plugins", statt unten im Plugins-Reiter. Die Hinweismeldung bei abgelehnter
  Basic-Anmeldung verweist entsprechend auf *Einstellungen → Verbindungssicherheit*.

## 26.09.22b2 — 2026-09-22

- **Kamera-Zertifikate werden gemerkt (Trust-on-First-Use).** Da Kameras selbstsignierte
  Zertifikate nutzen, war HTTPS bisher ungeprüft und damit für einen Mithörer im Netz
  abfangbar. Jetzt speichert das Programm beim ersten HTTPS-Kontakt den SHA-256-
  Fingerabdruck des Zertifikats **pro Kamera** (MAC/Seriennummer, nicht IP) in
  `known_certs.json` (`0600`, Teil der `.kkmbackup`-Sicherung). Weicht er später ab, wird
  die Verbindung direkt nach dem TLS-Handshake verworfen — **bevor** eine Anfrage und damit
  Zugangsdaten gesendet werden. Der Aktionsdialog zeigt dann alten und neuen Fingerabdruck
  und bietet **„Neuem Zertifikat vertrauen und wiederholen"** an. Ist ein Zertifikat
  bekannt, fällt *auto* bei unerreichbarem HTTPS nicht mehr auf HTTP zurück
  (Downgrade-Schutz; explizit gewähltes *http* bleibt möglich).
- Nach **Werksreset** und **Firmware-Update** über das Programm wird das neue Zertifikat
  automatisch übernommen (auch während des Wartens auf den Neustart). Rechtsklick →
  **„Zertifikat vergessen"** für bewusste Zertifikatswechsel außerhalb des Programms;
  beim vollständigen Entfernen einer Kamera wird ihr Zertifikat mit gelöscht, bei
  IP-Wechsel MAC-loser Kameras mit umgeschlüsselt.
- Abschaltbar unter *Einstellungen → Plugins → „Kamera-Zertifikate beim ersten Kontakt
  merken und bei Änderung nachfragen"* (ab Werk an), dort auch **„Alle vergessen"**. Eine
  eingespielte Sicherung übernimmt beide Sicherheitsschalter sofort.
- Hintergrund-Lesezugriffe (Firmware/Modell nachladen, Zugangsdaten-Prüfung) prüfen
  ebenfalls; ein geändertes Zertifikat zählt dort still als Lesefehler (keine Rückfrage).

## 26.09.22b1 — 2026-09-22

- **Keine Basic-Anmeldung mehr über unverschlüsseltes HTTP.** Alle HTTP-Clients (Axis,
  Hikvision, Dahua, Hanwha, ONVIF) senden Zugangsdaten über `http://` nur noch per
  **Digest**. Bisher genügte es einem Mithörer, „Basic" zu verlangen (oder Port 443 zu
  blockieren und so den HTTP-Rückfall zu erzwingen), um das Kamera-Passwort im Klartext
  zu erhalten. Verlangt eine Kamera über HTTP nur Basic, bricht die Aktion mit klarer
  Meldung ab — ohne Passwort-Nachfrage und ohne Fehl-Erfolg bei Firmware-Uploads. Über
  HTTPS bleibt Basic erlaubt. Für Altgeräte **abschaltbar** unter *Einstellungen →
  Plugins → Verbindungssicherheit* (ab Werk aus). Ausnahme: die Werkszustands-Prüfung
  mit dem öffentlich bekannten `root/pass` bleibt unverändert.

## 26.09.22 — 2026-09-22

- **Dateirechte abgesichert (Linux).** Das Konfigurationsverzeichnis wird jetzt mit
  `0700` angelegt, alle darin geschriebenen Dateien (`groups.json`, `settings.json`,
  `vault.enc`, `vault.auto`) mit `0600`; ebenso exportierte `.kkmbackup`-Dateien und
  wiederhergestellte Dateien. Bisher entstanden sie gemäß `umask` meist mit `0664` —
  für andere lokale Benutzer lesbar. Besonders kritisch war das beim
  **Auto-Entsperr-Token**: dessen Schlüssel stammt aus öffentlich bekannten Merkmalen
  (Rechner-/Benutzername), ein lesbares Token gab damit das Master-Passwort preis.
  Bestehende Installationen werden beim Programmstart einmalig nachgerüstet.
- **Tresor beachtet die gespeicherte Iterationszahl.** `vault.enc` wird mit der
  PBKDF2-Iterationszahl aus der Datei geöffnet statt mit der Programmkonstante — alte
  Tresore bleiben so auch nach einer künftigen Erhöhung lesbar und werden beim
  Entsperren automatisch auf den aktuellen Wert angehoben. Unbekannte Verfahren
  (`kdf`) werden klar abgewiesen; das Auto-Entsperr-Token speichert seine
  Iterationszahl nun ebenfalls (ältere Token ohne Feld funktionieren weiter).
- **Iterationszahl aus Dateien wird begrenzt (100.000–10.000.000).** Tresor,
  Auto-Entsperr-Token und `.kkmbackup` prüfen den Wert vor der Schlüsselableitung. Eine
  präparierte Sicherung mit ~4 Mrd. Iterationen konnte die Oberfläche bisher faktisch
  einfrieren; sie wird jetzt sofort als ungültig abgelehnt.

## 26.09.20 — 2026-09-20

- **Verschlüsselte Benutzerlisten (Stapel-Import).** Der Benutzer- und der
  ONVIF-Benutzer-Dialog akzeptieren als Import-Quelle jetzt neben einer Klartext-`.txt`/
  `.csv` auch ein **passwortgeschütztes ZIP-Archiv** (WinZip-AES-256, z. B. mit
  7-Zip/WinZip erstellt) — so liegen die Klartext-Passwörter nicht ungeschützt auf der
  Platte. Wird eine ZIP-Datei gewählt (an der Signatur erkannt), fragt das Programm das
  Archiv-Passwort maskiert ab und liest die enthaltene Text-/CSV-Datei entschlüsselt ein.
  Übernommen aus dem Axis-Discovery-Tool (via `pyzipper` + `pycryptodomex`, beide im
  AppImage/`.exe` gebündelt). Format und Vorab-Validierung bleiben unverändert.

## 26.09.17 — 2026-09-17

- **Lizenzdokumentation vervollständigt.** `THIRD_PARTY_LICENSES.md` bettet jetzt die
  vollständigen Lizenztexte von **PSF** (CPython), **Apache-2.0** (OpenSSL, cryptography)
  und **LGPL-2.1** (zeroconf) als Anhang ein — damit liegen alle geforderten Lizenztexte
  jeder Distribution bei (wichtig für den Windows-Build, der die LGPL-Textdatei bisher
  nicht mitbrachte). Korrigiert: libffi **3.6.0 → 3.8.0**, cffi als **MIT-0**; ergänzt:
  Hinweis auf CPython-interne Fremdteile (libmpdec/HACL*/BLAKE2). Der Windows-Spec
  bündelt über `copy_metadata` zusätzlich die Original-Lizenzdateien der Wheels. Ein
  vollständiges Lizenz-Audit bestätigte die durchgehende GPL-3.0-Kompatibilität aller
  gebündelten Komponenten (OpenSSL 3.x = Apache-2.0, daher keine OpenSSL-Ausnahme nötig).

## 26.09.11 — 2026-09-11

- **Projektseite + Update-Prüfung.** Der Reiter *Einstellungen → Über* zeigt jetzt die
  **GitHub-Projektseite** als anklickbaren Link. Neu darunter eine **Update-Prüfung**,
  die die öffentlichen GitHub-Releases als Quelle nutzt: „Jetzt nach Updates suchen"
  meldet, ob eine neuere Version vorliegt (mit Download-Link), und die Option **„Beim
  Programmstart nach Updates suchen"** (standardmäßig an, jederzeit **abschaltbar**)
  prüft beim Start im Hintergrund und weist nur bei einer tatsächlich neueren Version
  dezent darauf hin. Offline/ohne Verbindung passiert nichts (kein Fehler). Die Abfrage
  wertet nur **stabile** Releases (keine `bN`-Vorabversionen).

## 26.08.29 — 2026-08-29

- **Kamera manuell hinzufügen.** „Suchen/aktualisieren" ist jetzt ein Split-Button:
  der anliegende Pfeil öffnet den Unterpunkt **„Kamera manuell hinzufügen…"**. Der
  Dialog nimmt Name, IP-Adresse, Port, Hostname und — anders als beim reinen
  Discovery-Tool — den **Hersteller** (bestimmt, welches Plugin die Aktionen
  ausführt). So lassen sich Kameras erfassen, die die Suche (mDNS/WS-Discovery) nicht
  findet, z. B. in einem anderen Subnetz. Die IP wird per `ipaddress` validiert,
  Duplikate (gleiche IP) werden abgefangen. Direkt nach dem Hinzufügen wird die IP
  **sofort angesprochen (Erkennung)**: erst die Erreichbarkeit, und ist die Kamera
  online, läuft dieselbe Auswertung wie nach einer Suche — Firmware/Modell auslesen
  bzw. Werkszustand erkennen und bei Bedarf nach Zugangsdaten fragen. Ist die IP
  nicht erreichbar, bleibt der Eintrag als Offline-Zeile stehen (keine
  Passwortabfrage für eine tote IP). Der Eintrag landet im Roster (überlebt
  Neustarts) und wird durch einen späteren Suchtreffer derselben IP automatisch
  ersetzt — Gruppenzugehörigkeit und gespeicherte Zugangsdaten wandern dabei mit.

## 26.08.25 — 2026-08-25

- **Abhängigkeiten geprüft; OpenSSL auf 3.5.8 angehoben** (vorher 3.5.7 — neuester Patch
  des **LTS**-Zweigs 3.5.x). Alles andere ist bereits auf dem neuesten unterstützten
  Stand: Python 3.14.7, Tcl/Tk 9.0.4 (9.1 nur Alpha), libffi 3.8.0 sowie — da
  `requirements.txt` bewusst ungepinnt ist — zeroconf, cryptography, sv-ttk in ihrer
  jeweils aktuellen Version. Wird beim nächsten AppImage-Build wirksam.

## 26.08.10b3 — 2026-08-10

- **Toolbar: Scroll-Pfeile auf Button-Höhe.** Die Pfeile (◀/▶) wurden bisher über die
  volle Höhe der Leiste gestreckt und waren dadurch höher als die übrigen Buttons. Jetzt
  behalten sie ihre natürliche Höhe (= Höhe der normalen Buttons) und sind in der Zeile
  zentriert.

## 26.08.10b2 — 2026-08-10

- **Toolbar: Scroll-Pfeile statt Bildlaufleiste.** Der mittlere Aktions-Bereich wird jetzt
  über zwei Pfeile bewegt — **◀ links von „IP-Adresse"** und **▶ rechts von „Zeitzone"** —
  statt über eine durchgehende Bildlaufleiste. Die Pfeile erscheinen nur, wenn nicht alle
  Aktions-Buttons in die Breite passen, und sind am jeweiligen Ende ausgegraut; ein Klick
  scrollt um etwa eine Button-Breite. Der Suchbereich links und die Werkzeuge rechts
  bleiben wie zuvor fix sichtbar. Verifiziert an echtem Display.

## 26.08.10b1 — 2026-08-10

- **Toolbar-Scroll verfeinert: nur die mittleren Aktions-Buttons sind scrollbar.** Die
  Bildlaufleiste gilt jetzt ausschließlich für die Buttons **IP-Adresse … Zeitzone**; die
  Werkzeuge rechts (**Exportieren / Einstellungen / Schloss / Hilfe** + Fortschritt) bleiben
  wie der Suchbereich links **immer sichtbar**. Die Bildlaufleiste liegt in einer eigenen
  Zeile direkt unter der Toolbar, damit sie auch bei sehr schmalem Mittelteil zuverlässig
  erscheint. Verifiziert an echtem Display (800/1000/1600 px): Ränder stets sichtbar, Mitte
  ab ~800 px scrollbar.

## 26.08.10 — 2026-08-10

- **Hauptfenster-Toolbar bei kleinem/nicht maximiertem Fenster scrollbar.** Passten die
  vielen Buttons nicht in die Fensterbreite (gerade mit der neuen Aktion „Zeitzone"),
  wurden sie rechts abgeschnitten. Jetzt bleibt der **Suchbereich** („Suchen/aktualisieren"
  + „Online prüfen") **fix links immer sichtbar**, und die übrigen Aktions-/Werkzeug-Buttons
  liegen in einem **horizontal scrollbaren Bereich**: passt nicht alles, erscheint eine
  Bildlaufleiste, statt Buttons zu verstecken. Bei ausreichend breitem Fenster verhält
  sich die Leiste wie zuvor (rechte Buttons rechts angedockt, keine Bildlaufleiste).

## 26.08.09b6 — 2026-08-09

- **Neue Aktion „Zeitzone" (Axis) über die Time API.** Setzt die Zeitzone einer oder
  mehrerer Kameras per **IANA-Name** (z. B. `Europe/Berlin`) über die Axis **Time API**
  (`POST /axis-cgi/time.cgi`, `setTimeZone`; ab **AXIS OS 9.30**); die Sommerzeit wird
  automatisch abgeleitet. Damit ersetzt das Programm den Parameter `Time.POSIXTimeZone`,
  der in **AXIS OS 13** aus `param.cgi` entfernt wurde. Der neue Dialog bietet eine
  durchsuchbare IANA-Liste (aus `zoneinfo`, mit kleinem eingebautem Rückfall) mit freier
  Eingabe und einen Knopf **„Von erster Kamera laden"**, der die aktuell gesetzte Zone und
  die vom Gerät unterstützten Zonen holt. Neue Capability `Capability.TIMEZONE` (nur Axis;
  bei anderen Plugins bleibt der Button ausgegraut); Toolbar- und Rechtsklick-Eintrag,
  Doku (Hilfe + Handbuch DE/EN) ergänzt.

## 26.08.09b5 — 2026-08-09

- **Ersteinrichtung: klare Fehlermeldung bei zu schwachem Passwort (AXIS OS 13).** An
  einer AXIS-M7104-Preview mit **Firmware 13.0.33** verifiziert. AXIS OS 13 prüft das
  Passwort des Erstadmins strenger und lehnt ein zu schwaches mit „Error: invalid password"
  (HTTP 200) ab. Bisher verschleierte `add_or_set_user(factory=True)` das: Es probierte
  danach die Werks-Zugangsdaten und meldete deren 401 als „Authentifizierung
  fehlgeschlagen". Jetzt wird eine **echte Geräte-Ablehnung** (Fehlertext statt 401) beim
  unauthentifizierten Erstversuch als maßgebliche Ursache durchgereicht — der Nutzer sieht
  den wahren Grund. Der Werks-Login-Rückfall für ältere Geräte (unauth → 401) bleibt.
- **OS-13-Verifikation der bestehenden Axis-Funktionen** (Recherche/Ergebnisse in
  `Plugin_Recherchen/AXIS_OS13_VAPIX_RECHERCHE.md`): Online-Prüfung, Discovery,
  Werkszustandserkennung, Ersteinrichtung, Geräteinfo (Firmware 13.0.33), Konfig-Export
  (681 Parameter) und die **Konfig-Import-Härtung** (obsoleter Parameter übersprungen,
  gültiger angewendet) laufen. Neuer Hinweis: OS-13-Geräte sprechen **nur HTTPS** (Port 80
  abgelehnt) — durch `scheme="auto"` bereits abgedeckt.

## 26.08.09b4 — 2026-08-09

- **Axis-Konfig-Import robuster: einzelne abgelehnte Parameter überspringen statt alles
  scheitern lassen.** Bisher wurde die ADM-`.cfg` in *einem* `param.cgi`-Batch angewendet
  — lehnte die Kamera einen einzigen Parameter ab (z. B. einen in neuerer Firmware
  entfernten/obsoleten; in AXIS OS 13 fallen etliche weg), scheiterte der **ganze** Import.
  Jetzt wird bei einer Batch-Ablehnung **parameterweise** nachgefahren: die gültigen
  Parameter werden angewendet, die vom Gerät abgelehnten übersprungen und in der
  Ergebnismeldung genannt („N vom Gerät abgelehnt/übersprungen: …"). Zwei Fallstricke
  sauber behandelt: Ein `401` auf den Batch löst **nur dann** die erneute Passwortabfrage
  aus, wenn ein Lesezugriff bestätigt, dass die Zugangsdaten wirklich nicht mehr stimmen
  (sonst gilt es als Parameter-Ablehnung); und bei echtem Auth-Fehler wird **nicht**
  Parameter für Parameter neu eingeloggt (das würde die Brute-Force-Sperre der Kamera
  auslösen). Vorbereitung auf AXIS OS 13 (Recherche in
  `Plugin_Recherchen/AXIS_OS13_VAPIX_RECHERCHE.md`).

## 26.08.09b3 — 2026-08-09

- **Erneute Passwortabfrage, wenn das Tresor-Passwort nicht mehr stimmt.** Wurde das
  Passwort einer Kamera *außerhalb* des Programms geändert, schlug eine Aktion mit dem
  gespeicherten Passwort bisher nur mit „fehlgeschlagen" fehl. Jetzt erkennt der
  Aktionsdialog den Authentifizierungsfehler (HTTP 401), fragt **nach dem Durchlauf einmal
  das aktuelle Passwort ab** und **wiederholt die Aktion** für die betroffenen Kamera(s).
  Optional (Häkchen, standardmäßig an, wenn der Tresor entsperrt ist) wird das neue,
  funktionierende Passwort direkt **im Tresor aktualisiert**, sodass die Abfrage nicht
  erneut kommt. Ein 401 tritt vor jeder Wirkung auf — die Aktion wurde also nicht
  ausgeführt, der erneute Versuch ist unbedenklich. Umsetzung: Die stdlib-Clients
  (Axis/Hikvision/Dahua/Hanwha/ONVIF) markieren 401-Fehler i18n-sicher mit einem
  Attribut, das der Dialog über `VendorPlugin.is_auth_error()` auswertet; die erneut
  eingegebenen Zugangsdaten überschreiben pro Kamera für den Wiederholungslauf.

## 26.08.09b2 — 2026-08-09

- **Suche: „[WinError 10065] Der Host war bei einem Socketvorgang nicht erreichbar"
  (Hanwha/ONVIF) behoben.** Beim Suchen/Aktualisieren erschien unter Windows manchmal die
  Meldung „Suche teilweise fehlgeschlagen: Hanwha (Wisenet): [WinError 10065]…". Ursache:
  Der WS-Discovery-Probe (ONVIF, von Hanwha mitbenutzt) wurde per Multicast über *ein* vom
  Betriebssystem gewähltes Interface gesendet; hatte dieses keine Route zur Discovery-Gruppe
  (mehrere NICs, VPN-/Virtual-Adapter, getrenntes WLAN), warf `sendto` unter Windows
  `WSAEHOSTUNREACH` — und die Exception brach die Suche mit Fehlermeldung ab. Der Probe wird
  jetzt (wie schon bei der Hikvision-SADP-Suche) über **jedes lokale Interface** gesendet;
  einzelne nicht erreichbare Interfaces werden übersprungen statt gemeldet. Nebeneffekt: In
  Multi-NIC-Umgebungen werden mehr ONVIF-/Hanwha-Geräte gefunden.

## 26.08.09b1 — 2026-08-09

- **Firmware-Dialog: Dateifilter je Hersteller statt nur `*.bin`.** Beim „Firmware-Datei
  für Modell wählen…" zeigte der Filter „Firmware" nur `*.bin` an — Hikvision-`.dav`-,
  Hanwha-`.img`- und andere Firmwaredateien waren nur über „Alle Dateien" sichtbar. Der
  Filter kommt jetzt vom Plugin des jeweiligen Modells (`firmware_extensions`): Axis/Dahua
  `.bin`, **Hikvision `.dav`**, **Hanwha/Wisenet `.img`**. „Alle Dateien" bleibt als
  Rückfall.

## 26.08.09 — 2026-08-09

- **Axis-Geräte-Sicherung im Menüpunkt „Konfig-Backup".** Bisher konnte man dort nur
  Hikvision-, Dahua- und Hanwha-Backups ein-/herunterspielen; Axis fehlte. Jetzt sichert
  und spielt das Axis-Plugin die **vollständige Gerätekonfiguration** über die
  Device-Configuration-API (`GET /config/rest/$export` bzw. `PATCH /config/rest/$import`,
  AXIS OS 11.8+) — ein gerätespezifisches Komplett-Abbild (IP, Name, Ereignisregeln,
  Zeit, Benutzer …), Gegenstück zu den `.bin`-Backups der anderen Hersteller. Anders als
  jene ist die Axis-Sicherung eine **`.json`-Ressourcen-Map** (genau das Format, das die
  Weboberfläche herunterlädt; Passwörter sind nicht enthalten). Der Backup-Dialog liest
  Dateiendung, „Netz behalten"-Option und Einspiel-Varianten jetzt vom Plugin: für Axis
  bietet er die Varianten **„Zusammenführen"** (nur gesicherte Werte überschreiben) und
  **„Ersetzen"** (betroffene Bereiche erst auf Standard) an. Die Logik ist verbatim aus
  dem Axis_Kamera_Discovery-Tool übernommen. Das **Einspielen** ist noch **nicht an
  echter Hardware verifiziert** — der Dialog zeigt dafür den bekannten Warnhinweis; das
  Herunterladen entspricht dem bewährten Discovery-Export.
- **Build: libffi auf 3.8.0 aktualisiert** (täglicher Abhängigkeits-Check; Python 3.14.7,
  OpenSSL 3.5.7 LTS und Tcl/Tk 9.0.4 waren bereits aktuell).

## 26.08.08b2 — 2026-08-08

- **Hikvision-Firmwareupdate: „passiert nichts / Endlos-Warten" behoben.** Ältere
  STD-CGI-Geräte (z. B. ICL004/V5.4.5) flashen nicht von selbst: Sie nehmen die
  Firmware mit HTTP 200 an, merken sie aber nur vor und wenden sie erst beim nächsten
  **Neustart** an (dieselbe Reboot-Semantik wie bei der IP-Umstellung). Bisher wurde
  dieser Neustart nie ausgelöst → die Kamera lief mit der alten Firmware weiter und der
  Dialog wartete endlos auf einen Reboot, der nie kam. Jetzt stößt `upgrade_firmware`
  den Neustart selbst an, sobald der Upload mit einem sauberen HTTP 200 quittiert wird
  (bleibt die Verbindung bestehen = vorgemerkt). Geräte, die von sich aus flashen
  (Verbindungsabbruch), verhalten sich unverändert. **An echter Hardware verifiziert**
  (ICL004, `192.0.2.156`): echter Flash der `digicap.dav` → Upload HTTP 200 →
  Neustart ausgelöst → Kamera ging offline und kam gesund zurück (vorher blieb sie oben
  → Endlos-Warten); ungültige Datei → HTTP 500 „Device Error" (korrekt als Fehler
  gemeldet).

## 26.08.08b1 — 2026-08-08

- **Hikvision: nach IP-Umstellung wird der nötige Neustart automatisch ausgelöst.**
  Ältere Geräte übernehmen eine Umstellung auf DHCP (oder eine neue feste IP) erst nach
  einem Reboot und antworten mit „Reboot Required". Statt das nur als Hinweis anzuzeigen,
  stößt das Programm den Neustart jetzt selbst an (`PUT /ISAPI/System/reboot`). Die
  Rückmeldung lautet dann z. B. „auf DHCP umgestellt — Neustart automatisch ausgelöst".
  Best effort: schlägt der Neustart-Aufruf fehl, bleibt die (bereits übernommene)
  IP-Änderung erfolgreich und es erscheint ein entsprechender Hinweis.

## 26.08.08 — 2026-08-08

- **Hikvision: werksneue Kameras im fremden IP-Segment werden jetzt gefunden.** Die
  SADP-Discovery empfing bisher keine Antworten von Kameras auf ihrer Werks-IP (z. B.
  `192.0.0.64`/`192.168.1.64`), wenn der Rechner in einem anderen Segment steht.
  Ursache: SADP-Geräte schicken ihre `ProbeMatch`-Antwort an die **Multicast-Gruppe**
  `239.255.255.250:37020`, nicht per Unicast — der alte Code band aber nur einen
  Ephemeral-Port ohne Gruppenbeitritt und sah die Antworten nie. Jetzt wird auf Port
  37020 gebunden und der Multicast-Gruppe (auf allen Interfaces) beigetreten
  (`SO_REUSEPORT` für Koexistenz mit der offiziellen SADP-Software; Fallback auf
  Ephemeral, falls der Port belegt ist), periodisch nachgefragt und pro Interface
  gesendet. **An echter Hardware verifiziert** (ICL004 auf `192.0.0.64`, Rechner in
  `192.0.2.0/24`). Nebenbei liest die Discovery jetzt die Firmware (`SoftwareVersion`)
  mit aus.
- **Build:** Python-Pin auf **3.14.7** angehoben (täglicher Dependency-Check; Tcl/Tk
  9.0.4, OpenSSL 3.5.7 LTS, libffi 3.7.1 bleiben aktuell).

## 26.08.02b3 — 2026-08-02

- **Regression aus b2 behoben: Suche/Aktualisierung blieb bei Axis-Kameras hängen.**
  Beim Dead-Code-Aufräumen (b2) wurde in `axis/discovery.py` der Import
  `get_first_ip` mitentfernt — er sah dort ungenutzt aus, wird aber **re-exportiert**:
  `axis/plugin.py` löst die Kamera-IP über `discovery.get_first_ip(camera)` auf.
  Dadurch warf `ip_of()` (und damit `check_online`/`device_info` jeder Axis-Kamera)
  einen `AttributeError` außerhalb der Fehlerbehandlung, was die Fortschrittszählung
  der Hintergrund-Worker zerstörte → „Suchen/Aktualisieren" endete nie. Der Import
  ist wiederhergestellt und als bewusster Re-Export kommentiert.

## 26.08.02b2 — 2026-08-02

- **Toten Code entfernt (Aufräumen, keine Funktionsänderung).** Statische Analyse
  (pyflakes/vulture) durchgegangen: ungenutzte Importe raus (`config_dir` in
  `app.py`; `ALL_CAMERAS_ID`/`camera_key` in `settings_dialog.py`; die
  `FIELD_NAMES`-Doku-Importe der vier discovery-Module — als Kommentar erhalten);
  ungenutzte Funktionen entfernt (`sunapi.get_mac`, `sunapi._interface`,
  `GroupStore.forget` — es gibt nur noch `forget_many`, `VendorPlugin.action_dialogs`
  — die Zuordnung läuft über `ACTION_DIALOGS`); Schleifenvariable `field` (Shadow des
  `dataclasses.field`) in `groups.py` umbenannt.
- **Nebenbei behoben:** Die Config-Backup-Exporte (Hanwha/Hikvision) verwarfen bei
  „Kamera nicht erreichbar" den eigentlichen Verbindungsfehler (tote `last_conn`-
  Variable). Dieser wird jetzt in die Fehlermeldung aufgenommen.

## 26.08.02b1 — 2026-08-02

- **AppImage verschlankt: ungenutzte Tcl-Erweiterungen und SQLite entfernt.** Der
  Tcl-9-„batteries-included"-Quellbaum liefert `[incr Tcl]`, `tdbc` (+ mysql/odbc/
  postgres), das `Thread`-Paket und `sqlite3` mit — das Programm nutzt keines davon
  (es ist bewusst datenbankfrei). Das Build-Skript wirft sie jetzt beim Verschlanken
  raus. Das reduziert Größe **und** die rechtliche Attributionsfläche auf die
  tatsächlich genutzten Komponenten.
- **Lizenz-Doku: Expat (libexpat) ergänzt.** Expat steckt in CPython (`pyexpat`) und
  ist Grundlage von `xml.etree` — das Programm parst damit alle Kamera-Antworten
  (ONVIF/Hikvision/Axis). MIT-lizenziert, GPL-3.0-kompatibel; jetzt in
  `THIRD_PARTY_LICENSES.md` und damit auch im Lizenz-Reiter aufgeführt.

## 26.08.02 — 2026-08-02

- **Neuer Reiter „Lizenzen" in den Einstellungen** (hinter „Über"). Zeigt in einem
  scrollbaren, schreibgeschützten Feld die Drittanbieter-Lizenzen aller gebündelten
  Komponenten (`THIRD_PARTY_LICENSES.md`) sowie den vollständigen GPL-3.0-Lizenztext
  des Programms (`LICENSE`). Beide Dateien werden neben `main.py` ausgeliefert
  (AppImage + Windows-.exe) und zur Laufzeit geladen — Muster wie beim Hilfe-Fenster
  (`sys._MEIPASS` im Frozen-Build, sonst Wurzelverzeichnis).

## 26.07.31b7 — 2026-07-31

- **Hanwha Config-Restore (Einspielen) gelöst und verifiziert.** Der frühere `Error
  607` lag am **falschen Upload-Format**: die Wisenet-Firmware erwartet die Datei
  **nicht** als Multipart, sondern die **rohen Bytes base64-kodiert** als
  `application/x-www-form-urlencoded`-Body (ermittelt aus dem Web-UI-JavaScript
  `configRestore` → `btoa(fileBytes)`). `sunapi.restore_config` sendet jetzt genau das;
  an der QNO-6082R (V1.41.18) quittiert die Kamera mit `OK` und startet neu. Hanwha-
  Import ist damit als verifiziert markiert (`config_backup_import_verified`), der
  Warnhinweis „noch nicht verifiziert" entfällt. `ExcludeSettings=Network` (Option „Netz
  behalten") bleibt bestehen.

## 26.07.31b6 — 2026-07-31

- **Bugfix: Aktionen an Nicht-Axis-Kameras schlugen mit 401 fehl.** Der Zugangsdaten-
  Block der Aktionsdialoge belegte den Benutzer fest mit `root` (Axis-Konvention).
  Hanwha/Hikvision/Dahua nutzen aber `admin` — ohne manuelle Korrektur scheiterte
  **jede** Aktion (Konfig-Backup, Werksreset, …) an der Authentifizierung. Neu: Plugin-
  Attribut `default_username`, mit dem der Dialog das Benutzerfeld herstellerabhängig
  vorbelegt (Axis `root`, Hanwha/Hikvision/Dahua/ONVIF `admin`).
- **Hanwha robuster gegen HTTP 490.** Wisenet-Kameras antworten mit `490`, wenn die
  Zahl gleichzeitiger CGI-Sitzungen erschöpft ist (offene Web-UI + Online-Prüfung +
  Aktion). Statt sofort abzubrechen, wartet der SUNAPI-Client jetzt kurz und versucht
  es erneut (bis zu 3×) — betrifft alle GET/POST inkl. Config-Backup, Restore, Firmware
  und Werksreset.

## 26.07.31b5 — 2026-07-31

- **Hikvision Konfig-Backup an echter Hardware verifiziert.** Export **und** Import
  laufen auf der ICLP041D (Firmware V5.4.5): Export lieferte den ~888-KB-Blob, der
  Import des eigenen Configs wurde vom Gerät mit Erfolgsstatus quittiert (kein Fehler
  wie Hanwhas 607), die Kamera kam nach dem Neustart unverändert zurück. Der Hikvision-
  Import ist damit als verifiziert markiert (neues Plugin-Flag
  `config_backup_import_verified`), der Warnhinweis „noch nicht verifiziert" entfällt für
  Hikvision. Bei Hanwha (Restore weiter offen) bleibt er stehen.

## 26.07.31b4 — 2026-07-31

- **Konfig-Backup jetzt auch für Hikvision.** Das Hikvision-Plugin meldet nun
  `CONFIG_BACKUP` und nutzt dieselbe Aktion/Dialoge wie Hanwha. Export/Import laufen
  über ISAPI `GET`/`PUT /ISAPI/System/configurationData` (opaker Blob,
  `application/octet-stream`; wie beim Firmware-Upload). Neue ISAPI-Funktionen
  `export_config`/`import_config` + Plugin-Methoden `export_config_backup`/
  `import_config_backup`.
  - **Noch nicht an Hardware verifiziert**, weil die Hikvision-Testkamera derzeit
    uninitialisiert auf der Werks-IP (192.0.0.64, anderes Subnetz) steht. Import ist im
    Dialog als ungetestet markiert; Plugin bleibt `experimental`. Hinweis: neuere
    Hikvision-Firmware (≥ 5.5.x) verlangt beim Config-Ex-/Import teils einen „security
    code".
- **Backup-Dialog vendor-abhängig.** Die Option „Netzwerkeinstellungen (IP) beibehalten"
  erscheint nur bei Plugins, die das können (neues Flag `config_backup_keep_network`;
  Hanwha ja, Hikvision nein). Der Warnhinweis zum Einspielen ist jetzt herstellerneutral
  formuliert (vorher „Wisenet").

## 26.07.31b3 — 2026-07-31

- **Werksreset jetzt für alle Hersteller erreichbar (Rechtsklickmenü).** Der Werksreset
  hing bisher im „Konfiguration"-Dialog, der nur bei `Capability.CONFIG` (= **nur Axis**)
  freigeschaltet ist — für **Hikvision, Hanwha, Dahua, ONVIF** war er dadurch trotz
  vorhandener, verifizierter `FACTORY_RESET`-Fähigkeit **nicht auslösbar**. Der Reset ist
  nun eine eigenständige Aktion (neuer `FactoryResetDialog`) und liegt im
  **Rechtsklick-Kontextmenü** der Kameraliste („Auf Werkseinstellungen zurücksetzen…"),
  sichtbar/aktiv für jede Auswahl, deren Plugin `FACTORY_RESET` meldet. Beide Modi wie
  gehabt: „mit Erhalt der IP" (`keep_ip`, wartet auf Neustart + Werkszustand) und
  „kompletter Reset inkl. IP". Aus dem Config-Dialog entfernt (eine Quelle statt zwei).

## 26.07.31b2 — 2026-07-31

- **Neue Aktion „Konfig-Backup" (Capability `CONFIG_BACKUP`).** Getrennt von der
  Axis-`CONFIG`-Vorlage (auswählbare Parameter) behandelt sie den opaken, geräte-/
  firmwaregebundenen Komplett-Backup-Blob mancher Hersteller. Erste Umsetzung:
  **Hanwha (Wisenet)** über SUNAPI. Neuer Dialog `ConfigBackupDialog` mit zwei
  Modi (Einspielen / Herunterladen), Datei-Auswahl und Option „Netzwerkeinstellungen
  (IP) beibehalten" (`ExcludeSettings=Network`). Endpunkte aus `attributes.cgi`
  gelesen: Export `configbackup&action=control`, Restore `configrestore&action=control`.
  Neue Plugin-Methoden `import_config_backup`/`export_config_backup` (Basis + Hanwha)
  und SUNAPI-Funktionen `export_config`/`restore_config`.
  - **Herunterladen** ist an echter QNO-6082R verifiziert (173-KB-Blob).
  - **Einspielen** ist auf dieser Firmware (1.41.18) **noch nicht verifiziert**: die
    Kamera lehnt den Upload mit `Error Code 607 (Unknown Error)` ab — sowohl für ein
    API-exportiertes als auch ein Web-UI-Backup, unabhängig von Feldname/
    `ExcludeSettings`/Passwort. Die Firmware nutzt beim Restore offenbar einen eigenen,
    undokumentierten Flow. Die Funktion bleibt enthalten, ist im Dialog aber klar als
    ungetestet markiert (Warnhinweis). Hanwha-Plugin bleibt `experimental`.
- **Rechtsklick-Kontextmenü:** neuer Punkt „Konfig-Backup" (nur bei Plugins mit
  `CONFIG_BACKUP`).
- **`.gitignore`:** `configfiles/` (lokale Kamera-Config-Backups) ausgeschlossen.

## 26.07.31b1 — 2026-07-31

- **Gespeicherte Zugangsdaten im Tresor einsehbar.** Einstellungen → **Tresor**
  hat bei entsperrtem Tresor einen neuen Punkt „Gespeicherte Zugangsdaten
  anzeigen…". Er öffnet eine read-only Übersicht aller im Vault gespeicherten
  Kamera-Zugangsdaten (Schlüssel/Benutzer/Passwort) mit **Scrollbar**, **Filter**
  (nach Schlüssel oder Benutzer), umschaltbarer **Passwort-Anzeige** (standardmäßig
  maskiert) und **„Passwort kopieren"** in die Zwischenablage. Neuer öffentlicher
  Vault-Accessor `PasswordVault.all_entries()` (statt Zugriff auf `_data`); neuer
  Dialog `_CredentialsViewer`. Nur bei entsperrtem Tresor erreichbar.

## 26.07.31 — 2026-07-31

- **Gruppenauswahl im Rechtsklickmenü mit Scrollbar & Filter.** „Zu Gruppe
  hinzufügen" öffnet nun einen kleinen Auswahldialog (Listbox mit vertikaler
  Scrollbar + Filterfeld) statt eines Kaskaden-Untermenüs. Bei vielen Gruppen
  entfällt damit das mühsame Pfeil-Scrollen des nativen `tk.Menu` (das prinzipiell
  keine Scrollbar unterstützt). Tippen filtert live, Doppelklick/Enter übernimmt;
  „Neue Gruppe…" bleibt als Schaltfläche erhalten. Neuer Dialog `_GroupPicker`
  (nach dem Muster von `_VersionPicker`).

## 26.07.25 — 2026-07-25

- **Firmware-Vorschlag: Axis' `latest/ver.txt` ist jetzt maßgeblich.** Der Axis-Repo
  markiert eine Version als „latest"; gelegentlich liegt schon ein numerisch **höherer**
  Versionsordner bereit (ein noch nicht als „latest" freigegebener Patch). Bisher konnte
  dadurch der **Vorschlag** höher ausfallen als die als **neueste** markierte Version
  (z. B. „neueste" 11.11.212, „Vorschlag" 11.11.220). `AxisPlugin.firmware_updates`
  filtert nun alle Versionen heraus, die neuer als der `latest/ver.txt`-Stand sind — sie
  werden weder vorgeschlagen noch in der Versionsauswahl gezeigt. Fällt `latest/ver.txt`
  aus (unerreichbar), gilt wie bisher der höchste Versionsordner als neueste.

## 26.07.23b3 — 2026-07-23

- **Englische In-App-Hilfe.** Der **„Help"-Button** zeigt im Englisch-Modus jetzt die
  englische Hilfe (`HILFE_EN.md`) statt der deutschen. `_open_help` wählt die Datei
  anhand der aktiven Sprache und fällt auf `HILFE.md` zurück, falls die englische fehlt.
  Die Hilfe verwendet die exakten englischen UI-Beschriftungen aus dem Katalog, passt
  also zur sichtbaren Oberfläche. `HILFE_EN.md` wird in AppImage (`build_appimage.sh`)
  und Windows-Build (`.spec`) mitgepackt. An bundled-AppImage-Python verifiziert:
  DE → deutsche, EN → englische Hilfe.

## 26.07.23b2 — 2026-07-23

- **i18n-Reihenfolge-Fix:** Die virtuellen Gruppennamen **„Alle Kameras"** und **„Ohne
  Gruppe"** blieben trotz vorhandener Übersetzung deutsch, weil `GroupStore()` (dessen
  Konstruktor `load()` aufruft und die Namen über `t()` übersetzt) in `MainWindow.__init__`
  **vor** `set_language()` stand — zur Ladezeit war also noch Deutsch aktiv. `set_language()`
  wird jetzt direkt nach dem Laden der Einstellungen und **vor** `GroupStore()` gesetzt;
  damit erscheinen die Gruppennamen im Englisch-Modus als „All cameras" / „Ungrouped".

## 26.07.23b1 — 2026-07-23

- **i18n-Nachtrag:** fünf über Variablen übergebene Beschriftungen fehlten im
  englischen Katalog und blieben dadurch deutsch — die Toolbar-Buttons **Benutzer**
  („Users"), **ONVIF-Benutzer** („ONVIF users") und **Konfiguration** („Configuration")
  sowie die virtuellen Gruppennamen **„Alle Kameras"** („All cameras") und **„Ohne
  Gruppe"** („Ungrouped"). Ursache: `t()` wird hier mit einer Variablen aufgerufen
  (`t(label)`, `t(ALL_CAMERAS_NAME)`), sodass die AST-Extraktion die Message-ID nicht
  als Literal sieht; die betroffenen Konstanten sind jetzt vollständig im Generator
  erfasst (Katalog: 465 Einträge, per AST + dynamischer Liste geprüft).

## 26.07.23 — 2026-07-23

- **Englische Übersetzung + Sprachauswahl.** Das Programm lässt sich jetzt auf
  Englisch umstellen (Einstellungen → Darstellung → „Sprache / Language"). Die Wahl
  wird in `settings.json` (`language`) gespeichert und **beim nächsten Programmstart**
  übernommen — dieselbe Mechanik wie „Beim Start maximiert öffnen" (kein Live-Umbau
  laufender Fenster). Übersetzt sind die gesamte Oberfläche (Hauptfenster, alle
  Aktions- und Einstellungsdialoge, Haftungshinweis) **und** die im Ergebnis-Log
  sichtbaren Plugin-Meldungen (Axis/VAPIX, Hikvision/ISAPI, Dahua, Hanwha/SUNAPI,
  ONVIF, ADM-Import, Firmware-Suche).
- **i18n-Schicht (`kkm/core/i18n.py` + `i18n_catalog.py`), stdlib-only.** Der
  deutsche Quelltext ist zugleich die Message-ID: `t("Text")` liefert ohne Katalog
  unverändert Deutsch zurück, im Englisch-Modus die Übersetzung, und fällt für fehlende
  Schlüssel auf den deutschen Quelltext zurück (rein additiv). Platzhalter laufen über
  benannte Felder (`t("… {ip} …", ip=…)`), sodass beide Sprachvarianten dieselbe
  Signatur haben. Interne Kennungen (FIELD_NAMES-Schlüssel, Spalten-IDs, Einstellungs-
  Keys, der Werkszustand-Marker) bleiben deutsch — nur Anzeige-Text geht durch `t()`,
  damit Persistenz, Export und `.kkmbackup` unverändert kompatibel bleiben.
- **Provenienz gewahrt:** die aus dem Axis_Kamera_Discovery-Tool verbatim übernommene
  `vapix.py` (und die übrigen stdlib-only-Clients) importieren `t` defensiv mit einem
  Fallback, bleiben also eigenständig ohne `kkm.core` lauffähig.

## 26.07.21b4 — 2026-07-21

- **Hanwha: Auslieferungszustand erkennen.** Eine werksneue oder zurückgesetzte
  Wisenet-Kamera blockiert die gesamte SUNAPI mit HTTP **403** (eine initialisierte
  verlangt dagegen eine Anmeldung, 401). `is_unconfigured` nutzt diesen Unterschied,
  sodass solche Kameras im Hauptfenster als **„Ersteinrichtung erforderlich"** geführt
  werden, statt vergeblich nach einem Passwort zu fragen (wie bei Axis/Hikvision). Das
  **Setzen** des Erstpassworts bleibt der Wisenet-Web-UI vorbehalten (RSA-verschlüsselt);
  über die reguläre API ist es im uninitialisierten Zustand bewusst nicht möglich. An
  echter Hardware verifiziert.

## 26.07.21b3 — 2026-07-21

- **Hanwha-Firmware-Upload an echter Hardware verifiziert** — Fehler behoben: Der
  SUNAPI-Firmware-Endpunkt verlangt zwingend den Parameter **`Type=Normal`** (fehlt
  er, antwortet die Kamera mit „Invalid Input Value"); der Multipart-Feldname ist
  dagegen egal. Die Antwort ist ein **Status-Stream** (`DownloadAck` → `DownloadOK`
  → … → `End`/`OK` bzw. `Fail`/`Skip`), der jetzt ausgewertet wird: `Fail` wirft
  einen Fehler, `Skip` (gleiche Version bereits installiert) wird als solches
  gemeldet, beim eigentlichen Flashen kappt das Gerät die Verbindung (Reboot) = 
  Erfolg. Ein echter 52-MB-Flash an der Wisenet QNO-6082R lief erfolgreich durch.
- **Hanwha-Werksreset (`keep_ip`) an echter Hardware verifiziert** (lief ohne
  Codeänderung): `ExcludeSettings=Network` behält die IP-Adresse, der übrige
  Auslieferungszustand wird hergestellt (das Admin-Passwort wird dabei
  zurückgesetzt — normales Reset-Verhalten). Damit sind **alle acht Capabilities**
  des Hanwha-Plugins an echter Hardware getestet.

## 26.07.21b2 — 2026-07-21

- **Neues (experimentelles) Hanwha-/Wisenet-Plugin.** Viertes Hersteller-Plugin,
  direkt an echter Hardware (Wisenet QNO-6082R, Firmware 1.41.18) entwickelt und
  verifiziert: Gerätesuche (ONVIF-WS-Discovery, auf Hanwha gefiltert über den
  ONVIF-`manufacturer`-Scope), Geräteinfo inkl. MAC, IP setzen (fest/DHCP),
  Benutzerverwaltung, ONVIF-Benutzer (über den bestehenden ONVIF-SOAP-Client) —
  alles über **SUNAPI** (`/stw-cgi/`, HTTP-Digest, `KEY=VALUE`, stdlib-only). Der in
  der Recherche befürchtete Haken (SUNAPI-Doku NDA-gebunden) entfiel: die Kamera
  **dokumentiert ihre eigene API** unter `/stw-cgi/attributes.cgi/<cgi>`. Kein
  `FIRMWARE_CHECK`, kein `CONFIG`. Im Plugin-Manager als **„experimentell"**
  gekennzeichnet und **ab Werk ausgeschaltet**; Firmware-Upload und Werksreset sind
  implementiert, aber noch nicht an Hardware getestet (nur ein Modell insgesamt).
  SUNAPI-Eigenheiten, die beim Hardware-Test auffielen und im Code berücksichtigt
  sind: Schreib-Antworten stehen als `OK`/`NG`+Fehlercode im **200-Body** (nicht im
  HTTP-Status); die Action heißt `update` (nicht `add/update`); Benutzer sind feste
  Slots (`user1..userN`, ein freier Slot ist ein deaktivierter); `IPv4Type=Manual`
  und `IPv4PrefixLength` darf nicht zusammen mit `IPv4SubnetMask` gesendet werden.
- Das generische ONVIF-Discovery-Dict trägt jetzt zusätzlich den Hersteller aus dem
  ONVIF-Scope (`_manufacturer`) — darüber filtert das Hanwha-Plugin seine Treffer.

## 26.07.21b1 — 2026-07-21

- **Hikvision-Firmware-Upload an echter Hardware verifiziert** — zwei Fehler behoben:
  - **Falscher Content-Type.** Die Firmware (`.dav`) wurde wie alle anderen Aufrufe
    als `application/xml` gesendet; das Gerät versucht sie dann als XML zu parsen und
    lehnt mit HTTP 400 ab. Der Upload nutzt jetzt `application/octet-stream` (der
    ISAPI-Request-Helfer nimmt dafür einen `content_type`-Parameter).
  - **Irreführende Fehlermeldung.** Passt die Firmware nicht zum Modell, meldet das
    getestete Gerät den generischen `statusString` „Invalid XML Content"; die wahre
    Ursache steht im `subStatusCode` (`badDevType`). Die Fehlerauswertung übersetzt
    bekannte Sub-Codes jetzt klar (z. B. „Firmware passt nicht zu diesem Gerätemodell").

  Damit ist der Upload-Weg (Endpunkt, PUT, Content-Type, Fehlerbehandlung) bestätigt:
  das Gerät empfängt und **validiert** die Firmware. Ein tatsächliches Flashen war
  nicht möglich, weil die vorliegende `.dav` für ein anderes Modell ist — die Kamera
  hat sie korrekt (und ohne Schaden) abgelehnt. Damit sind **alle acht Capabilities**
  des Plugins an echter Hardware getestet.

## 26.07.21 — 2026-07-21

- **Hikvision-Plugin an echter Hardware verifiziert** (ein STD-CGI-OEM-Gerät,
  ISAPI-Firmware V5.4.5) — dabei drei Fehler in den Schreib-Aktionen behoben:
  - **IP setzen scheiterte mit „Invalid XML Content" (HTTP 400).** Ältere ISAPI-
    Geräte akzeptieren beim `PUT` auf `…/ipAddress` nur das **vollständige**
    Objekt, nicht einen minimalen Payload. `set_static_ip`/`set_dhcp` arbeiten jetzt
    per **Read-Modify-Write**: das aktuelle `ipAddress`-Objekt wird gelesen und nur
    Adresstyp/IP/Maske/Gateway geändert.
  - **IP-Update hätte IPv6 abgeschaltet.** Der alte Payload sendete hart
    `ipVersion=v4`; auf einem Dual-Stack-Gerät (`dual`) hätte das IPv6 deaktiviert.
    Durch Read-Modify-Write bleiben `ipVersion`, IPv6-Adressen und DNS erhalten
    (verifiziert: IPv6 unverändert nach dem Setzen).
  - **„Reboot Required" wurde als Fehler gewertet.** Das Gerät quittiert eine
    übernommene IP-Änderung mit `statusCode 1` + „Reboot Required" — das ist ein
    Erfolg mit Hinweis, kein Fehler. Neue zentrale Status-Auswertung `_check_status`
    (prüft `statusCode`, behandelt „Reboot Required" als Erfolg, benennt den Lockout)
    für alle Schreib-Aktionen.

  Verifiziert: SADP-Discovery, Online-/Geräteinfo, Auslieferungszustand, Benutzer
  anlegen/ändern, IP fest/DHCP, ONVIF-Benutzer sowie Werksreset in **beiden Modi** —
  mit Erhalt der Netzwerkeinstellungen (`mode=basic`: IP und Admin-Zugang bleiben)
  und vollständig (`mode=full`: Kamera fällt auf ihre Werks-IP zurück). Beide
  Reset-Modi liefen ohne Codeänderung. **Weiterhin experimentell**, weil allein der
  Firmware-Upload noch nicht an echter Hardware getestet ist (die riskanteste
  Aktion — er braucht eine modellpassende `.dav`).

## 26.07.19b4 — 2026-07-19

- **Neues (experimentelles) Dahua-Plugin.** Zweites Hersteller-Plugin nach dem
  Hikvision-Muster: Gerätesuche per **DHIP** (UDP-Multicast 37810, liefert MAC/Modell/
  Seriennummer/Firmware), Geräteinfo, IP setzen (fest/DHCP), Benutzerverwaltung,
  ONVIF-Benutzer (über den bestehenden ONVIF-SOAP-Client wiederverwendet),
  Firmware-Upload und Werksreset — alles über die **Dahua HTTP API** (HTTP-Digest,
  `KEY=VALUE` wie Axis `param.cgi`, stdlib-only). Kein `FIRMWARE_CHECK` (kein offenes
  Firmware-Verzeichnis) und kein `CONFIG` (kein Fleet-Vorlagenformat). Im
  Plugin-Manager als **„experimentell"** gekennzeichnet und **ab Werk ausgeschaltet**;
  die genauen `setConfig`-Payloads folgen der (halb-öffentlichen) Dahua-Dokumentation,
  sind aber noch nicht an Hardware verifiziert. **Bonus:** deckt zugleich viele
  Dahua-OEM-Marken ab (u. a. **Honeywell Performance Series**, Amcrest).
- Recherche-Notizen für weitere mögliche Plugins ergänzt (Hanwha, ACTi, Dahua, ABUS,
  Honeywell). ABUS und Honeywell sind überwiegend OEM-Ware und laufen über das
  Hikvision- bzw. Dahua-/ONVIF-Plugin — ein eigenes Plugin lohnt dort nicht.

## 26.07.19b3 — 2026-07-19

- **Neues (experimentelles) Hikvision-Plugin.** Erstes Hersteller-Plugin nach Axis:
  Gerätesuche per **SADP** (UDP-Multicast 37020, liefert MAC/Modell/Seriennummer/
  Aktivierungsstatus), Geräteinfo, IP setzen (fest/DHCP), Benutzerverwaltung,
  ONVIF-Benutzer (über den bestehenden ONVIF-SOAP-Client wiederverwendet),
  Firmware-Upload (`.dav`) und Werksreset — alles über die **ISAPI**-Schnittstelle
  (HTTP-Digest, XML, stdlib-only, gleiches Muster wie `vapix.py`). Kein
  `FIRMWARE_CHECK` (kein offenes Firmware-Verzeichnis) und kein `CONFIG` (ISAPI hat
  keine Fleet-Konfigurationsvorlage), analog zum ONVIF-Plugin.
- **Plugins können sich als „experimentell" kennzeichnen** (neues Basis-Flag
  `VendorPlugin.experimental`). Der Plugin-Manager (Einstellungen → Plugins) hängt
  „(experimentell)" an den Namen und zeigt einen Warnhinweis, dass solche Plugins noch
  nicht an echter Hardware geprüft sind. Das Hikvision-Plugin ist so markiert und wie
  das ONVIF-Plugin **ab Werk ausgeschaltet**. Die genauen ISAPI-Payloads (v. a. IP und
  Benutzer) folgen der Dokumentation, sind aber noch nicht an Hardware verifiziert;
  ISAPI-Besonderheiten (uhrzeitempfindlicher Digest, Konto-Sperre nach zu vielen
  Fehlversuchen) werden mit eigenen Fehlermeldungen behandelt.

## 26.07.19b2 — 2026-07-19

- **Neue Spalte „IPv6-Adresse" samt Erkennung.** Die Suche erfasst jetzt auch die
  IPv6-Adressen der Kameras: das Axis-Plugin fragt per mDNS zusätzlich
  AAAA-Records ab (`Zeroconf(ip_version=All)`, mit Rückfall auf IPv4 auf Hosts
  ohne IPv6-Stack), das ONVIF-Plugin wertet IPv6-XAddrs der WS-Discovery-Antwort
  aus, statt sie zu verwerfen. Anzeige kommagetrennt, globale Adressen vor
  Link-Local (fe80::); die Spalte ist wie gewohnt ausblendbar und wird beim
  CSV-Export mitgeschrieben (neues Basisfeld „IP Adresse: IPv6"). IPv6 fließt
  auch in die Duplikat-Erkennung Hersteller-/ONVIF-Treffer ein. Die **Aktionen**
  (IP setzen, Benutzer, Firmware …) laufen weiterhin über IPv4 — reine
  IPv6-Antworten ohne IPv4-Adresse werden daher weiterhin übersprungen.

## 26.07.19b1 — 2026-07-19

- **ONVIF- und Hersteller-Plugin melden dieselbe Kamera nicht mehr als zwei
  Geräte.** Die Entdopplung hatte zwei Lücken: Sie verglich nur die *erste* IP
  (Kameras mit mehreren Adressen fielen durch) und sie griff nur innerhalb eines
  Suchlaufs — fand mDNS die Kamera einmal nicht (oder war das Hersteller-Plugin
  zeitweise deaktiviert), blieb der generische ONVIF-Treffer unter seiner
  Geräte-UUID dauerhaft neben der MAC-Identität im Bestand. Jetzt wird über
  **alle** gemeldeten IPs verglichen, und nach jeder Suche werden bestehende
  Duplikate im Bestand zusammengeführt: Gruppenzugehörigkeiten, Online-Status und
  gespeicherte Zugangsdaten (Tresor/Sitzung) wandern zur Hersteller-Identität,
  der generische Eintrag verschwindet. Die Statuszeile meldet die Anzahl der
  Zusammenführungen.

## 26.07.19 — 2026-07-19

Stabilitäts-/Robustheits-Durchsicht des gesamten Codes; zehn Punkte behoben:

- **Beschädigte `groups.json` crasht den Start nicht mehr.** Die Datei wird als
  `groups.json.corrupt` beiseitegelegt (nicht gelöscht) und die App startet mit
  leerem Bestand. Unbekannte Felder und einzelne kaputte Gruppen-Einträge werden
  übersprungen statt mit `TypeError` zu scheitern (Vorwärtskompatibilität).
- **Beschädigte Tresor-Datei liefert eine klare Fehlermeldung.** `unlock()` wirft
  jetzt immer `VaultError` — vorher schlug ein korruptes `vault.enc` als
  unbehandelte `JSONDecodeError` im Klick-Handler des Schloss-Buttons auf.
- **Aktions-Dialoge:** Die Poll-Schleife endet sauber, wenn der Dialog geschlossen
  wird, während ein Durchlauf noch Meldungen liefert (vorher `TclError` auf
  zerstörten Widgets). Beim Schließen während eines laufenden Durchlaufs wird
  zudem nachgefragt.
- **Tresor sperren während der Hintergrund-Anreicherung** (Firmware/Modell nach
  der Suche) ließ den Worker sterben — die Progressbar lief endlos. Der Fall wird
  jetzt als Fehlversuch gezählt und der Lauf endet normal.
- **`auto`-Schema (HTTPS→HTTP) fällt nur noch bei Verbindungsfehlern zurück,**
  nicht mehr bei HTTP-Fehlern wie 401. Vorher wurden Zugangsdaten nach einem
  fehlgeschlagenen HTTPS-Login nochmals im Klartext über HTTP gesendet, jeder
  Fehlversuch zählte doppelt (schnellere Brute-Force-Sperre des Geräts) und die
  angezeigte Fehlermeldung stammte vom zweiten Versuch (neu: `VapixConnectError`).
- **Fortlaufende IP-Vergabe überspringt `.0`/`.255`** (Netz-/Broadcast-Adresse im
  üblichen /24) — vorher konnte eine Kamera die unerreichbare `x.y.z.255`
  bekommen. `next_ip` erkennt außerdem den Überlauf hinter `255.255.255.255`.
- **Einstellungen-Speichern wirft nicht mehr,** wenn das Config-Verzeichnis nicht
  beschreibbar ist (hing u. a. am Spaltenziehen in der Tabelle — jeder Klick hätte
  einen Fehler ausgelöst); die Einstellungen gelten dann nur für die Sitzung.
- **Aktions-Buttons/Kontextmenü grauen jetzt wirklich aus,** was das Plugin der
  ausgewählten Kameras nicht kann (z. B. „Konfiguration“/„Firmware“ bei
  generischen ONVIF-Kameras) — bisher öffnete der Dialog und jede Kamera schlug
  mit einer leeren Fehlermeldung fehl.
- **Toten, fehlerhaften Code entfernt:** `AxisDiscovery.on_service_state_change`
  referenzierte das nicht existierende `Zeroconf.StateChange`.
- **Suche doppelt so schnell bei mehreren Plugins:** Axis-mDNS und ONVIF-
  WS-Discovery warten jeweils das volle Timeout ab und laufen jetzt parallel statt
  nacheinander (10 s statt 20 s bei zwei aktiven Plugins). Scheitert ein Plugin,
  bleiben die Treffer der anderen erhalten und der Fehler wird gemeldet.

## 26.07.17b3 — 2026-07-17

- **AppImage von ~64 MB auf ~21 MB verkleinert** — reiner Build-Ballast, der zur
  Laufzeit nie angefasst wird, wird jetzt aus der AppDir entfernt: statische
  Bibliotheken (`libpython3.14.a` ~69 MB, `libcrypto/ssl.a` ~14 MB), Header,
  Manpages/Doku, `pkgconfig`/`cmake`, `ensurepip` samt gebündeltem pip-Wheel, die
  `openssl`-Kommandozeile sowie die Test-Suiten/Testmodule der Standardbibliothek.
  Zusätzlich werden alle mitgelieferten `.so` und das Python-Binary gestrippt und
  das SquashFS mit zstd (Stufe 19) gepackt. **Wichtig:** `libtcl*`/`libtk*` werden
  bewusst *nicht* gestrippt — Tcl/Tk 9 hängen ihre Script-Library (`init.tcl` …) per
  zipfs an die `.so` an; `strip` würde diese Daten verwerfen. Funktional unverändert
  (ssl/HTTPS, Tk, ctypes/zeroconf, Tresor geprüft).

## 26.07.17b1 — 2026-07-17

- **Haftungshinweis beim Programmstart.** Ein Popup weist darauf hin, dass dies kein
  offizielles Tool der unterstützten Hersteller ist und die Nutzung auf eigene Gefahr
  erfolgt. Mit „OK" wird der Hinweis geschlossen; eine Checkbox „Ich weiß, was ich
  tue – nicht wieder anzeigen" bestätigt ihn dauerhaft. Solange sie nicht gesetzt
  ist, erscheint der Hinweis bei jedem Start. Derselbe Warntext steht zusätzlich
  unter **Einstellungen → Über**.

## 26.07.17 — 2026-07-17

- **Kontextmenü „Zu Gruppe hinzufügen“ jetzt alphabetisch sortiert.** Die Gruppen
  standen bislang in der internen Speicherreihenfolge; sie werden nun (unabhängig von
  Groß-/Kleinschreibung) nach Namen sortiert angezeigt.

## 26.07.11b13 — 2026-07-11

- **Abhängigkeiten geprüft; libffi auf 3.7.1 angehoben** (vorher 3.6.0 — zwei Versionen
  im Rückstand). Alles andere ist bereits auf dem neuesten unterstützten Stand: Python
  3.14.6, Tcl/Tk 9.0.4, OpenSSL 3.5.7 (neuester Patch des **LTS**-Zweigs; 3.6/4.0 gibt es,
  sind aber nicht die langfristig gepflegten Zweige) sowie — da `requirements.txt` bewusst
  ungepinnt ist — zeroconf 0.150.0, cryptography 49.0.0, sv-ttk 2.6.1, cffi 2.1.0.
  Geprüft wurde nicht das Skript, sondern die gebaute Umgebung: echter FFI-Aufruf über
  `ctypes`, `ifaddr` und `zeroconf` laufen mit der neuen libffi (`libffi.so.8.4.1`).

## 26.07.11b12 — 2026-07-11

- **Spalten lassen sich jetzt auch über die Fensterbreite hinaus ziehen** — dann erscheint
  der waagerechte Scrollbalken. Bisher standen die Spalten auf `stretch`, wodurch Tk die
  Spaltensumme stets auf die Fensterbreite zurückrechnete: Breiterziehen nahm dem Nachbarn
  nur Platz weg, breiter als das Fenster konnte die Tabelle nie werden. Ohne `stretch`
  wächst die Summe, der Balken erscheint (und verschwindet wieder, sobald es passt).
- Damit die Spalten beim ersten Start trotzdem das Fenster ausfüllen, werden sie einmalig
  auf die verfügbare Breite eingepasst. Gespeicherte Breiten kommen dadurch außerdem
  **exakt** zurück (vorher skalierte `stretch` sie beim Start wieder um).

## 26.07.11b11 — 2026-07-11

- **Spaltenbreiten der Geräteliste lassen sich wieder ziehen.** Die Spalten hatten
  `minwidth` **gleich** ihrer Vorgabebreite (160 px) — damit standen alle Spalten auf ihrem
  Minimum und ließen sich weder schmaler ziehen (Minimum erreicht) noch breiter (die
  Nachbarspalten konnten nicht nachgeben). Die Mindestbreite liegt jetzt bei 70 px; das
  Ziehen an der Spaltengrenze funktioniert in beide Richtungen, und bei zu schmalem Fenster
  erscheint weiterhin der waagerechte Scrollbalken.
- **Die eingestellten Breiten bleiben erhalten** (neu in `settings.json`:
  `column_widths`) — sie werden nach dem Ziehen gespeichert und beim nächsten Start
  wiederhergestellt.
- Hilfe und Benutzerhandbuch entsprechend ergänzt.

## 26.07.11b10 — 2026-07-11

- **Firmware-Dialog passt jetzt auf kleine Bildschirme.** Die Modell-/Kameraliste war fest
  zehn Zeilen hoch und hatte **keinen Scrollbalken** — bei vielen Kameras (oder aufgeklappten
  Modellzeilen) war der Rest praktisch nicht erreichbar, und der Dialog wurde auf 768p-
  Bildschirmen unten abgeschnitten. Die Liste ist nun **scrollbar** (Balken erscheint nur,
  wenn nötig) und ihre Höhe richtet sich nach der Zahl der Modelle, gedeckelt auf 7 Zeilen —
  auf niedrigen Bildschirmen auf 4. Aufklappen lässt den Dialog dadurch nicht mehr wachsen.
  Zusätzlich kompakter: kürzere Hinweistexte, der Warnhinweis steht neben dem Knopf statt
  darüber, und das Ergebnis-Log ist in diesem Dialog kleiner. Die Dialoghöhe liegt damit
  konstant bei rund 660 px (vorher über 800 px und mit der Kameraliste wachsend); Aktions-
  Dialoge werden generell nicht höher als der Bildschirm.
- Der auto-versteckende Scrollbalken-Helfer des Hauptfensters liegt jetzt in
  `kkm/gui/widgets.py` — die Dialoge brauchen ihn ebenfalls.

## 26.07.11b9 — 2026-07-11

- **Eingebaute Hilfe (`HILFE.md`) auf den aktuellen Stand gebracht.** Sie kannte die
  neueren Funktionen noch nicht und behauptete weiterhin „derzeit nur Axis". Ergänzt:
  **Update-Suche** im Firmware-Abschnitt (Spalte *Verfügbar (online)*, Download mit
  Zuweisung, LTS-treuer Vorschlag, Vergleichsbasis bei gemischten Ständen), die
  **Auswahl beim Konfigurations-Import** (Parameter, Stream-Profile einzeln, VMD4 — samt
  Begründung, warum man eine `.cfg` selten komplett übernimmt), ein neuer Abschnitt
  **„Plugins: Axis und ONVIF"** (wer was kann, ONVIF ab Werk aus, Voraussetzungen:
  ONVIF-Benutzer und Kamera-Uhr), die Entdopplung doppelter Suchtreffer sowie die neuen
  Einstellungen der Update-Suche. Die Hilfe wird als Rohtext angezeigt — der Abschnitt
  kommt daher ohne Markdown-Tabelle aus.

## 26.07.11b8 — 2026-07-11

- **Benutzerhandbuch als PDF** (`Benutzerhandbuch.pdf`, 11 Seiten): Titelseite mit
  Programm-Icon, verlinktes Inhaltsverzeichnis, alle Funktionen ausführlich beschrieben —
  inklusive der neuen (Firmware-Update-Suche, ONVIF-Plugin mit Fähigkeiten-Tabelle,
  Auswahl beim Konfigurations-Import), dazu Installation, erste Schritte, Fehlersuche und
  Glossar. Quelle ist `BENUTZERHANDBUCH.md`; `tools/make_manual.py` erzeugt daraus das PDF
  (benötigt `reportlab`, nur zum Bauen der Doku, keine Laufzeit-Abhängigkeit).

## 26.07.11b7 — 2026-07-11

- **Windows-`.exe`: Unterstrich statt Bindestrich vor der Version** —
  `dist\Kamerakonfigurationsmanager_26.07.11b7.exe` statt
  `Kamerakonfigurationsmanager-26.07.11b7.exe`. Betrifft nur den Dateinamen (PyInstaller-Spec
  und `build_windows.ps1`); die AppImage behält ihr bisheriges Schema.

## 26.07.11b6 — 2026-07-11

- **Auch beim Import lässt sich jetzt auswählen, was übernommen wird.** Bisher wurde eine
  `.cfg` immer vollständig auf alle gewählten Kameras geschrieben — inklusive der Dinge,
  die man selten mitschleppen will (die Netzwerk-/Zeitserver-Einstellungen der Quellkamera
  stehen genauso in der Datei wie die Bildeinstellungen). Der *Importieren*-Knopf öffnet
  nun denselben Auswahldialog wie das Auslesen: durchsuchbare Parameterliste zum An- und
  Abwählen, **Stream-Profile einzeln** und die **Bewegungserkennung (VMD4)**. Voreingestellt
  ist alles, was die Datei enthält; vor dem Schreiben fasst eine Rückfrage zusammen, was auf
  wie viele Kameras geht.
- **Stream-Profile sind auch beim Export einzeln wählbar** (vorher nur „alle oder keine") —
  beide Richtungen teilen sich denselben Dialog (`ConfigSelectDialog`).
- Dafür nehmen `apply_adm_config()` (VAPIX) sowie `import_config()` / `write_config_file()`
  (Plugin-Seam) nun `selected_params`, `selected_profiles` und `with_vmd4` entgegen; ohne
  Angabe bleibt das Verhalten unverändert (alles).

## 26.07.11b5 — 2026-07-11

- **Neues Plugin: ONVIF (generisch).** Ein zweites Plugin neben Axis — es spricht nur den
  standardisierten *Device-Management*-Dienst und funktioniert damit herstellerübergreifend
  mit jeder ONVIF-Kamera. Es kann bewusst **weniger** als das Axis-Plugin:
  - **Enthalten:** Gerätesuche (WS-Discovery statt mDNS), Online-Prüfung, Geräte-Info
    (Hersteller/Modell/Firmware/Seriennummer), IP-Adresse (fest/DHCP inkl. Gateway),
    ONVIF-Benutzer (anlegen/Passwort ändern), Werksreset (Soft/Hard).
  - **Nicht enthalten:** *Konfiguration* — ONVIF kennt kein Parameter-Template
    (`GetSystemBackup` liefert nur einen undurchsichtigen Blob für genau dieses Gerät);
    *Firmware* — die beiden ONVIF-Wege sind optional und uneinheitlich umgesetzt;
    *Update-Suche* — es gibt kein standardisiertes Firmware-Verzeichnis; *Benutzer* — der
    Standard kennt nur **eine** Benutzerliste, und das ist die ONVIF-Liste. Die
    entsprechenden Knöpfe bleiben für ONVIF-Geräte ausgegraut.
  - **Anmeldung** per WS-Security-UsernameToken mit Passwort-Digest. Der Zeitstempel wird
    an die **Uhr der Kamera** angeglichen (`GetSystemDateAndTime`, laut Spec ohne
    Anmeldung erreichbar) — ohne das schlägt die Anmeldung bei Zeitversatz fehl, ohne
    erkennbaren Grund.
  - **Ab Werk ausgeschaltet** und im Plugin-Manager zuschaltbar: Das Plugin findet auch
    Kameras, für die es ein Hersteller-Plugin gibt. Sind beide an, verwirft die Suche den
    generischen Treffer, wenn dieselbe IP schon von einem Hersteller-Plugin kam — sonst
    stünde dieselbe Kamera zweimal in der Liste (Kennung: MAC gegen ONVIF-UUID).
  - Auf einen WS-Discovery-Probe antworten auch Windows-Rechner und Drucker (WSD,
    Port 5357); die Suche prüft daher die Typ-Angabe und nimmt nur Videosender.
  - Keine neue Abhängigkeit: `urllib` + `hashlib` + `socket` + `xml.etree`, wie im
    Axis-Plugin.

## 26.07.11b4 — 2026-07-11

- **Herstellergrenze wieder hergestellt (Vorarbeit für ein zweites Plugin).** CLAUDE.md
  behauptete, die GUI rede nur über `VendorPlugin` mit den Herstellern — tatsächlich
  importierten `kkm/gui/` und sogar `kkm/core/groups.py` an neun Stellen direkt aus dem
  Axis-Plugin. Solange es nur Axis gab, fiel das nicht auf; ein zweites Plugin wäre daran
  gescheitert. Aufgeräumt:
  - Neu: `kkm/core/camera.py` — die Form des Kamera-Dicts (`FIELD_NAMES`) und die Helfer
    darauf (`get_first_ip`, `next_ip`, `version_tuple`, `parse_user_list`,
    `export_results`). Nichts davon war je Axis-spezifisch, es lag nur im Axis-Plugin.
  - Die Dialoge holen Rollen (`USER_ROLES`), ONVIF-Stufen (`ONVIF_LEVELS`) und die
    Dateiparser jetzt von der **Plugin-Instanz** (neu: `ActionDialog.plugin0()`) statt von
    der Klasse `AxisPlugin`. Neu im Seam: `parse_config_file()` / `write_config_file()`
    (Konfigurationsdatei) und `firmware_cache_size()` / `clear_firmware_cache()`.
  - Der ADM-Import im Einstellungs-Dialog erscheint nur noch, wenn das Axis-Plugin
    vorhanden ist; die Sicherung darunter ist herstellerneutral und bleibt.
  - Keine Funktionsänderung — dieselben Dialoge, dieselben Rollen, dieselben Meldungen.

## 26.07.11b3 — 2026-07-11

- **Windows-`.exe` trägt jetzt die Versionsnummer im Namen** — wie die AppImage:
  `dist\Kamerakonfigurationsmanager-26.07.11b3.exe` statt bisher
  `Kamerakonfigurationsmanager.exe`. Die Version liest die PyInstaller-Spec selbst aus
  `kkm/version.py` (einzige Quelle der Wahrheit), ein direkter PyInstaller-Aufruf
  benennt die Datei also genauso wie der Aufruf über `build_windows.ps1`. Das Skript
  kennt zudem — analog zu `build_appimage.sh --bump` — den Schalter `-Bump`, der die
  Version vor dem Bauen erhöht, und prüft am Ende, dass die erwartete Datei entstanden ist.

## 26.07.11b2 — 2026-07-11

- **Fehlermeldung beim Programmstart behoben.** Beim Aufbau des Hauptfensters warf Tk
  jedes Mal `AttributeError: … has no attribute 'group_tree'` auf die Konsole: Der
  `trace_add`-Beobachter des Gruppen-Suchfelds war schon registriert, als der
  Platzhaltertext gesetzt wurde — er rief `_refresh_groups()` auf, obwohl der
  Gruppen-Baum erst danach entstand. Der Beobachter wird nun erst hinter dem
  Gruppen-Baum registriert. Sichtbar war der Fehler nur auf der Konsole (Tk fängt ihn
  ab), das Suchfeld selbst funktionierte.

## 26.07.11b1 — 2026-07-11

- **Update-Suche im Firmware-Dialog.** Der Dialog kann die ausgewählten Modelle jetzt
  online abgleichen: Knopf *Nach Updates suchen* zeigt je Modellzeile die verfügbare
  Version (Spalte „Verfügbar (online)"), *Update herunterladen und zuweisen* lädt die
  passende `.bin` mit Fortschrittsanzeige herunter und trägt sie als Firmware-Datei des
  Modells ein — der bisherige Upload-Weg (parallel, Reboot-Erkennung, factory default)
  bleibt unverändert, die manuelle Dateiauswahl ebenso.
  - Quelle ist das öffentliche Firmware-Verzeichnis von Axis. Genutzt wird **`ftp.axis.com`**:
    über `www.axis.com` beantwortet Axis den `.bin`-Abruf mit einer Weiterleitung auf das
    My-Axis-Login, über `ftp.axis.com` liegt dieselbe Datei anonym per HTTPS (mit
    Range-Unterstützung, daher Fortschritt und Wiederaufnahme abgebrochener Downloads).
  - **Vorschlag bleibt in der Hauptversion der Kamera** (LTS-treu): eine Kamera auf
    10.12.x bekommt 10.12.338 vorgeschlagen, nicht den Sprung auf 12.11.72. Über
    *Version wählen…* lässt sich jede andere Version des Modells wählen (inkl. der
    neuesten). Abschaltbar in den Einstellungen.
  - Bei gemischten Ständen innerhalb einer Modellzeile ist die **neueste** Firmware der
    Zeile die Vergleichsbasis — sonst wäre der Vorschlag für die aktuellere Kamera ein
    Downgrade (eine Modellzeile bekommt genau eine Datei für alle ihre Kameras).
  - Neu in den Einstellungen (Reiter *Firmwareupdates*): Suche an/abschaltbar, LTS-Treue,
    eigenes Firmware-Verzeichnis (interner Spiegel) und *Firmware-Cache leeren*.
  - Neu im Plugin-Seam: `Capability.FIRMWARE_CHECK` mit `firmware_updates()`,
    `firmware_release()` und `download_firmware()`; die Axis-Umsetzung liegt in
    `kkm/plugins/axis/firmware_repo.py` (stdlib-only, keine neue Abhängigkeit). Ein
    Hersteller ohne diese Capability zeigt die Knöpfe schlicht nicht.
- **AppImage: HTTPS ins Internet funktioniert wieder.** Das selbst gebaute OpenSSL bringt
  keinen Zertifikatsspeicher mit (`cafile = None`) — für die Kameras egal (ungeprüftes SSL
  wegen selbstsignierter Zertifikate), aber jede Verbindung ins Internet scheiterte daran.
  Das `AppRun` setzt nun `SSL_CERT_FILE`/`SSL_CERT_DIR` auf den CA-Speicher des Systems;
  zusätzlich sucht die Update-Suche selbst die üblichen Pfade. Ohne CA-Speicher bricht sie
  mit klarer Meldung ab, statt die Zertifikatsprüfung stillschweigend abzuschalten — die
  heruntergeladene Datei wird schließlich auf die Kamera geschrieben.

## 26.07.11 — 2026-07-11

- **Neues Programm-Icon.** Statt der Bullet-Kamera mit gelbem Zahnrad nun ein weißes,
  stilisiertes Zahnrad auf dem bisherigen blauen Verlaufshintergrund; im Innenloch des
  Zahnrads sitzt eine Kameralinse (dunkler Fassungsring, blaue Iris mit Radialverlauf,
  Pupille und Glanzlichter). Die Silhouette bleibt bis 16 px lesbar. `assets/`-PNG
  (1024×1024) und Windows-`.ico` (16–256) neu erzeugt; AppImage- und Windows-Build
  nutzen sie unverändert automatisch.

## 26.07.05b7 — 2026-07-05

- **Meldungsfenster erscheinen jetzt zuverlässig im Vordergrund.** Hinweis- und
  Fehlerdialoge (z. B. „Bitte zuerst eine .cfg-Datei wählen" beim Klick auf
  *Importieren* ohne Dateiauswahl) konnten hinter dem gerade offenen Dialog bzw.
  dem Hauptfenster landen — unsichtbar, aber blockierend (modal). Ursache: den
  `messagebox`-Aufrufen fehlte das Elternfenster, sodass Tk sie ans Wurzelfenster
  statt an den aktiven Dialog hängte. Allen 24 betroffenen Aufrufen (in den
  Aktions-Dialogen und im Hauptfenster) wird nun `parent=` mitgegeben; die Meldung
  erscheint dadurch immer über dem auslösenden Fenster.

## 26.07.05b6 — 2026-07-05

- **Korrektur: Die Windows-`.exe` hat weiterhin Tcl/Tk 8.6, nicht Tk 9.** Die in
  26.07.05b4 getroffene Annahme war falsch — der python.org-**Windows**-Installer
  von Python 3.14 bündelt weiterhin **Tcl/Tk 8.6.15** (CPythons
  `PCbuild/get_externals.bat` pinnt für Windows `tk-8.6.15.0`); nur der *macOS*-
  Installer wurde ab 3.14.5 auf Tk 9.0 umgestellt. Da PyInstaller die Tk-Version
  des bauenden Interpreters übernimmt, bleibt die `.exe` bei Tk 8.6. Tk 9 gibt es
  daher **nur** in der Linux-AppImage (die Tcl/Tk 9 selbst kompiliert). Python 3.14
  bleibt auf Windows — zur Konsistenz der Python-Version mit der AppImage; der
  Dunkelmodus (`sv-ttk`) läuft auf Tk 8.6 unverändert. Die irreführenden Angaben in
  `build_windows.ps1`, `BUILD_WINDOWS.md`, `README.md` und `CLAUDE.md` wurden
  berichtigt. Keine Funktions- oder Code-Änderung.

## 26.07.05b5 — 2026-07-05

- **Linux-AppImage jetzt ebenfalls auf Python 3.14** (vorher 3.13) — zur
  Vereinheitlichung mit der Windows-`.exe`. Tk 9 hatte die AppImage schon (Python
  wird gegen selbst kompiliertes Tcl/Tk 9.0.4 gebaut), daher rein interner
  Interpreter-Sprung: `build_appimage.sh` auf 3.14.6 gezogen, Wheel-Filter auf
  `cp314` (regulär, nicht free-threaded `cp314t`) angepasst. Funktion unverändert.

## 26.07.05b4 — 2026-07-05

> **⚠ Berichtigung (26.07.05b6):** Dieser Eintrag ist falsch. Der Windows-
> Installer von Python 3.14 bringt **kein** Tk 9 mit — die `.exe` blieb bei Tk 8.6.
> Nur der macOS-Installer wurde auf Tk 9 umgestellt. Siehe 26.07.05b6.

- **Windows-`.exe` wird jetzt mit Tcl/Tk 9 gebaut** (bisher Tk 8.6). Der Build läuft
  dafür auf **Python 3.14**, dessen Windows-Installer Tcl/Tk 9.0 mitbringt —
  PyInstaller übernimmt die Tk-Version des bauenden Interpreters. Damit hat die
  `.exe` dieselbe Tk-9-Oberfläche wie die Linux-AppImage (im „Über"-Tab sichtbar).
  `build_windows.ps1`/`BUILD_WINDOWS.md` auf `py -3.14` umgestellt; benötigt eine
  aktuelle PyInstaller-Version (≥ 6.10, Tk-9-fähig). Linux-AppImage unverändert.

## 26.07.05b3 — 2026-07-05

- **Konfigurations-Export kann jetzt auch die Bewegungserkennung (VMD4)
  mitschreiben** — analog zu den Stream-Profilen. Das Auslesen holt die
  VMD4-Konfiguration per `getConfiguration` (ohne die App zu starten); im
  Parameter-Auswahlfenster gibt es die Option „Bewegungserkennung (VMD4) mit
  exportieren" (ausgegraut, wenn die Kamera keine aktive VMD4 hat). Die `.cfg`
  erhält denselben `<Vmd4>`-Block wie ein AXIS-Device-Manager-Export und lässt sich
  1:1 wieder importieren. Round-trip gegen eine echte P3265-V verifiziert.

## 26.07.05b2 — 2026-07-05

- **VMD4-Import: gestoppte VMD-Anwendung wird automatisch gestartet.** Eine
  gestoppte VMD-App antwortet an ihrem `control.cgi` mit einem generischen
  „HTTP-Fehler 500" — der Import startet sie deshalb vorab (`applications/
  control.cgi?action=start&package=vmd`) und wartet, bis die Steuer-API bereit ist.
  Gegen eine echte P3265-V (AXIS OS 12.10) verifiziert. Zusätzlich: die
  Versionsaushandlung sendet jetzt korrekt ein `apiVersion`-Feld (sonst Fehler
  2003), und HTTP-Fehler der JSON-APIs zeigen jetzt den Antwort-Body der Kamera mit.

## 26.07.05b1 — 2026-07-05

- **Konfigurations-Import versteht jetzt Bewegungserkennung (VMD4).** ADM-`.cfg`-
  Dateien mit einem `<Vmd4>`-Block (Motion Detection, kein `param.cgi`-Parameter,
  sondern JSON) werden erkannt und über die VMD4-App-Schnittstelle
  (`POST /local/vmd/control.cgi`, `setConfiguration`) mitangewendet. Die API-Version
  wird pro Kamera ausgehandelt (`getSupportedVersions`), damit ältere und neuere
  Firmware funktionieren. In der Dateiinfo wird „Bewegungserkennung (VMD4)"
  angezeigt; der Import-Log meldet Erfolg/Fehlschlag separat. Bestehende `.cfg`
  (nur Parameter/Stream-Profile) verhalten sich unverändert.

## 26.07.05 — 2026-07-05

- **Windows (portable `.exe`): Konfiguration liegt jetzt neben der ausführbaren
  Datei** im Ordner `kamera_konfigurationsmanager` statt in `%APPDATA%`. Damit ist
  die Konfiguration (Gruppen, Einstellungen, Passwort-Tresor) mitnehmbar (z. B. auf
  einem USB-Stick). Gilt nur für die gebündelte `.exe`; aus dem Quellcode gestartet
  bleibt `%APPDATA%`. Die Linux-AppImage ist unverändert (weiterhin `~/.config`).

- **Parameter-Auswahl: Umschalter „Nur Ausgewählte anzeigen"** (neben „Alle"/„Keine")
  blendet die Liste auf die aktuell ausgewählten Parameter ein — praktisch, um vor
  dem Speichern die Auswahl zu überprüfen. Wird zusammen mit dem Textfilter
  angewandt.

## 26.07.04b5 — 2026-07-04

- **Parameter-Auswahl beim Konfigurations-Export zeigt jetzt die Anzahl** der aktuell
  ausgewählten Parameter unten an („Ausgewählt: N von M Parametern") — aktualisiert
  sich live beim An-/Abwählen sowie über „Alle"/„Keine".

## 26.07.04b4 — 2026-07-04

- **Konfigurations-Import: schreibgeschützte `Properties.*`-Parameter werden
  übersprungen.** AXIS-Device-Manager-Exporte schreiben die Read-only-Gruppe
  `Properties.*` (Geräte-Eigenschaften) mit. Wurde sie an `param.cgi?action=update`
  gesendet, wies die Kamera (AXIS OS 12) den **gesamten** Batch mit HTTP 401
  („Authentifizierung fehlgeschlagen") ab — dadurch schlug z. B. eine Overlay-
  Vorlage komplett fehl, obwohl nur die 2 `Properties.*`-Einträge das Problem waren.
  `apply_parameters` filtert diese Gruppe jetzt vor dem Anwenden heraus (gegen eine
  echte P3265-V verifiziert: vorher 401, jetzt „10 Parameter angewendet").

## 26.07.04b3 — 2026-07-04

- **Option „Beim Start maximiert öffnen"** (Einstellungen → Darstellung): Ist sie
  aktiv, öffnet das Hauptfenster beim nächsten Start bildschirmfüllend
  (plattformübergreifend: `zoomed` unter Windows/macOS, `-zoomed` unter Linux/X11,
  sonst Bildschirmgröße als Fallback). Standardmäßig aus.

## 26.07.04b2 — 2026-07-04

- **Button „Suchen" heißt jetzt „Suchen/aktualisieren"** — verdeutlicht, dass die
  Aktion auch bereits bekannte Kameras neu einliest/aktualisiert. HILFE angepasst.

## 26.07.04b1 — 2026-07-04

- **Tcl/Tk auf 9.0.4 aktualisiert** (AppImage-Build, vorher 9.0.3). Reine
  Wartungs-Aktualisierung der gebündelten GUI-Bibliothek; `THIRD_PARTY_LICENSES.md`
  entsprechend gepflegt. (Windows nutzt das System-Tcl/Tk und ist nicht betroffen.)

## 26.07.04 — 2026-07-04

- **Neuer Reiter „Über" in den Einstellungen**: zeigt die Programmversion, die
  Versionen der verwendeten Komponenten (Python, Tcl/Tk, `zeroconf`,
  `cryptography`, `sv-ttk` — zur Laufzeit ermittelt), den Ersteller (Mirik) und die
  Lizenz (GPL-3.0-or-later) sowie den Hinweis, dass das Programm mit Unterstützung
  von künstlicher Intelligenz entwickelt wurde.

## 26.07.03b20 — 2026-07-03

- **Windows: Dunkelmodus repariert (Build)**: Das Windows-Build-Skript
  (`build_windows.ps1`) installierte **`sv-ttk` nicht** — dadurch fehlte das
  Sun-Valley-Theme in der `.exe` und die App blieb beim hellen Standard-Theme
  („Dunkel" bewirkte nichts). Das Skript installiert die Laufzeit-Abhängigkeiten
  jetzt vollständig via `requirements.txt` (inkl. `sv-ttk`); `BUILD_WINDOWS.md`
  entsprechend korrigiert. Zum Beheben die `.exe` mit dem aktualisierten Skript
  neu bauen. (Kein App-Code betroffen; die Linux-AppImage war nie betroffen.)

## 26.07.03b19 — 2026-07-03

- **Nativer System-Dateidialog**: Datei öffnen/speichern nutzt jetzt – sofern
  vorhanden – den **System-Dateidialog** (`zenity` für GTK/GNOME, `kdialog` für
  KDE) statt des größenspringenden Tk-Dialogs. Beim Start aus dem AppImage wird die
  gebündelte `LD_LIBRARY_PATH`/`PYTHON*`-Umgebung entfernt, damit das
  System-Werkzeug seine eigenen Bibliotheken lädt. Ist kein solches Werkzeug da
  (bzw. unter Windows/macOS, wo Tk ohnehin nativ ist), wird wie zuvor der
  Tk-Dialog mit fixierter Größe verwendet. `filetypes` werden auf die jeweilige
  Filter-Syntax abgebildet, `defaultextension` beim Speichern ergänzt.

## 26.07.03b18 — 2026-07-03

- **Datei-Dialog: feste Größe**: Der (unter Linux nicht-native) Tk-Dateidialog
  passte seine Größe an den Ordnerpfad an und sprang dadurch beim Öffnen. Neue
  dünne Wrapper (`kkm/gui/filedialogs.py`) erzwingen beim Erscheinen eine feste
  Standardgröße (780×520). Alle Öffnen/Speichern-Dialoge nutzen sie jetzt. Auf
  Plattformen mit nativem Dialog (Windows/macOS) ist es ein No-op.

## 26.07.03b17 — 2026-07-03

- **Firmware-Dialog: aktuelle Version + aufklappbare Kameras + grüne Erfolge**: Die
  Modell-Tabelle hat jetzt eine Spalte **„Aktuelle Firmware"** und lässt sich pro
  Modellzeile **aufklappen**, sodass die einzelnen Kameras (Name, IP, aktuelle
  Firmware) sichtbar werden. Bei erfolgreichem Update wird die jeweilige
  Kamerazeile **grün** und ihre Version auf die neue aktualisiert; die Modellzeile
  wird grün, sobald alle ihre Kameras fertig sind. Die Rückmeldung erfolgt live —
  auch im Parallelbetrieb — über eine thread-sichere Erfolgs-Queue.

## 26.07.03b16 — 2026-07-03

- **Firmware-Updates parallel**: Neuer Einstellungen-Reiter **„Firmwareupdates"**
  mit Schalter „Firmware-Updates parallel ausführen" (+ „Maximal gleichzeitig").
  Ist er aktiv (Standard), werden mehrere markierte Kameras gleichzeitig
  aktualisiert statt nacheinander — gerade weil jetzt bei jeder Kamera auf den
  Neustart gewartet wird, verkürzt das Sammel-Updates erheblich. `run_per_camera`
  unterstützt dafür einen gedeckelten Thread-Pool (`parallel`/`max_workers`); der
  Firmware-Dialog liest die Einstellung. Andere Aktionen bleiben sequenziell. Neue
  Settings-Schlüssel `firmware_parallel` / `firmware_max_parallel`.

## 26.07.03b15 — 2026-07-03

- **Firmware-Update: verfrühte Erfolgsmeldung bei alter Firmware behoben** (z. B.
  AXIS M7001): Dort bleibt die Kamera nach dem Upload zunächst erreichbar (alte
  Firmware) und startet erst danach neu — die bisherige Poll-Logik meldete deshalb
  sofort „Erfolg". Jetzt wird auf den **kompletten Reboot-Zyklus** gewartet: fertig
  ist es erst, wenn die Kamera zwischendurch **offline** war und wieder antwortet,
  oder wenn sich die **Firmware-Version geändert** hat (Fallback, falls das Gerät
  intern durchbootet). Erst dann kommt die Erfolgsmeldung mit der neuen Version.
  Gegen die echte M7001 (device_info liest `5.20.5` korrekt) abgesichert;
  Zustandslogik per Simulation verifiziert.

## 26.07.03b14 — 2026-07-03

- **Firmware-Update: Rückmeldung erst nach Erreichbarkeit + Versions-Update**:
  Nach dem Aufspielen wartet der Firmware-Dialog jetzt, bis die Kamera neu
  gestartet und wieder erreichbar ist, liest die **neue Firmware-Version** aus und
  meldet erst dann den Erfolg; die Version wird automatisch in der Geräteliste
  aktualisiert (`MainWindow.apply_firmware_update`). Mit Option *factory default*
  kommt die Kamera werksneu zurück und wird als „Ersteinrichtung erforderlich"
  markiert (wie beim Werksreset). Gemeinsamer Poll-Helfer `ActionDialog.poll_until`
  (auch vom Werksreset genutzt).

## 26.07.03b13 — 2026-07-03

- **Werksreset: Rückmeldung erst nach Erreichbarkeit + Listen-Update**: Beim
  Werksreset *mit Erhalt der IP* wartet das Programm jetzt, bis die Kamera neu
  gestartet und wieder erreichbar **und** im Werkszustand ist (Polling über
  `is_unconfigured`), und meldet den Erfolg erst dann. Anschließend wird die
  Kamera in der Liste als „Ersteinrichtung erforderlich" markiert und ihre nun
  ungültigen Zugangsdaten (Tresor + Sitzungs-Cache) werden verworfen — damit eine
  spätere Suche sie korrekt als werksneu erkennt. Beim kompletten Reset (IP ändert
  sich) folgt ein Hinweis, per Suche neu zu finden. Neuer Hook
  `MainWindow.after_factory_reset`.

## 26.07.03b12 — 2026-07-03

- **Werksreset im Konfigurations-Dialog**: Neuer Bereich „Werkseinstellungen" mit
  Auswahl zwischen **Werksreset mit Erhalt der IP-Adresse**
  (`factorydefault.cgi` — Netzwerk/IP bleiben) und **komplettem Werksreset**
  (`hardfactorydefault.cgi` — inkl. IP). Sicherheitsabfrage; wirkt auf alle
  markierten Kameras. Neue Capability `FACTORY_RESET` (Abschnitt erscheint nur,
  wenn das Plugin ihn unterstützt), Plugin-Methode `factory_reset` und
  `vapix.factory_default` (prüft erst die Zugangsdaten, wertet den
  reboot-bedingten Verbindungsabbruch als Erfolg).

## 26.07.03b11 — 2026-07-03

- **Aktionen im Rechtsklick-Menü**: Die fünf Vorderansicht-Aktionen (IP-Adresse,
  Benutzer, ONVIF-Benutzer, Firmware, Konfiguration) sind jetzt zusätzlich zur
  Toolbar auch im Kontextmenü der Geräteliste erreichbar und wirken auf die
  markierten Kameras. Aktionsliste als gemeinsame Konstante `ACTION_ITEMS`.

## 26.07.03b10 — 2026-07-03

- **Reiter umbenannt**: Der Einstellungen-Reiter *Import* heißt jetzt
  *Import und Sicherung* (er enthält neben dem AXIS-Import auch Export/Restore
  der Sicherung).

## 26.07.03b9 — 2026-07-03

- **Backup-Kompression auf zlib umgestellt**: Der gebündelte AppImage-Interpreter
  enthält kein `_lzma`-Modul — die Sicherung nutzt daher `zlib` (Deflate) statt
  LZMA. Für die JSON-Daten praktisch gleichwertig, und im Bundle garantiert
  vorhanden (verifiziert). Format-/Feature-Verhalten sonst unverändert.

## 26.07.03b8 — 2026-07-03

- **Sicherung & Wiederherstellung (Backup)**: Neuer Bereich im Einstellungen-Reiter
  *Import*. **Export** bündelt Gruppen/Geräte (`groups.json`), Einstellungen
  (`settings.json`) und den Passwort-Tresor (`vault.enc`) in **eine**
  verschlüsselte Datei (`.kkmbackup`): tar → LZMA → AES-256-GCM mit einem
  abgefragten **Backup-Passwort** (PBKDF2-Schlüsselableitung). **Wiederherstellen**
  spielt die Datei zurück und ersetzt die aktuellen Daten; die In-Memory-Objekte
  werden neu geladen (kein versehentliches Überschreiben), der Tresor gesperrt und
  ein veraltetes Auto-Entsperr-Token entfernt. Nur Standardbibliothek + das schon
  vorhandene `cryptography` — **keine** neue Abhängigkeit, identisch unter
  Linux/Windows. (Bewusst kein echtes `.7z`-Format, um den schlanken Build ohne
  Zusatzpakete/Binaries zu erhalten.) Neues Modul `kkm/core/backup.py`.

## 26.07.03b7 — 2026-07-03

- **Werkszustand auch bei alter Firmware erkennen** (z. B. AXIS M7001): Diese
  Geräte verlangen auch werksneu eine Authentifizierung (normaler 401, kein
  `axis-setup`), sind aber noch mit den Werks-Standard-Zugangsdaten `root/pass`
  erreichbar. `vapix.is_unconfigured` prüft daher bei einem normalen 401 zusätzlich,
  ob der Standard-Login noch funktioniert, und stuft das Gerät dann als werksneu
  ein („Ersteinrichtung erforderlich"). Gegen eine echte M7001 **und** eine
  P3265-V verifiziert; konfigurierte Geräte (Standard-Login abgelehnt) → weiterhin
  normale Passwortabfrage.

## 26.07.03b6 — 2026-07-03

- **Werkszustands-Erkennung für AXIS OS 10/11 korrigiert**: Neuere Geräte (z. B.
  AXIS P3265-V) verlangen auch werksneu eine Authentifizierung, `pwdgrp.cgi`
  antwortet also mit 401 statt 200 — die bisherige Erkennung (b5) schlug dort fehl.
  `vapix.is_unconfigured` wertet jetzt zusätzlich den Antwort-Header
  `axis-setup` bzw. den Body-Hinweis „initial admin user must be created" aus und
  erkennt so den Ersteinrichtungs-Zustand zuverlässig (gegen eine echte P3265-V
  verifiziert). Der 200-Fall älterer Firmware bleibt erhalten.

## 26.07.03b5 — 2026-07-03

- **Werksneue Kameras erkennen**: Nach einer Suche wird für jede Kamera mit
  unbekannten Zugangsdaten geprüft, ob sie sich noch im **Auslieferungszustand**
  befindet (kein Passwort gesetzt — unauthentifizierter VAPIX-Aufruf antwortet mit
  200 statt 401). Solche Kameras werden **nicht** nach einem Passwort gefragt;
  stattdessen erscheint in der Spalte **Firmware** der Hinweis
  **„Ersteinrichtung erforderlich"**. Nur die restlichen unbekannten Kameras
  lösen weiterhin die Passwortabfrage aus. Neue Plugin-Methode
  `VendorPlugin.is_unconfigured()` (Axis nutzt das vorhandene
  `vapix.is_unconfigured`).

## 26.07.03b4 — 2026-07-03

- **Neue Sondergruppe „Ohne Gruppe"**: Zweite dauerhafte, nicht löschbare Gruppe
  (unter „Alle Kameras"), die alle bekannten Kameras zeigt, die noch **keiner
  Benutzergruppe** zugeordnet sind — z. B. bei einer Suche neu gefundene. Sobald
  eine Kamera einer Gruppe zugewiesen wird, verschwindet sie automatisch aus
  „Ohne Gruppe". Die Mitgliedschaft wird dynamisch aus Roster + Zuordnungen
  berechnet (nicht gespeichert). Sie ist kein Zuordnungsziel und wird von der
  Gruppensuche nicht ausgeblendet. Neue Kern-Konstanten `UNGROUPED_ID` /
  `VIRTUAL_GROUP_IDS`.

## 26.07.03b3 — 2026-07-03

- **IP-Umstellung aktualisiert die Liste**: Wird über die Aktion *IP-Adresse* eine
  **feste IP** gesetzt, übernimmt die Geräteliste im Erfolgsfall die neue Adresse
  sofort (pro Kamera, nur für erfolgreich umgestellte). Hat die Kamera keine
  MAC/Seriennummer, wird ihr Identitätsschlüssel (Name@IP) in Roster, Gruppen,
  Sitzungs-Cache und Tresor mitgezogen. DHCP-Umstellungen ändern die Anzeige
  nicht, da die neue Adresse vom DHCP-Server vergeben und hier nicht bekannt ist.
  Neue Kern-Methode `GroupStore.rekey_camera()`.

## 26.07.03b2 — 2026-07-03

- **Platzhalter im Gruppen-Suchfeld**: Das Suchfeld zeigt jetzt den grauen
  Hinweistext „Suche", der beim Hineinklicken/Tippen verschwindet und bei leerem
  Feld wieder erscheint.

## 26.07.03b1 — 2026-07-03

- **Suche in der Gruppenliste**: Rechts neben der Überschrift *Gerätegruppen*
  gibt es jetzt ein Suchfeld. Während der Eingabe wird die Gruppenliste live auf
  Gruppen gefiltert, deren Name den Suchtext enthält (case-insensitiv).
  „Alle Kameras" bleibt immer sichtbar; ein leeres Feld zeigt wieder alle Gruppen.

## 26.07.03 — 2026-07-03

- **Gruppenliste alphabetisch**: Die eigenen Gerätegruppen links werden jetzt
  alphabetisch (case-insensitiv) sortiert angezeigt statt in Anlage-Reihenfolge.
  „Alle Kameras" bleibt fest an erster Stelle.

## 26.07.02b5 — 2026-07-02

- **Import aus AXIS Device Manager**: Neuer Reiter *Import* in den Einstellungen
  übernimmt Geräte **und** Gruppen aus einer Export-Datei des AXIS Device Manager
  (JSON). Beide Dateiformate werden erkannt: **1.x** (normalisiert: `deviceTag` +
  `deviceTagRelation`) und **2.x** (Gerätе-IDs direkt im Tag). Geräte werden
  anhand ihrer MAC/Seriennummer in den Roster zusammengeführt (verschmelzen später
  automatisch mit per Suche gefundenen), Gruppen gleichen Namens werden ergänzt
  statt dupliziert. Enthaltene Zugangsdaten kommen optional in den Tresor — in
  Format 2.x sind die Passwörter base64-kodiert und werden beim Import dekodiert.
  Verschlüsselte Exporte werden abgewiesen. Neue Kern-Methode
  `PasswordVault.set_many()` schreibt viele Zugangsdaten in einem Vorgang.

## 26.07.02b4 — 2026-07-02

- **Gruppenliste-Scrollbalken korrekt gemessen**: In b3 erschien der horizontale
  Balken bei langen Gruppennamen oft trotzdem nicht — die Spaltenbreite wurde mit
  `TkDefaultFont` statt der tatsächlichen (größeren) sv_ttk-Treeview-Schrift
  gemessen und dadurch unterschätzt. Die stretch-Spalte dehnte sich dann nur bis
  zur Panelbreite und klemmte den Text ab, ohne überzulaufen. Jetzt wird mit der
  echten Schrift (Tcl `font measure`) gemessen, sodass der Balken zuverlässig
  erscheint und der volle Name lesbar wird.

## 26.07.02b3 — 2026-07-02

- **Horizontaler Scrollbalken der Gruppenliste** funktioniert jetzt: Die
  Baumspalte (`#0`) füllte bisher nur die Panelbreite und klemmte lange
  Gruppennamen einfach ab (kein Überlauf → kein Scrollbalken). Ihre `minwidth`
  wird nun bei jedem Aktualisieren an den **längsten Gruppennamen** angepasst;
  ist das Panel schmaler, erscheint der Auto-Hide-H-Balken und man kann den
  Namen vollständig lesen.

## 26.07.02b2 — 2026-07-02

- **Mindestbreite der Gruppenspalte**: Der Trenner zwischen Gruppen- und
  Kameraliste lässt sich nicht mehr so weit nach links ziehen, dass die drei
  Gruppen-Buttons („+ Gruppe", „Umbenennen", „Löschen") abgeschnitten werden.
  Die Mindestbreite wird zur Laufzeit aus der Wunschbreite der Button-Zeile
  abgeleitet (`ttk.PanedWindow` kennt keine Pro-Pane-minsize → Sash-Position
  wird geklemmt).

## 26.07.02b1 — 2026-07-02

- **Scrollbalken für Gruppen- und Kameraliste**: Beide Listen bekommen
  auto-versteckende Scrollbalken (vertikal + horizontal). Der horizontale Balken
  erscheint, sobald die Fensterbreite nicht für alle Spalten reicht — die
  Tabellenspalten quetschen sich dank `minwidth` nicht mehr unleserlich zusammen,
  sondern lassen sich seitwärts scrollen. Ist genug Platz, bleiben die Balken
  unsichtbar.

## 26.07.02 — 2026-07-02

- **Sortierbare Tabellenspalten**: Ein Klick auf einen Spaltenkopf sortiert die
  Geräteliste nach dieser Spalte aufsteigend, ein erneuter Klick absteigend; ein
  Pfeil (▲/▼) markiert die aktive Spalte und Richtung. Die Sortierung ist
  **natürlich** — IP-Adressen (`.9` vor `.10`), Firmware-Versionen
  (`5.20.5` vor `11.9.61`) und Namen mit Zahlen ordnen sich sinnvoll; leere
  Werte / „—" wandern ans Ende.

## 26.07.01b12 — 2026-07-01

- **Firmware/Modell alter Kameras jetzt korrekt (root.-Präfix)**: Ältere AXIS-
  Firmware (z. B. M7001, OS 5.x) liefert param.cgi-Werte **ohne** `root.`-Präfix
  (`Properties.Firmware.Version=5.20.5`), neuere **mit**. Die Auswertung
  (`_param_value`) akzeptiert nun beide Formen — betrifft Geräteinfo (Firmware/
  Modell/Serie) und den Konfig-Export. Damit erscheint auch die M7001-Firmware.

## 26.07.01b11 — 2026-07-01

- **Firmware-Auslesen für ältere Kameras (z. B. M7001, AXIS OS 5.x)**: Manche alte
  Firmware beantwortet die kombinierte param.cgi-Gruppenabfrage gar nicht (und hat
  `basicdeviceinfo.cgi` noch nicht). Firmware/Modell werden jetzt als weiterer
  Fallback über **Einzelgruppen-Abfragen** (`group=Properties.Firmware.Version`
  bzw. `Brand.ProdShortName`) nachgelesen.

## 26.07.01b10 — 2026-07-01

- **Firmware-Auslesen robuster (basicdeviceinfo.cgi)**: Wenn `param.cgi` keine
  Firmware liefert (neuere AXIS OS geben teils leere Werte oder eine
  `# Error`-Antwort mit HTTP 200 zurück — Verbindung „ok", aber Spalte leer), wird
  Firmware/Modell ergänzend über den JSON-Endpunkt `basicdeviceinfo.cgi`
  (`getAllProperties` → `Version`/`ProdShortName`) gelesen. Das 401-Verhalten für
  die Zugangsdaten-Prüfung bleibt erhalten.
- **Genauere Statusmeldung**: „Firmware gelesen: X, Y ohne Firmware-Wert, Z
  fehlgeschlagen" — unterscheidet jetzt „verbunden, aber kein Firmware-Wert" von
  echten Fehlern.

## 26.07.01b9 — 2026-07-01

- **Firmware/Modell bleiben über Suchen erhalten**: `remember()` überschrieb bei
  jeder Suche den Roster-Eintrag komplett und löschte damit die per VAPIX
  gelesene Firmware/Modell. Diese Felder werden jetzt erhalten, wenn die neue
  mDNS-Fassung sie nicht mitbringt (eine neue, tatsächlich gelesene Version
  gewinnt weiterhin).
- **Rückmeldung beim Auslesen**: Nach der Suche zeigt die Statuszeile, für wie
  viele Kameras Firmware/Modell gelesen wurde bzw. fehlschlug (statt Lesefehler
  still zu verschlucken) — hilft, Zugangsdaten-/Erreichbarkeitsprobleme zu erkennen.

## 26.07.01b8 — 2026-07-01

- **Tresor-Schnellschalter in der Aktionsleiste**: rechts neben „Einstellungen" ein
  Schloss-Button — **🔒** wenn der Tresor gesperrt ist, **🔓** wenn entsperrt. Ein
  Klick schaltet um (entsperren mit Master-Passwort bzw. sperren); das Symbol folgt
  dem Tresor-Status automatisch. Das Schloss-Symbol ist vergrößert dargestellt.
- **Tresor beim Programmstart automatisch entsperren** (optional): Neues Häkchen
  im Einstellungen → Tresor. Beim Aktivieren wird das Master-Passwort einmal
  abgefragt und gerätegebunden verschlüsselt hinterlegt (`vault.auto`, an Rechner
  + Benutzerkonto gebunden, funktioniert nicht auf fremden Geräten); danach wird
  der Tresor bei jedem Start automatisch entsperrt. Deutlicher Sicherheitshinweis
  im Dialog; Häkchen entfernen löscht das Token. Master-Passwort-Änderung zieht
  das Token automatisch nach.
- **Passworteingabe in den Aktionsdialogen optional (Tresor zuerst)**: Neues
  Häkchen **„Zugangsdaten aus Tresor verwenden"** (standardmäßig an, sobald ein
  Tresor existiert) in IP-, Benutzer-, ONVIF-, Firmware- und Konfigurations-Dialog.
  Ist es gesetzt, werden je Kamera **zuerst** Benutzer und Passwort aus dem Tresor
  genutzt; die Felder oben sind ausgegraut und dienen nur als Rückfall. Ist der
  Tresor beim Aktionsstart noch gesperrt, wird angeboten, ihn zu entsperren. So
  entfällt die Passworteingabe, wenn das Passwort im Tresor liegt.

## 26.07.01 — 2026-07-01

- **Kamera im Browser öffnen**: Doppelklick auf einen Tabelleneintrag öffnet die
  Weboberfläche der Kamera (`http://<IP>`) im Standard-Browser; zusätzlich neuer
  Eintrag **„Kamera öffnen"** im Rechtsklick-Kontextmenü (bei einzelner Auswahl).

## 26.06.30b7 — 2026-06-30

- **Fehler behoben: „Online prüfen" zeigte alle Kameras als online.** Die Prüfung
  ignorierte das Ergebnis und nutzte zudem `is_unconfigured`, das nicht zwischen
  „konfiguriert" und „nicht erreichbar" unterscheidet. Neue echte Erreichbarkeits-
  prüfung `is_online` (jede HTTP-Antwort inkl. 401 = online; nur Verbindungs-/
  Timeout-Fehler = offline); `check_online` liefert nun den echten Status.
- **Modernes Design (Sun Valley) mit Hell/Dunkel**: zeitgemäßes, flaches
  Erscheinungsbild über das gebündelte `sv-ttk`-Theme; Standard **Dunkel**.
  Umschaltung unter Einstellungen → Darstellung (wirkt sofort, wird gespeichert).
  Status- und Warnfarben passen sich dem Theme an.

## 26.06.30b6 — 2026-06-30

- **Tresor bei Bedarf einrichten**: Wenn Passwörter gespeichert werden sollen (per
  Häkchen in den Aktionsdialogen oder bei der Zugangsdaten-Abfrage nach der Suche),
  der Tresor aber noch gesperrt/nicht angelegt ist, wird jetzt angeboten, ihn
  anzulegen bzw. zu entsperren. Lehnt man ab, werden die Zugangsdaten nur für die
  laufende Sitzung gemerkt (klarer Hinweis statt stillem Verwerfen). Gemeinsamer
  Helfer `ensure_vault_unlocked`; `_maybe_store` zentral in der Dialog-Basis.

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
- **Performance (große Bestände, ~1000 Kameras)**:
  - Reverse-Index im `GroupStore` → `groups_of`/Tabellenaufbau statt O(N×Gruppen×
    Mitglieder) jetzt praktisch O(1) je Kamera.
  - Batch-Löschen (`forget_many`, `vault.delete_many`) → ein Speichervorgang statt
    einer pro Kamera.
  - Firmware-Auslesen, Online-Prüfung und Zugangsdaten-Test laufen parallel über
    einen Thread-Pool (12) statt sequenziell.

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
