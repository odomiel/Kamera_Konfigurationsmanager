# Änderungsverlauf

Versionsschema: `JJ.MM.TT[bN]` (zweistelliges Jahr; mehrere Releases am selben Tag
erhalten ein hochzählendes `bN`-Suffix). Die aktuelle Version steht in
`kkm/version.py`.

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
