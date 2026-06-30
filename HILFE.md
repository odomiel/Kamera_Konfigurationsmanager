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
- **Oben:** die Aktionsleiste (siehe unten).

Mehrere Kameras lassen sich mit **Strg**/**Umschalt** markieren.

---

## Suchen & Status

- **Suchen** — durchsucht das lokale Netzwerk nach Kameras (mDNS) und nimmt sie in
  „Alle Kameras" auf. Bereits bekannte Kameras bleiben erhalten, auch wenn sie
  gerade offline sind.
- **Online prüfen** — prüft die markierten Kameras (oder die ganze Gruppe) sofort
  auf Erreichbarkeit; das Ergebnis erscheint in der Spalte **Status**
  (● Online / ○ Offline).
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
Verbindung (auto/https/http), optionaler Port und Timeout. Ist der **Passwort-Tresor**
entsperrt und das Passwortfeld leer, wird ein gespeichertes Kamera-Passwort
automatisch verwendet.

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
Vier Bereiche:
- **Tresor** — Passwort-Tresor anlegen, entsperren, sperren oder Master-Passwort
  ändern. Der Tresor speichert Kamera-Passwörter verschlüsselt (AES-256-GCM,
  abgeleitet aus dem Master-Passwort).
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
