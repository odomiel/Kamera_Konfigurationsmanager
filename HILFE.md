# Hilfe — Kamera_Konfigurationsmanager

Diese Hilfe beschreibt alle Funktionen des Programms. Sie ist auch im Programm
über den Button **„Hilfe"** (oben rechts) erreichbar.

Das Programm verwaltet und konfiguriert Netzwerkkameras (derzeit **Axis**) —
**ohne** Live-Bild. Aktionen wirken immer auf die in der Geräteliste **markierten**
Kameras und laufen im Hintergrund; das Ergebnis je Kamera wird protokolliert.

---

## Hauptfenster

- **Links:** die Gerätegruppen. Ganz oben die nicht löschbare Gruppe
  **„Alle Kameras"** (enthält alle bekannten Kameras), darunter eigene Gruppen.
- **Rechts:** die Geräteliste der gewählten Gruppe mit den Spalten Name, Modell,
  IP-Adresse, MAC/Seriennummer, Firmware, **Gruppe(n)** und **Status** (online).
  Ein **Klick auf einen Spaltenkopf** sortiert nach dieser Spalte (erneuter Klick
  kehrt die Richtung um; ▲/▼ zeigt die aktive Spalte). Sortiert wird „natürlich" —
  IP-Adressen und Firmware-Versionen ordnen sich zahlenrichtig.
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

- **Suchen** — durchsucht das lokale Netzwerk nach Kameras (mDNS) und nimmt sie in
  „Alle Kameras" auf. Bereits bekannte Kameras bleiben erhalten, auch wenn sie
  gerade offline sind.
  - **Firmware/Modell** stehen nicht im Suchergebnis und werden nach der Suche per
    Kamera-Login nachgelesen: Kameras mit bekannten Zugangsdaten (Tresor oder
    bereits in dieser Sitzung eingegeben) werden automatisch ausgelesen.
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

### IP-Adresse
Stellt die Netzwerk-Adresse der markierten Kameras um:
- **Auf DHCP umstellen.**
- **Feste IP fortlaufend** ab einer Start-IP — die Adressen werden der Reihe nach
  vergeben (gemeinsame Subnetzmaske, optionales Gateway).
- **Pro Kamera einzeln** — je Kamera ein eigenes IP-Feld (mit aktueller IP
  vorbefüllt).

Die Ziel-Adressen werden vor der Umstellung geprüft; danach sind die Kameras ggf.
unter neuer Adresse erreichbar.

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

Achtung: Die Firmware muss zum Modell passen; die Kameras starten danach neu.

### Konfiguration (Axis `.cfg`)
Import/Export von Axis-Device-Manager-Konfigurationsdateien (Format v1 + v2):
- **Importieren** — eine `.cfg` auf alle markierten Kameras anwenden.
- **Exportieren** — Konfiguration der ersten markierten Kamera auslesen, in einer
  durchsuchbaren Liste die gewünschten Parameter auswählen und als `.cfg` speichern
  (optional mit Stream-Profilen).

---

## Exportieren
Speichert die Geräteliste der aktuellen Gruppe als **CSV** oder **Textdatei**.

---

## Einstellungen
Mehrere Bereiche:
- **Darstellung** — modernes Design **Dunkel** oder **Hell** (Sun Valley); die
  Umschaltung wirkt sofort und wird gespeichert.
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
- **Plugins** — Hersteller-Plugins aktivieren/deaktivieren (derzeit nur Axis).
- **Online-Prüfung** — pro Gruppe die automatische Online-Prüfung ein-/ausschalten
  und das Intervall festlegen.
- **Spalten** — einzelne Spalten der Geräteliste ein-/ausblenden (die Spalte
  „Name" bleibt immer sichtbar).

---

## Speicherort der Daten
Alle Einstellungen liegen im Benutzerprofil
(Windows: `%APPDATA%\kamera_konfigurationsmanager`, Linux:
`~/.config/kamera_konfigurationsmanager`): Gruppen (`groups.json`), Einstellungen
(`settings.json`) und der verschlüsselte Passwort-Tresor (`vault.enc`).
