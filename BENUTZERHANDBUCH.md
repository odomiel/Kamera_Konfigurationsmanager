# Benutzerhandbuch

## 1 Über dieses Programm

Der **Kamera_Konfigurationsmanager** findet Netzwerkkameras im lokalen Netz und
konfiguriert sie — einzeln oder viele auf einmal. Der Aufbau orientiert sich grob am
AXIS Device Manager, **ohne Live-Bild und ohne Aufzeichnung**: Es geht ausschließlich um
Verwaltung und Konfiguration.

Alle Aktionen wirken immer auf die in der Geräteliste **markierten** Kameras, laufen im
Hintergrund und protokollieren ihr Ergebnis für **jede Kamera einzeln**. Das Fenster
bleibt dabei bedienbar; nichts blockiert.

Die Oberfläche ist auf **Deutsch** und **Englisch** verfügbar (umschaltbar in den
Einstellungen → *Darstellung*, siehe Kapitel 12; die Umstellung wirkt beim nächsten Start).
Dieses Handbuch liegt auf Deutsch und Englisch vor (englisch: `BENUTZERHANDBUCH_EN.md` bzw.
`User_Manual.pdf`).

Unterstützt werden zwei Gerätefamilien:

- **Axis** — voller Funktionsumfang über die VAPIX-Schnittstelle.
- **ONVIF (generisch)** — jede standardkonforme Kamera, mit dem Funktionsumfang, den der
  ONVIF-Standard hergibt (siehe Kapitel 11). Ab Werk ausgeschaltet.

> **Hinweis:** Das Programm speichert alles in einfachen Dateien — keine Datenbank, kein
> Serverdienst, keine Cloud. Es läuft rein lokal in Ihrem Netz.

## 2 Installation und Start

### Linux (AppImage)

Die AppImage ist eigenständig: Sie enthält Python, Tcl/Tk und alle Bibliotheken. Es
muss nichts installiert werden.

```
chmod +x Kamerakonfigurationsmanager-<Version>-x86_64.AppImage
./Kamerakonfigurationsmanager-<Version>-x86_64.AppImage
```

### Windows (portable .exe)

Die Datei `Kamerakonfigurationsmanager_<Version>.exe` wird **nicht installiert**, sondern
direkt gestartet. Sie legt ihre Daten **neben sich selbst** ab (Ordner
`kamera_konfigurationsmanager`) — Programm und Konfiguration lassen sich damit zusammen
auf einen USB-Stick kopieren und woanders weiterverwenden.

### Aus dem Quelltext

```
pip install -r requirements.txt
python3 main.py
```

Benötigt Python 3.14 mit Tkinter sowie die Pakete `zeroconf`, `cryptography` und
`sv-ttk`.

## 3 Erste Schritte

Beim Start erscheint zunächst ein **Haftungshinweis**: Dies ist kein offizielles Tool der
unterstützten Hersteller, die Nutzung erfolgt auf eigene Gefahr. Mit der Checkbox
*„Ich weiß, was ich tue – nicht wieder anzeigen"* lässt er sich dauerhaft bestätigen;
derselbe Text steht auch unter *Einstellungen → Über*.

Der typische Ablauf beim ersten Start:

1. **Suchen/aktualisieren** anklicken. Das Programm durchsucht das lokale Netz und trägt
   alle gefundenen Kameras in die Gruppe „Alle Kameras" ein.
2. Für Kameras mit unbekannten Zugangsdaten erscheint eine **Abfrage**. Geben Sie
   Benutzer und Passwort ein — mit der Option *„Dieses Passwort bei allen Kameras mit
   unbekannten Zugangsdaten ausprobieren"* gilt die Eingabe für alle noch offenen
   Kameras.
3. Funktionierende Zugangsdaten werden **automatisch gespeichert**. Da dafür ein
   verschlüsselter Tresor nötig ist, bietet das Programm an, ihn jetzt einzurichten
   (Kapitel 9). Lehnen Sie ab, merkt es sich die Zugangsdaten nur für die laufende
   Sitzung.
4. Erst jetzt kennt das Programm **Modell und Firmware** jeder Kamera — beides steht nicht
   im Suchergebnis, sondern wird per Kamera-Login nachgelesen.
5. Kameras markieren und eine Aktion aus der Leiste oben wählen.

> **Werksneue Kameras** werden automatisch erkannt und **nicht** nach einem Passwort
> gefragt. In der Spalte *Firmware* steht dann „Ersteinrichtung erforderlich".

## 4 Das Hauptfenster

**Links** stehen die Gerätegruppen. Ganz oben die nicht löschbare Gruppe **„Alle
Kameras"**, darunter **„Ohne Gruppe"** (alle Kameras ohne eigene Gruppenzuordnung, etwa
frisch gefundene), darunter Ihre eigenen Gruppen alphabetisch. Das **Suchfeld** neben der
Überschrift filtert die Gruppenliste live.

**Rechts** steht die Geräteliste der gewählten Gruppe mit den Spalten *Name, Modell,
IP-Adresse, IPv6-Adresse, MAC/Seriennummer, Firmware, Gruppe(n)* und *Status*. Die
IPv6-Adressen werden bei der Suche miterkannt (globale Adressen zuerst, Link-Local
`fe80::` dahinter) und dienen der Anzeige und dem Export — die Aktionen selbst laufen
über die IPv4-Adresse. Ein Klick auf einen
Spaltenkopf sortiert danach, ein erneuter Klick kehrt die Richtung um (▲/▼ zeigt die
aktive Spalte). Sortiert wird „natürlich", das heißt IP-Adressen und Firmware-Versionen
ordnen sich zahlenrichtig und nicht alphabetisch. Die **Spaltenbreiten** ändern Sie durch
Ziehen an der Spaltengrenze in der Kopfzeile; die Einstellung bleibt über Programmstarts
hinweg erhalten. Welche Spalten überhaupt sichtbar sind, legen Sie in den Einstellungen
fest (Kapitel 12).

**Oben** liegt die Aktionsleiste. Rechts neben *Einstellungen* zeigt ein Schloss-Schalter
den Zustand des Passwort-Tresors: geschlossenes Schloss = gesperrt, offenes Schloss =
entsperrt. Ein Klick schaltet um.

Mehrere Kameras markieren Sie mit **Strg** oder **Umschalt**. Ein **Doppelklick** auf eine
Kamera öffnet ihre Weboberfläche im Browser.

Alle fünf Aktionen stehen auch im **Rechtsklick-Menü** der Geräteliste bereit.

## 5 Gerätesuche und Online-Status

Die Suche findet Axis-Kameras per **mDNS**; ist zusätzlich das ONVIF-Plugin aktiv, sucht
sie parallel per **WS-Discovery** nach ONVIF-Geräten. Bereits bekannte Kameras bleiben
erhalten, auch wenn sie gerade offline sind.

Gefundene Kameras werden auf **online** gesetzt, bekannte aber nicht mehr gefundene auf
**offline** (grün beziehungsweise rot in der Spalte *Status*). **Online prüfen** prüft die
markierten Kameras sofort; zusätzlich lässt sich pro Gruppe eine **automatische
Online-Prüfung** mit Intervall einschalten (Kapitel 12).

> **Doppelte Einträge?** Sind Axis- und ONVIF-Plugin gleichzeitig aktiv, findet das
> ONVIF-Plugin die Axis-Kameras ebenfalls. Das Programm verwirft solche Treffer
> automatisch: Wurde eine der IP-Adressen schon von einem Hersteller-Plugin gemeldet,
> gewinnt dieses, weil es mehr kann. Steht dieselbe Kamera aus früheren Suchen doch
> einmal unter beiden Identitäten in der Liste, führt die nächste Suche die Einträge
> selbsttätig zusammen — Gruppenzuordnung, Online-Status und gespeicherte Zugangsdaten
> wandern dabei zum Hersteller-Eintrag (die Statuszeile meldet „… ONVIF-Duplikat(e)
> zusammengeführt").

## 6 Gruppen

Gruppen sind reine Ordnungshilfe — eine Kamera darf in mehreren Gruppen sein.

- **+ Gruppe / Umbenennen / Löschen** (links unten) verwaltet eigene Gruppen. „Alle
  Kameras" lässt sich weder umbenennen noch löschen.
- **Zuweisen:** Kameras markieren, Rechtsklick → *„Zu Gruppe hinzufügen"* → Gruppe wählen
  oder *„Neue Gruppe…"*.
- **Aus Gruppe entfernen** löst nur die Zuordnung, die Kamera bleibt bekannt.
- **Kamera(s) vollständig entfernen** löscht die Kamera aus allen Gruppen **und** ihr
  gespeichertes Passwort. Bei der nächsten Suche taucht eine erreichbare Kamera wieder auf.

## 7 Zugangsdaten in den Aktionsdialogen

Jeder Aktionsdialog hat oben den Bereich **Zugangsdaten**: Benutzer, Passwort, Verbindung
(auto/https/http), optionaler Port und Timeout.

Ist **„Zugangsdaten aus Tresor verwenden"** angehakt (Voreinstellung, sobald ein Tresor
existiert), werden Benutzer und Passwort **je Kamera** aus dem Tresor genommen. Die Felder
oben sind dann ausgegraut und dienen nur als **Rückfall** für Kameras ohne Tresor-Eintrag.
Entfernen Sie das Häkchen, gelten die eingetippten Zugangsdaten einheitlich für alle
markierten Kameras.

## 8 Die Aktionen

### 8.1 IP-Adresse

Stellt die Netzwerkadresse der markierten Kameras um — wahlweise auf **DHCP**, auf eine
**feste IP fortlaufend ab einer Start-IP** (die Adressen werden der Reihe nach vergeben;
Netz- und Broadcast-Adressen wie `x.y.z.0`/`x.y.z.255` überspringt das Programm dabei
automatisch) oder **pro Kamera einzeln** (je Kamera ein Feld, mit der aktuellen IP
vorbefüllt).

Die Zieladressen werden vor der Umstellung geprüft. Bei fester IP aktualisiert das
Programm die Geräteliste sofort auf die neue Adresse; bei DHCP bleibt die angezeigte
Adresse stehen, weil die neue Adresse vom DHCP-Server kommt und dem Programm nicht bekannt
ist — suchen Sie danach erneut.

> **Hinweis:** Manche Kameras (z. B. ältere Hikvision/STD-CGI) übernehmen die Umstellung
> auf DHCP oder eine neue feste IP erst nach einem **Neustart** („Reboot Required"). Das
> Programm löst diesen Neustart automatisch aus; die Ergebnismeldung lautet dann z. B.
> „auf DHCP umgestellt — Neustart automatisch ausgelöst".

### 8.2 Benutzer

Verwaltet die regulären Kamera-Benutzer: **Anlegen** (Name, Passwort, Rolle
*administrator/operator/viewer*, Option *Auslieferungszustand* für fabrikneue Kameras),
**Passwort ändern** und **Stapel-Import** aus einer Textdatei im Format
`Name,Passwort[,Rolle]`. Die Datei wird einmal vorab geprüft — schlägt eine Zeile fehl,
wird gar nichts angelegt.

Die Option *„Passwort im Tresor speichern"* legt den Zugang verschlüsselt ab.

### 8.3 ONVIF-Benutzer

Wie *Benutzer*, aber für ONVIF-Konten mit den Stufen **Administrator/Operator/User**.

> **Wichtig:** Bei Axis-Kameras sind ONVIF-Benutzer eine **eigene Liste**, getrennt von
> den regulären Benutzern. Wer das ONVIF-Plugin nutzen will, braucht hier zuerst ein
> Konto — mit den VAPIX-Zugangsdaten kommt ONVIF nicht herein.

### 8.4 Firmware

Aktualisiert mehrere Kameras **verschiedener Modelle gleichzeitig**. Die Kameras sind nach
Modell gruppiert; jede Modellzeile bekommt **eine** passende `.bin`-Datei, und eine Zeile
lässt sich aufklappen, um die einzelnen Kameras zu sehen. Modelle ohne zugewiesene Datei
werden übersprungen.

**Nach Updates suchen** (nur Axis) gleicht die Modelle online ab. Das Programm liest das
öffentliche Firmware-Verzeichnis des Herstellers und zeigt in der Spalte *Verfügbar
(online)*, welche Version es gibt:

- `11.11.212 ↑` — ein Update ist verfügbar.
- `5.20.5 (aktuell)` — die Kamera ist auf dem neuesten Stand.
- `?` — das Modell wurde im Verzeichnis nicht gefunden (dann bitte die Datei von Hand
  zuweisen).

**Update herunterladen und zuweisen** lädt die passende Datei mit Fortschrittsanzeige
herunter und trägt sie als Firmware-Datei des Modells ein. Der Download landet in einem
Cache; ein abgebrochener Download wird beim nächsten Versuch fortgesetzt.

Der Vorschlag bleibt bewusst in der **Hauptversion der Kamera**: Eine Kamera auf 10.12.x
bekommt die neueste 10.12er vorgeschlagen und nicht den Sprung auf einen neuen
Hauptversions-Zweig. Über **Version wählen…** können Sie jede andere Version des Modells
nehmen, auch die neueste überhaupt. Diese Zurückhaltung lässt sich in den Einstellungen
abschalten.

Nach dem Aufspielen **wartet** das Programm den Neustart ab, liest die neue Version aus und
färbt die Zeile grün. Ist *Werkseinstellungen (factory default)* angehakt, kommt die Kamera
werksneu zurück und wird als „Ersteinrichtung erforderlich" gekennzeichnet.

> **Achtung:** Die Firmware muss zum Modell passen. Die Kameras starten nach dem Update
> neu und sind für einige Minuten nicht erreichbar.

> **Hinweis:** Einige Kameras (z. B. ältere Hikvision/STD-CGI) flashen nicht sofort,
> sondern nehmen die hochgeladene Firmware nur an und wenden sie erst beim **nächsten
> Neustart** an. Das Programm stößt diesen Neustart in dem Fall selbst an — sonst bliebe
> die Kamera scheinbar unverändert und der Fortschritt würde endlos „auf den Neustart"
> warten.

### 8.5 Konfiguration

Import und Export von Axis-Konfigurationsdateien (`.cfg`, Format v1 und v2).

**Importieren** — Datei wählen, dann öffnet sich die **Auswahl**, was übernommen werden
soll: die einzelnen Parameter (durchsuchbare Liste mit *Alle*/*Keine* und der Ansicht *Nur
Ausgewählte anzeigen*), die **Stream-Profile einzeln** und die **Bewegungserkennung
(VMD4)**. Vorausgewählt ist alles, was die Datei enthält.

> **Warum auswählen?** Eine `.cfg` enthält nicht nur Bildeinstellungen, sondern auch die
> Netzwerk-, Namensserver- und Zeitserver-Parameter der Quellkamera. Wer eine
> Bildeinstellung auf zwanzig Kameras ausrollen will, möchte deren Netzwerkkonfiguration
> selten mitschicken. Filtern Sie die Liste zum Beispiel nach `Image.` und wählen Sie nur
> diese Parameter.

Schreibgeschützte `Properties.*`-Parameter überspringt das Programm automatisch — sonst
würde die Kamera den gesamten Import mit „Authentifizierung fehlgeschlagen" ablehnen. Eine
enthaltene Bewegungserkennung wird über die VMD4-Schnittstelle angewendet; ist die
VMD-Anwendung auf der Kamera gestoppt, startet das Programm sie vorher.

**Exportieren** — liest die Konfiguration der **ersten** markierten Kamera aus und öffnet
dieselbe Auswahl; anschließend wird die `.cfg` gespeichert.

**Auf Werkseinstellungen zurücksetzen** — mit zwei Varianten:

- **Mit Erhalt der IP-Adresse:** Alles zurück, aber die Kamera bleibt unter derselben
  Adresse erreichbar. Das Programm wartet den Neustart ab und meldet den Erfolg erst, wenn
  die Kamera wieder im Erstkonfigurations-Modus ist.
- **Kompletter Werksreset:** Auch die Netzwerkeinstellungen fallen zurück. Die Kamera ist
  danach unter neuer Adresse erreichbar und muss neu gesucht werden.

Beides ist **nicht umkehrbar** und muss bestätigt werden. Gespeicherte Zugangsdaten der
Kamera werden danach verworfen, weil sie nicht mehr gelten.

### 8.6 Konfig-Backup

Sichert bzw. spielt die **vollständige Gerätekonfiguration als Ganzes** ein — anders als
die `.cfg`-Vorlage (Abschnitt 8.5) mit ihrer Parameterauswahl ein gerätespezifisches
Komplett-Abbild (IP, Name, Ereignisregeln, Zeit, Benutzer …). Unterstützt von **Axis**,
**Hikvision**, **Dahua** und **Hanwha**.

- **Backup herunterladen (Kamera → Datei)** — liest die Sicherung der **ersten** markierten
  Kamera und speichert sie. Bei Axis eine **`.json`-Datei** (dieselbe, die die
  Weboberfläche liefert; Passwörter sind nicht enthalten), bei den anderen Herstellern ein
  verschlüsselter **`.bin`-Blob**.
- **Backup einspielen (Datei → Kamera)** — überträgt eine Sicherung; die Kamera startet
  danach neu. Da ein Backup gerätespezifische Daten (IP, Name) enthält, erzeugt dasselbe
  File auf mehreren Kameras Adress-/Identitätskonflikte — der Dialog warnt davor.
  - **Axis** benötigt AXIS OS 11.8 oder neuer (Device-Configuration-API) und bietet die
    Varianten **Zusammenführen** (nur gesicherte Werte überschreiben) oder **Ersetzen**
    (betroffene Bereiche erst auf Standard). Das Einspielen ist bei Axis noch nicht an
    echter Hardware verifiziert; der Dialog weist darauf hin.
  - **Hanwha** kann die **Netzwerkeinstellungen der Zielkamera beibehalten** (Checkbox).

## 9 Der Passwort-Tresor

Der Tresor speichert die Kamera-Passwörter verschlüsselt in **einer** Datei (`vault.enc`):
Aus Ihrem **Master-Passwort** wird per PBKDF2 ein Schlüssel abgeleitet, die Daten liegen
mit **AES-256-GCM** verschlüsselt. Es wird kein Schlüsselbund des Betriebssystems benutzt —
die Datei ist damit mitnehmbar.

Verwaltet wird er in den Einstellungen (Reiter *Tresor*): anlegen, entsperren, sperren,
Master-Passwort ändern. Der Schloss-Schalter oben rechts im Hauptfenster tut dasselbe mit
einem Klick.

**Automatisch entsperren** hinterlegt das Master-Passwort **gerätegebunden** (verschlüsselt,
an Rechner und Benutzerkonto gebunden), sodass der Tresor bei jedem Start sofort offen ist.

> **Sicherheitshinweis:** Das ist Komfort auf Kosten der Sicherheit — wer als dieser
> Benutzer Zugriff auf den Rechner hat, kann den Tresor öffnen. Auf einem anderen
> Rechner oder Konto funktioniert das Token nicht.

**Ohne Master-Passwort gibt es keinen Weg zurück.** Es gibt keine Hintertür und keine
Wiederherstellung.

## 10 Geräteliste exportieren

**Exportieren** speichert die Geräteliste der aktuellen Gruppe als **CSV** oder als
ausgerichtete **Textdatei** — praktisch für Dokumentation und Übergaben.

## 11 Plugins: Axis und ONVIF

Der gesamte herstellerspezifische Teil steckt in Plugins. Welche Aktionen möglich sind,
meldet das jeweilige Plugin; nicht unterstützte Knöpfe bleiben **ausgegraut**.

| Funktion | Axis | ONVIF (generisch) |
| --- | --- | --- |
| Gerätesuche | mDNS | WS-Discovery |
| Online-Prüfung | ja | ja (ohne Zugangsdaten) |
| Modell / Firmware auslesen | ja | ja |
| IP-Adresse (fest/DHCP) | ja | ja |
| Benutzer | ja | — (Standard kennt nur eine Liste) |
| ONVIF-Benutzer | ja | ja |
| Firmware aufspielen | ja | — |
| Update-Suche | ja | — |
| Konfiguration (.cfg) | ja | — |
| Konfig-Backup (Komplett-Sicherung) | ja | — |
| Werksreset | ja | ja |

Das ONVIF-Plugin ist **ab Werk ausgeschaltet** und wird in den Einstellungen unter
*Plugins* zugeschaltet. Es ist für Kameras gedacht, für die es kein eigenes Plugin gibt —
bei Axis-Geräten kann es schlicht weniger.

> **Experimentell: Hikvision und Dahua.** Zusätzlich liegen zwei Hersteller-Plugins bei,
> beide im Plugin-Manager als **„experimentell"** gekennzeichnet, **ab Werk
> ausgeschaltet** und noch **nicht an echter Hardware verifiziert** — die Schreib-Aktionen
> folgen der jeweiligen Hersteller-Dokumentation, sollten aber vorsichtig und auf eigene
> Gefahr eingesetzt werden:
>
> - **Hikvision** (ISAPI): Suche per SADP, Geräteinfo, IP, Benutzer, ONVIF-Benutzer,
>   Firmware-Upload, **Konfig-Backup**, Werksreset. Die SADP-Suche findet auch **werksneue**
>   Kameras, die noch auf ihrer **Werks-IP in einem anderen IP-Segment** stehen (z. B.
>   `192.0.0.64` bzw. `192.168.1.64`, während der Rechner in `192.0.2.x` ist).
> - **Dahua** (HTTP-API): Suche per DHIP, Geräteinfo, IP, Benutzer, ONVIF-Benutzer,
>   Firmware-Upload, Werksreset. Deckt zugleich viele **Dahua-OEM-Marken** ab — u. a. die
>   **Honeywell Performance Series** und Amcrest.
> - **Hanwha/Wisenet** (SUNAPI): Suche über ONVIF, Geräteinfo, IP, Benutzer,
>   ONVIF-Benutzer, Firmware, **Konfig-Backup**, Werksreset. An einer Wisenet-Kamera
>   verifiziert (Discovery, Info, IP, Benutzer); Firmware und Werksreset noch nicht.
>
> Bei allen gibt es keine Update-Suche und keinen `.cfg`-**Parameter**-Im-/Export (kein
> offenes Firmware-Verzeichnis, keine herstellerübergreifende Konfigurationsvorlage). Das
> **Konfig-Backup** (opakes Komplett-Abbild, Abschnitt 8.6) ist davon unabhängig und steht
> bei Hikvision und Hanwha zur Verfügung.

**Was ONVIF nicht kann und warum:** Der Standard normiert keine Konfigurationsvorlage
(seine Sicherungsfunktion liefert nur einen undurchsichtigen Datenblock für genau ein
Gerät), das Firmware-Update ist im Standard optional und bei den Herstellern sehr
unterschiedlich umgesetzt, und ein Verzeichnis verfügbarer Firmware-Stände gibt es nicht.

**Voraussetzungen für ONVIF:** Auf der Kamera muss ONVIF aktiviert sein und ein
**ONVIF-Benutzer** existieren. Außerdem sollte die **Uhr der Kamera** halbwegs stimmen —
die ONVIF-Anmeldung ist zeitabhängig. (Das Programm gleicht den Zeitversatz selbst aus, ein
grob falsch gestelltes Datum kann die Anmeldung aber trotzdem scheitern lassen.)

## 12 Einstellungen

**Darstellung** — modernes Design **Dunkel** oder **Hell**; die Umschaltung wirkt sofort.
**Sprache / Language** — die Programmsprache **Deutsch** oder **English**; die Auswahl wird
gespeichert und wirkt **beim nächsten Programmstart** (nicht sofort — wie *Beim Start
maximiert öffnen*). Übersetzt sind die gesamte Oberfläche und die Ergebnismeldungen der
Aktionen; gerätespezifische Namen (eigene Gruppennamen, Modell-/Firmware-Angaben) bleiben
unverändert. Zusätzlich: *Beim Start maximiert öffnen*.

**Tresor** — siehe Kapitel 9.

**Plugins** — Hersteller-Plugins ein- und ausschalten (Axis, ONVIF). Die Auswahl wird
gespeichert.

**Online-Prüfung** — pro Gruppe die automatische Prüfung ein-/ausschalten und das Intervall
festlegen.

**Spalten** — einzelne Spalten der Geräteliste ein- und ausblenden (*Name* bleibt immer
sichtbar).

**Firmwareupdates** — zwei Bereiche:

- *Firmware-Updates parallel ausführen* (mit **Maximal gleichzeitig**): Mehrere markierte
  Kameras werden gleichzeitig aktualisiert statt nacheinander. Das verkürzt Sammel-Updates
  erheblich, weil bei jeder Kamera auf den Neustart gewartet wird.
- *Update-Suche*: online suchen an/aus; **Vorschlag in der Hauptversion der Kamera
  belassen** (siehe 8.4); ein eigenes **Firmware-Verzeichnis**, falls Sie einen internen
  Spiegel betreiben (leer = Vorgabe des Herstellers); **Firmware-Cache leeren** samt Anzeige
  des belegten Platzes.

**Import und Sicherung**

- *Import aus AXIS Device Manager:* Übernimmt Geräte und Gruppen aus einer
  Export-Datei (JSON, Format 1.x und 2.x). Geräte werden anhand der MAC/Seriennummer
  zusammengeführt, Gruppen gleichen Namens ergänzt. Enthaltene Zugangsdaten wandern auf
  Wunsch in den Tresor. Verschlüsselte Exporte lassen sich nicht einlesen.
- *Sicherung exportieren:* schreibt Gruppen, Geräte **und** den Passwort-Tresor in **eine**
  verschlüsselte Datei (`.kkmbackup`, geschützt durch ein separat abgefragtes
  Backup-Passwort, AES-256-GCM). Plattformübergreifend wieder einlesbar.
- *Sicherung wiederherstellen:* spielt eine `.kkmbackup` zurück und **ersetzt** die
  aktuellen Daten. Danach ist der Tresor gesperrt und wird mit dem Master-Passwort **aus der
  Sicherung** geöffnet.

> **Backup-Passwort gut aufbewahren** — ohne es ist die Sicherung nicht wiederherstellbar.

**Über** — zeigt Programm- und Komponentenversionen, Ersteller und Lizenz sowie den Hinweis
auf die KI-gestützte Entwicklung.

**Lizenzen** — listet in einem scrollbaren Feld die Lizenzen **aller mitgelieferten
Komponenten** (Python, Tcl/Tk, OpenSSL, zeroconf, cryptography u. a. — die
Drittanbieter-Lizenzen) sowie den **vollständigen GPL-3.0-Lizenztext** des Programms.

## 13 Wo die Daten liegen

Gespeichert werden die Gruppen und die bekannte Geräteliste (`groups.json`), die
Einstellungen (`settings.json`) und der verschlüsselte Tresor (`vault.enc`) — jeweils im
Ordner `kamera_konfigurationsmanager`:

| Variante | Ort |
| --- | --- |
| Windows (portable .exe) | **neben der .exe** — mitnehmbar |
| Windows (aus dem Quelltext) | `%APPDATA%\kamera_konfigurationsmanager` |
| Linux | `~/.config/kamera_konfigurationsmanager` |

Heruntergeladene Firmware liegt im Unterordner `firmware_cache` und lässt sich in den
Einstellungen jederzeit löschen.

## 14 Fehlersuche

**„Authentifizierung fehlgeschlagen" (401).** Benutzer oder Passwort stimmen nicht — oder
der Tresor liefert für diese Kamera einen alten Eintrag. Prüfen Sie das Häkchen
*Zugangsdaten aus Tresor verwenden* und tragen Sie die Daten notfalls direkt ein. Nach
einem Werksreset gelten alte Zugangsdaten nicht mehr.

**Die Suche findet eine bekannte Kamera nicht.** mDNS und WS-Discovery arbeiten mit
Multicast und überqueren keine Netzgrenzen: Kameras in einem anderen Subnetz (oder hinter
einem VPN) antworten nicht. Bereits bekannte Kameras bleiben trotzdem in der Liste und
lassen sich weiterhin konfigurieren, solange sie per IP erreichbar sind.

**Update-Suche meldet „Modell nicht gefunden".** Das Modell heißt im Firmware-Verzeichnis
des Herstellers anders, als die Kamera es meldet. Laden Sie die Datei in diesem Fall selbst
herunter und weisen Sie sie von Hand zu — der Rest des Ablaufs bleibt gleich.

**Update-Suche meldet ein Zertifikatsproblem.** Der Download prüft bewusst das
HTTPS-Zertifikat (es handelt sich um eine fremde Datei, die anschließend auf die Kamera
geschrieben wird). Findet das Programm keinen Zertifikatsspeicher, bricht es ab, statt die
Prüfung stillschweigend abzuschalten.

**ONVIF meldet „Sender not authorized" oder Anmeldefehler.** Es fehlt ein ONVIF-Benutzer auf
der Kamera (bei Axis eine eigene Liste!), oder die Uhr der Kamera geht grob falsch.

**Eine Kamera steht doppelt in der Liste.** Axis-/ONVIF-Doppelgänger derselben Kamera
werden bei der nächsten Suche automatisch zusammengeführt (siehe Kapitel 5). Bleibt ein
Duplikat übrig, ist dieselbe Kamera unter zwei verschiedenen IPs bekannt (etwa nach einem
DHCP-Wechsel) — entfernen Sie den alten Eintrag über *Kamera(s) vollständig entfernen*.

**Nach dem Firmware-Update bleibt die Kamera „nicht rechtzeitig zurück".** Das Aufspielen
war erfolgreich, der Neustart dauerte nur länger als das Zeitfenster. Suchen Sie später
erneut oder prüfen Sie den Online-Status.

## 15 Glossar

**mDNS** — Verfahren, mit dem sich Geräte im lokalen Netz selbst ankündigen. Grundlage der
Axis-Gerätesuche.

**WS-Discovery** — das Gegenstück im ONVIF-Standard: Das Programm fragt per
Multicast ins Netz, ONVIF-Geräte antworten.

**VAPIX** — die Programmierschnittstelle der Axis-Kameras. Über sie laufen alle
Axis-Aktionen.

**ONVIF** — herstellerübergreifender Standard für Netzwerkkameras. Das Programm nutzt
davon nur den Teil zur Geräteverwaltung, nicht den Videoteil.

**VMD4** — die Bewegungserkennung von Axis. In einer `.cfg` steckt sie in einem eigenen
Block, nicht in den normalen Parametern.

**LTS** — ein Firmware-Zweig mit langer Pflege, der nur noch Fehler- und
Sicherheitskorrekturen bekommt statt neuer Funktionen.

**Capability** — eine Fähigkeit, die ein Plugin meldet (etwa „kann Firmware aufspielen").
Aus ihnen ergibt sich, welche Knöpfe für eine Kamera nutzbar sind.

## 16 Lizenz

Dieses Programm ist freie Software unter der **GNU General Public License, Version 3 oder
neuer (GPL-3.0-or-later)**. Es enthält Bestandteile des ebenfalls unter GPL-3.0 stehenden
Werkzeugs *Axis_Kamera_Discovery*.

Das Programm wurde mit Unterstützung von künstlicher Intelligenz entwickelt.
