# Änderungsverlauf

Versionsschema: `JJ.MM.TT[bN]` (zweistelliges Jahr; mehrere Releases am selben Tag
erhalten ein hochzählendes `bN`-Suffix). Die aktuelle Version steht in
`kkm/version.py`.

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
