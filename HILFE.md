# Hilfe — Kamera_Konfigurationsmanager

Diese Hilfe beschreibt alle Funktionen des Programms. Sie ist auch im Programm
über den Button **„Hilfe"** (oben rechts) erreichbar.

Das Programm verwaltet und konfiguriert Netzwerkkameras — **ohne** Live-Bild.
Aktionen wirken immer auf die in der Geräteliste **markierten** Kameras und laufen im
Hintergrund; das Ergebnis je Kamera wird protokolliert.

Unterstützt werden **Axis** (voller Funktionsumfang) und über ein generisches
**ONVIF**-Plugin auch Kameras anderer Hersteller (siehe Abschnitt „Plugins: Axis und
ONVIF"). Ein ausführliches **Benutzerhandbuch** liegt als `Benutzerhandbuch.pdf` bei.

Die Oberfläche ist auf **Deutsch** und **Englisch** verfügbar (umschaltbar unter
Einstellungen → „Darstellung"; wirkt beim nächsten Programmstart). Diese Hilfe selbst
ist nur auf Deutsch verfügbar.

---

## Hauptfenster

- **Links:** die Gerätegruppen. Ganz oben die nicht löschbare Gruppe
  **„Alle Kameras"** (enthält alle bekannten Kameras), direkt darunter die ebenfalls
  dauerhafte Gruppe **„Ohne Gruppe"** (alle Kameras, die noch keiner eigenen Gruppe
  zugeordnet sind — etwa bei einer Suche neu gefundene; sie verschwinden dort
  automatisch, sobald sie einer Gruppe zugewiesen werden), darunter die eigenen
  Gruppen **alphabetisch** sortiert. Rechts neben der Überschrift **„Gerätegruppen"** ein
  **Suchfeld** (mit grauem Hinweistext „Suche", der beim Tippen verschwindet):
  Während der Eingabe wird die Liste live auf Gruppen gefiltert,
  deren Name den Suchtext enthält (case-insensitiv); „Alle Kameras" bleibt immer
  sichtbar, ein leeres Feld zeigt wieder alle Gruppen. Der Trenner zwischen linker
  und rechter Seite lässt sich verschieben, aber nicht enger als nötig, damit die
  Gruppen-Buttons lesbar bleiben.
- **Rechts:** die Geräteliste der gewählten Gruppe mit den Spalten Name, Modell,
  IP-Adresse, IPv6-Adresse, MAC/Seriennummer, Firmware, **Gruppe(n)** und
  **Status** (online). Die IPv6-Adressen werden bei der Suche miterkannt
  (mDNS-AAAA-Records bzw. ONVIF-XAddrs) und dienen der Anzeige — die Aktionen
  (IP, Benutzer, Firmware …) laufen weiterhin über IPv4.
  Ein **Klick auf einen Spaltenkopf** sortiert nach dieser Spalte (erneuter Klick
  kehrt die Richtung um; ▲/▼ zeigt die aktive Spalte). Sortiert wird „natürlich" —
  IP-Adressen und Firmware-Versionen ordnen sich zahlenrichtig.
  Reicht die Fensterbreite nicht für alle Spalten (bzw. die Höhe nicht für alle
  Zeilen), erscheint automatisch ein **Scrollbalken**; Gleiches gilt für die
  Gruppenliste links.
  **Spaltenbreiten** lassen sich durch **Ziehen an der Spaltengrenze** in der
  Kopfzeile ändern; die eingestellten Breiten bleiben über Programmstarts hinweg
  erhalten.
- **Oben:** die Aktionsleiste (siehe unten). Rechts neben **„Einstellungen"** ein
  **Schloss-Schalter**: **🔒** = Tresor gesperrt, **🔓** = entsperrt. Ein Klick
  schaltet um — entsperrt (fragt das Master-Passwort; legt bei Bedarf einen Tresor
  an) bzw. sperrt den Tresor.

Mehrere Kameras lassen sich mit **Strg**/**Umschalt** markieren.

**Kamera öffnen** — ein **Doppelklick** auf eine Kamera (oder Rechtsklick →
**„Kamera öffnen"**) öffnet ihre Weboberfläche im Standard-Browser
(`http://<IP>`).

---

## Suchen & Status

- **Suchen/aktualisieren** — durchsucht das lokale Netzwerk nach Kameras (Axis: mDNS;
  bei aktivem ONVIF-Plugin zusätzlich WS-Discovery) und nimmt sie in „Alle Kameras"
  auf. Bereits bekannte Kameras bleiben erhalten, auch wenn sie gerade offline sind.
  - Findet das **ONVIF-Plugin** eine Kamera, die ein Hersteller-Plugin (Axis) schon
    gemeldet hat, wird der ONVIF-Treffer verworfen — sonst stünde dieselbe Kamera
    zweimal in der Liste. Das spezialisierte Plugin gewinnt, weil es mehr kann.
  - **Firmware/Modell** stehen nicht im Suchergebnis und werden nach der Suche per
    Kamera-Login nachgelesen: Kameras mit bekannten Zugangsdaten (Tresor oder
    bereits in dieser Sitzung eingegeben) werden automatisch ausgelesen.
  - **Werksneue Kameras** (Auslieferungszustand — noch kein individuelles Passwort
    gesetzt bzw. noch der Werks-Standard-Login aktiv) werden nach der Suche
    automatisch erkannt und **nicht** nach einem Passwort gefragt; stattdessen
    steht in der Spalte **Firmware** der Hinweis **„Ersteinrichtung erforderlich"**.
    Erkannt werden sowohl neue Geräte (AXIS OS 10/11, „Administratorkonto anlegen")
    als auch ältere mit Werks-Standard-Zugangsdaten.
  - Für Kameras mit **unbekannten Zugangsdaten** erscheint eine **Abfrage**
    (Benutzer/Passwort). Mit der Option **„Dieses Passwort bei allen Kameras mit
    unbekannten Zugangsdaten ausprobieren"** werden die Eingaben auf alle noch
    offenen Kameras angewendet. Funktionierende Zugangsdaten werden **automatisch
    gespeichert**. Ist der Tresor dabei noch gesperrt/nicht angelegt, wird
    **angeboten, ihn jetzt einzurichten**; lehnst du ab, werden die Zugangsdaten
    nur für die laufende Sitzung gemerkt. „Überspringen" lässt eine Kamera aus,
    „Abbrechen" beendet die Abfrage.
- **Online prüfen** — prüft die markierten Kameras (oder die ganze Gruppe) sofort
  auf Erreichbarkeit; das Ergebnis erscheint in der Spalte **Status**
  (● Online / ○ Offline).
- **Status nach der Suche** — bei jeder Suche werden gefundene Kameras auf
  **online** gesetzt, bereits bekannte aber nicht mehr gefundene auf **offline**.
  In der Statusspalte ist **online grün**, **offline rot** dargestellt.
- **Automatische Online-Prüfung** — pro Gruppe einstellbar (siehe Einstellungen);
  die gerade angezeigte Gruppe wird dann im eingestellten Intervall geprüft.

---

## Gruppen

- **+ Gruppe / Umbenennen / Löschen** (links unten) — eigene Gruppen verwalten.
  „Alle Kameras" kann nicht umbenannt oder gelöscht werden.
- **Kamera einer Gruppe zuweisen** — Kamera(s) markieren, **Rechtsklick** →
  **„Zu Gruppe hinzufügen"** → Gruppe wählen oder **„Neue Gruppe…"**. Eine Kamera
  darf in mehreren Gruppen sein (additiv).
- **Aus Gruppe entfernen** — innerhalb einer eigenen Gruppe per Rechtsklick →
  **„Aus … entfernen"** (entfernt nur die Zuordnung, nicht die Kamera).
- **Kamera vollständig entfernen** — Rechtsklick → **„Kamera(s) vollständig
  entfernen"**: löscht die Kamera aus der Geräteliste und allen Gruppen sowie ihr
  gespeichertes Passwort. Bei der nächsten Suche taucht eine erreichbare Kamera
  wieder auf.

---

## Zugangsdaten (in jedem Aktionsdialog)

Jeder Aktionsdialog hat oben einen Bereich **„Zugangsdaten"**: Benutzer, Passwort,
Verbindung (auto/https/http), optionaler Port und Timeout.

- **„Zugangsdaten aus Tresor verwenden"** (Häkchen, standardmäßig **an**, sobald ein
  Tresor existiert): Für **jede** Kamera werden **zuerst** Benutzer **und** Passwort
  aus dem Passwort-Tresor genommen. Die Felder „Benutzer/Passwort" sind dann
  ausgegraut und dienen nur als **Rückfall** für Kameras, die (noch) keinen
  Tresor-Eintrag haben. Ist der Tresor beim Start der Aktion noch gesperrt, wird
  angeboten, ihn zu entsperren.
- **Häkchen entfernen**: Benutzer/Passwort werden wieder eingegeben und gelten
  einheitlich für **alle** markierten Kameras (der Tresor wird ignoriert).

So muss man das Passwort **nicht** mehr eintippen, wenn es im Tresor liegt.

---

## Aktionen (Buttons in der Aktionsleiste)

Dieselben fünf Aktionen (IP-Adresse, Benutzer, ONVIF-Benutzer, Firmware,
Konfiguration) stehen auch im **Rechtsklick-Menü** der Geräteliste bereit und
wirken dort ebenfalls auf die markierten Kameras.

### IP-Adresse
Stellt die Netzwerk-Adresse der markierten Kameras um:
- **Auf DHCP umstellen.**
- **Feste IP fortlaufend** ab einer Start-IP — die Adressen werden der Reihe nach
  vergeben (gemeinsame Subnetzmaske, optionales Gateway).
- **Pro Kamera einzeln** — je Kamera ein eigenes IP-Feld (mit aktueller IP
  vorbefüllt).

Die Ziel-Adressen werden vor der Umstellung geprüft; danach sind die Kameras ggf.
unter neuer Adresse erreichbar. Bei einer festen IP wird die **Geräteliste im
Erfolgsfall sofort auf die neue Adresse aktualisiert** (nur für erfolgreich
umgestellte Kameras). Bei DHCP bleibt die angezeigte Adresse unverändert, weil die
neue Adresse vom DHCP-Server vergeben wird und dem Programm nicht bekannt ist.

Manche Kameras (z. B. ältere Hikvision/STD-CGI) übernehmen die Umstellung erst nach
einem **Neustart** — das Programm löst ihn automatisch aus und meldet das im
Ergebnis-Protokoll.

### Benutzer
Reguläre Kamera-Benutzer verwalten:
- **Anlegen** — Name, Passwort, Rolle (administrator/operator/viewer). Option
  **Auslieferungszustand (factory)** für fabrikneue Kameras.
- **Passwort ändern** — Passwort eines bestehenden Benutzers setzen.
- **Stapel-Import** — Benutzerliste aus einer Datei (`Name,Passwort[,Rolle]`),
  wird auf alle markierten Kameras angewendet.

Option **„Passwort im Tresor speichern"** legt den Zugang verschlüsselt ab.

### ONVIF-Benutzer
Wie „Benutzer", aber für ONVIF-Konten mit den Stufen
**Administrator/Operator/User** (kein Auslieferungszustand).

### Firmware
Aktualisiert die Firmware **mehrerer Kameras verschiedener Modelle gleichzeitig**:
- je Modell eine passende `.bin`-Datei zuweisen,
- Option **Werkseinstellungen (factory default)**,
- Modelle ohne zugewiesene Datei werden übersprungen.

In der Tabelle zeigt die Spalte **„Aktuelle Firmware"** die derzeit installierte
Version. Eine **Modellzeile lässt sich aufklappen**, um die einzelnen Kameras (mit
Name, IP und aktueller Firmware) zu sehen.

**Update-Suche (nur Axis).** Der Knopf **„Nach Updates suchen"** gleicht die Modelle
mit dem öffentlichen Firmware-Verzeichnis des Herstellers ab. In der Spalte
**„Verfügbar (online)"** steht dann je Modell:

- `11.11.212 ↑` — ein Update ist verfügbar,
- `5.20.5 (aktuell)` — die Kamera ist auf dem neuesten Stand,
- `?` — das Modell wurde nicht gefunden (dann die Datei von Hand zuweisen).

**„Update herunterladen und zuweisen"** lädt die passende `.bin` mit Fortschrittsanzeige
herunter und trägt sie als Firmware-Datei des Modells ein — der Rest des Ablaufs bleibt
gleich. Der Download landet in einem Cache (in den Einstellungen löschbar); ein
abgebrochener Download wird beim nächsten Versuch fortgesetzt.

Der Vorschlag bleibt bewusst in der **Hauptversion der Kamera**: Eine Kamera auf 10.12.x
bekommt die neueste 10.12er vorgeschlagen und springt nicht ungefragt auf einen neuen
Hauptversions-Zweig. Über **„Version wählen…"** lässt sich jede andere Version des
Modells wählen (auch die neueste überhaupt). Abschaltbar in den Einstellungen.

Sind Kameras eines Modells auf **unterschiedlichen** Ständen, ist der **neueste** davon
die Vergleichsbasis — sonst wäre der Vorschlag für die aktuellere Kamera ein Downgrade
(eine Modellzeile bekommt genau eine Datei für alle ihre Kameras).

Nach dem Aufspielen **wartet** das Programm, bis die Kamera neu gestartet und wieder
erreichbar ist, meldet erst dann den Erfolg und **liest die neue Firmware-Version
aus** und aktualisiert sie in der Geräteliste. Die zugehörige Zeile im Dialog wird
bei Erfolg **grün** (die Modellzeile, sobald alle ihre Kameras fertig sind). Ist die
Option *Werkseinstellungen* gesetzt, kommt die Kamera werksneu zurück und wird als
„Ersteinrichtung erforderlich" gekennzeichnet.

Achtung: Die Firmware muss zum Modell passen; die Kameras starten danach neu.

Einige Kameras (z. B. ältere Hikvision/STD-CGI) flashen nicht sofort, sondern wenden
die hochgeladene Firmware erst beim **nächsten Neustart** an — das Programm stößt
diesen Neustart in dem Fall selbst an (sonst würde es endlos „auf den Neustart" warten).

### Konfiguration (Axis `.cfg`)
Import/Export von Axis-Device-Manager-Konfigurationsdateien (Format v1 + v2):
- **Importieren** — eine `.cfg` auf alle markierten Kameras anwenden.
  - Nach der Dateiwahl öffnet sich die **Auswahl, was übernommen werden soll**: die
    einzelnen Parameter (durchsuchbare Liste mit **„Alle"/„Keine"** und dem Umschalter
    **„Nur Ausgewählte anzeigen"**), die **Stream-Profile einzeln** und die
    **Bewegungserkennung (VMD4)**. Vorausgewählt ist alles, was die Datei enthält; eine
    Rückfrage fasst vor dem Schreiben zusammen, was auf wie viele Kameras geht.
  - Das ist selten Zierde: Eine `.cfg` enthält neben den Bildeinstellungen auch die
    **Netzwerk-, Namensserver- und Zeitserver-Parameter der Quellkamera**. Wer nur eine
    Bildeinstellung ausrollen will, filtert die Liste z. B. nach `Image.` und wählt nur
    diese Parameter aus.
  - Schreibgeschützte `Properties.*`-Parameter (Geräte-Eigenschaften, die ein
    AXIS-Device-Manager-Export mitschreibt) werden automatisch übersprungen —
    sonst würde die Kamera den kompletten Import mit „Authentifizierung
    fehlgeschlagen" (HTTP 401) ablehnen.
  - Enthält die `.cfg` eine **Bewegungserkennung (VMD4)** — der AXIS Device Manager
    legt sie als eigenen Block ab, nicht als `param.cgi`-Parameter —, wird sie über
    die VMD4-App-Schnittstelle (`/local/vmd/control.cgi`) mitangewendet. In der
    Dateiinfo erscheint dann der Hinweis „Bewegungserkennung (VMD4)". Ist die
    VMD-Anwendung auf der Kamera **gestoppt**, wird sie vor dem Anwenden
    **automatisch gestartet** (eine gestoppte App würde sonst mit „HTTP-Fehler 500"
    antworten). Voraussetzung: Die Ziel-Kamera hat die Anwendung „AXIS Video Motion
    Detection" installiert (sonst meldet der Import einen Fehler).
- **Exportieren** — Konfiguration der ersten markierten Kamera auslesen und in
  **derselben Auswahl** wie beim Import festlegen, was in die `.cfg` kommt: Parameter,
  **Stream-Profile einzeln** und **Bewegungserkennung (VMD4)**. Die VMD4-Option ist nur
  wählbar, wenn die Kamera eine aktive Bewegungserkennung hat (sonst ausgegraut);
  das Auslesen startet die VMD-App **nicht** von selbst.
- **Auf Werkseinstellungen zurücksetzen** — setzt die markierten Kameras zurück
  (sie starten danach neu). Zur Auswahl stehen:
  - **Werksreset mit Erhalt der IP-Adresse** — alle Einstellungen zurück, aber die
    Netzwerk-/IP-Konfiguration bleibt erhalten (die Kamera bleibt unter derselben
    Adresse erreichbar). Das Programm **wartet**, bis die Kamera neu gestartet und
    wieder erreichbar ist, und meldet den Erfolg erst, wenn sie sich wieder im
    **Erstkonfigurations-Modus** befindet; in der Geräteliste erscheint dann
    „Ersteinrichtung erforderlich".
  - **Kompletter Werksreset (inkl. IP-Adresse)** — auch die Netzwerkeinstellungen
    werden zurückgesetzt (die Kamera fällt auf den Auslieferungszustand/DHCP zurück).
    Da sich dabei die IP ändert, ist die Kamera anschließend über **Suchen** neu
    zu finden.

  Eine Sicherheitsabfrage muss bestätigt werden; die Aktion lässt sich nicht
  rückgängig machen. Nach dem Reset gespeicherte Zugangsdaten der Kamera werden
  verworfen (sie gelten nicht mehr).

### Konfig-Backup (Komplett-Sicherung)
Sichert bzw. spielt die **vollständige Gerätekonfiguration als Ganzes** — im Gegensatz
zur `.cfg`-Vorlage (auswählbare Parameter) ein gerätespezifisches Komplett-Abbild
(IP, Name, Ereignisregeln, Zeit, Benutzer …). Unterstützt von **Axis**, **Hikvision**,
**Dahua** und **Hanwha**.
- **Backup herunterladen (Kamera → Datei)** — liest die Sicherung der ersten markierten
  Kamera und speichert sie. Bei Axis eine **`.json`-Datei** (dieselbe, die die
  Weboberfläche liefert; ohne Passwörter), bei den anderen Herstellern ein
  verschlüsselter **`.bin`-Blob**.
- **Backup einspielen (Datei → Kamera)** — überträgt eine Sicherungsdatei; die Kamera
  startet danach neu. Weil ein Backup gerätespezifische Daten (IP, Name) enthält, führt
  dasselbe File auf mehreren Kameras zu Adress-/Identitätskonflikten — der Dialog warnt.
  - **Axis** benötigt AXIS OS 11.8 oder neuer (Device-Configuration-API) und bietet zwei
    Varianten: **Zusammenführen** (nur gesicherte Werte überschreiben) oder **Ersetzen**
    (betroffene Bereiche erst auf Standard). Das Einspielen ist bei Axis noch nicht an
    echter Hardware verifiziert; der Dialog weist darauf hin.
  - **Hanwha** kann die **Netzwerkeinstellungen der Zielkamera beibehalten** (Checkbox).

---

## Exportieren
Speichert die Geräteliste der aktuellen Gruppe als **CSV** oder **Textdatei**.

---

## Plugins: Axis und ONVIF

Der herstellerspezifische Teil steckt in Plugins. Welche Aktionen möglich sind, meldet
das jeweilige Plugin — nicht unterstützte Buttons bleiben **ausgegraut**.

**Beide Plugins können:** Gerätesuche (Axis per mDNS, ONVIF per WS-Discovery),
Online-Prüfung (bei ONVIF sogar ohne Zugangsdaten), Modell/Firmware auslesen,
IP-Adresse (fest/DHCP), ONVIF-Benutzer und Werksreset.

**Nur das Axis-Plugin kann:** reguläre **Benutzer** (der ONVIF-Standard kennt nur *eine*
Benutzerliste — die ONVIF-Liste), **Firmware aufspielen**, die **Update-Suche**, den
**Konfigurations-Import/-Export** (`.cfg`) und das **Konfig-Backup** (Komplett-Sicherung
über die Device-Configuration-API). Für ONVIF-Geräte bleiben diese Buttons ausgegraut.

Das **ONVIF-Plugin ist ab Werk ausgeschaltet** (Einstellungen → *Plugins*). Es ist für
Kameras gedacht, für die es kein eigenes Hersteller-Plugin gibt; bei Axis-Geräten kann es
schlicht weniger. Der ONVIF-Standard normiert keine Konfigurationsvorlage, das
Firmware-Update ist dort optional und je Hersteller unterschiedlich umgesetzt, und ein
Verzeichnis verfügbarer Firmware-Stände gibt es nicht — daher die Lücken oben.

**Voraussetzungen:** Auf der Kamera muss ONVIF aktiviert sein und ein **ONVIF-Benutzer**
existieren (bei Axis ist das eine **eigene** Benutzerliste — die regulären Zugangsdaten
funktionieren für ONVIF nicht). Außerdem sollte die **Uhr der Kamera** stimmen: Die
ONVIF-Anmeldung ist zeitabhängig. Das Programm gleicht den Zeitversatz selbst aus, ein
grob falsch gestelltes Datum kann die Anmeldung aber trotzdem scheitern lassen.

---

## Einstellungen
Mehrere Bereiche:
- **Darstellung** — modernes Design **Dunkel** oder **Hell** (Sun Valley); die
  Umschaltung wirkt sofort und wird gespeichert. Über **„Sprache / Language"** lässt
  sich die Programmsprache zwischen **Deutsch** und **English** umstellen; die Auswahl
  wird gespeichert und wirkt **beim nächsten Programmstart** (nicht sofort — wie die
  Maximiert-Option). Übersetzt sind die gesamte Oberfläche und die Ergebnismeldungen
  der Aktionen; gerätespezifische Namen (eigene Gruppennamen, Modell-/Firmware-Werte)
  bleiben unverändert. Zusätzlich lässt sich
  **„Beim Start maximiert öffnen"** aktivieren — das Hauptfenster öffnet dann beim
  nächsten Programmstart bildschirmfüllend.
- **Tresor** — Passwort-Tresor anlegen, entsperren, sperren oder Master-Passwort
  ändern. Der Tresor speichert Kamera-Passwörter verschlüsselt (AES-256-GCM,
  abgeleitet aus dem Master-Passwort).
  - **„Tresor beim Programmstart automatisch entsperren"** (Häkchen): Beim
    Aktivieren wird das Master-Passwort einmal abgefragt und **gerätegebunden**
    (verschlüsselt, an Rechner + Benutzerkonto gebunden) hinterlegt; danach ist
    der Tresor bei jedem Start sofort entsperrt. **Sicherheitshinweis:** Das ist
    Komfort auf Kosten der Sicherheit — wer als dieser Benutzer Zugriff auf den
    Rechner hat, kann den Tresor öffnen. Das Token funktioniert nicht auf einem
    anderen Rechner/Konto. Häkchen entfernen löscht das Token wieder.
- **Plugins** — Plugins aktivieren/deaktivieren: **Axis** (an) und **ONVIF (generisch)**
  (ab Werk aus). Die Auswahl wird gespeichert.
- **Online-Prüfung** — pro Gruppe die automatische Online-Prüfung ein-/ausschalten
  und das Intervall festlegen.
- **Spalten** — einzelne Spalten der Geräteliste ein-/ausblenden (die Spalte
  „Name" bleibt immer sichtbar).
- **Firmwareupdates** — zwei Bereiche:
  - Schalter **„Firmware-Updates parallel ausführen"**: Sind mehrere Kameras markiert,
    werden sie gleichzeitig aktualisiert (bis zur einstellbaren Anzahl **Maximal
    gleichzeitig**) statt nacheinander. Das verkürzt Sammel-Updates deutlich, da bei
    jeder Kamera auf den Neustart gewartet wird. Ist der Schalter aus, laufen die
    Updates der Reihe nach.
  - **Update-Suche:** online nach Updates suchen (an/aus); **„Vorschlag in der
    Hauptversion der Kamera belassen"** (LTS-treu, siehe Abschnitt *Firmware*); ein
    eigenes **Firmware-Verzeichnis**, falls ein interner Spiegel genutzt wird (leer =
    Vorgabe des Plugins); **„Firmware-Cache leeren"** mit Anzeige des belegten Platzes.
- **Import und Sicherung** — Geräte und Gruppen aus einer
  **AXIS-Device-Manager**-Export-Datei (JSON) übernehmen sowie eigene Sicherungen
  erstellen/einspielen. Unterstützt werden die Datei-Formate **1.x** und **2.x**.
  Über „Export-Datei wählen und importieren…" die Datei auswählen; eine Vorschau
  zeigt Version, Anzahl Geräte/Gruppen/Zugangsdaten, danach bestätigen. Geräte
  werden anhand der MAC/Seriennummer zusammengeführt (kein Duplikat, wenn sie
  später per Suche wiederauftauchen), Gruppen gleichen Namens werden **ergänzt**.
  Ist das Häkchen **„Zugangsdaten in den Tresor übernehmen"** gesetzt und der
  Tresor entsperrt, werden die enthaltenen Benutzer/Passwörter im Tresor
  gespeichert. Verschlüsselte Exporte lassen sich nicht importieren.

  Im selben Reiter gibt es die **Sicherung (Daten + Passwort-Tresor)**:
  - **Sicherung exportieren…** — schreibt Gruppen, Geräte und den Passwort-Tresor
    in **eine** verschlüsselte Datei (`.kkmbackup`). Dabei wird ein
    **Backup-Passwort** abgefragt (zweimal), mit dem die Datei per AES-256-GCM
    geschützt wird. Die Datei ist plattformübergreifend (Linux/Windows) wieder
    einlesbar. **Backup-Passwort gut aufbewahren** — ohne es ist die Sicherung
    nicht wiederherstellbar.
  - **Sicherung wiederherstellen…** — spielt eine `.kkmbackup`-Datei zurück und
    **ersetzt** die aktuellen Gruppen, Geräte und den Tresor. Nach dem Einspielen
    ist der Tresor gesperrt und wird mit dem **Master-Passwort aus der Sicherung**
    entsperrt. Bei geänderter Plugin-Auswahl das Programm neu starten.

- **Über** — zeigt die Programmversion, die Versionen der verwendeten Komponenten
  (Python, Tcl/Tk, zeroconf, cryptography, sv-ttk), den Ersteller und die Lizenz
  sowie den Hinweis, dass das Programm mit Unterstützung von künstlicher Intelligenz
  entwickelt wurde.

---

## Speicherort der Daten
Gespeichert werden Gruppen (`groups.json`), Einstellungen (`settings.json`) und der
verschlüsselte Passwort-Tresor (`vault.enc`) im Unterordner
`kamera_konfigurationsmanager`:

- **Windows (portable `.exe`):** **neben der ausführbaren Datei** — die Konfiguration
  ist damit mitnehmbar (z. B. auf einem USB-Stick) und bleibt beim Programm.
- **Windows (aus dem Quellcode gestartet):** im Benutzerprofil unter
  `%APPDATA%\kamera_konfigurationsmanager`.
- **Linux:** im Benutzerprofil unter `~/.config/kamera_konfigurationsmanager`.
