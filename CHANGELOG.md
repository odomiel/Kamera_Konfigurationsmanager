# Änderungsverlauf

Versionsschema: `JJ.MM.TT[bN]` (zweistelliges Jahr; mehrere Releases am selben Tag
erhalten ein hochzählendes `bN`-Suffix). Die aktuelle Version steht in
`kkm/version.py`.

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
