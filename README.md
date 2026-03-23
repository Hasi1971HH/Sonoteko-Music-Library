<div align="center">

# 🎵 Sonoteko

**Deine Musikbibliothek. Vollständig im Griff.**

Sonoteko ist eine leistungsstarke Desktop-App für macOS zur Verwaltung, Bearbeitung und Wiedergabe deiner Musiksammlung — mit integriertem Player, vollständigem Tag-Editor und automatischer Metadaten-Pflege.

[![Release](https://img.shields.io/github/v/release/Hasi1971HH/Sonoteko-Music-Library?style=flat-square&color=e94560)](../../releases)
[![Platform](https://img.shields.io/badge/platform-macOS-lightgrey?style=flat-square)](../../releases)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

</div>

---

## Download & Installation

1. Gehe zu [**Releases**](../../releases)
2. Lade die neueste `Sonoteko-macOS.zip` herunter
3. ZIP entpacken → `Sonoteko.app` in den **Programme-Ordner** ziehen
4. Doppelklick — fertig

> **Erster Start auf macOS:** Falls eine Sicherheitswarnung erscheint (App nicht aus dem App Store), Rechtsklick auf die App → **Öffnen** → **Öffnen** bestätigen. Dieser Schritt ist nur einmalig nötig.

---

## Features

### 📚 Musikbibliothek
- Ordner scannen und automatisch in die Bibliothek importieren
- SQLite-Datenbank für schnellen Zugriff auf tausende Tracks
- Sortieren, Filtern und Durchsuchen nach Titel, Künstler, Album, Genre u. v. m.
- Spalten frei ein-/ausblendbar und dauerhaft gespeichert

### 🏷️ Tag-Editor
- Unterstützt **MP3** (ID3v2), **FLAC** (Vorbis Comments), **OGG** und **M4A/AAC**
- Alle gängigen Felder: Titel, Künstler, Album, Jahr, Genre, Komponist, BPM, ISRC, Tonart, Stimmung und viele mehr
- **Batch-Bearbeitung** — Album, Künstler oder Genre für eine ganze CD auf einen Schlag setzen
- **Auto-Nummerierung** — Track-Nummern automatisch vergeben
- **Cover-Art** — Bilder laden, anzeigen, exportieren oder entfernen
- **Datei-Umbenennung** nach konfigurierbaren Vorlagen (z. B. `{tracknumber:02} - {title}`)

### 🎧 Integrierter Player
- Direkte Wiedergabe aus der Bibliothek heraus
- Album-Cover-Anzeige im Playback-Bereich (passt sich an die Fenstergröße an)
- Playlist-Unterstützung mit Vor/Zurück-Navigation
- Seek-Leiste mit Zeitanzeige, Lautstärkeregler

### 🌐 Online-Metadaten
- Albuminfos und Cover automatisch aus dem Internet abrufen
- Lyrics laden und direkt in die Tags schreiben
- Metadaten mit einem Klick übernehmen

### 📊 ReplayGain
- Track- und Album-Gain-Analyse direkt in der App
- Werte werden als Standard-Tags gespeichert und sind mit jedem Player kompatibel

### 💾 Export & Backup
- Bibliotheks-Export in gängige Formate
- Backup-Funktion zum Sichern und Wiederherstellen der Datenbank

---

## Schnellstart

| Schritt | Aktion |
|---------|--------|
| **1. Musik importieren** | `Datei → Ordner hinzufügen …` — Sonoteko scannt rekursiv und importiert alle Tracks |
| **2. Tags bearbeiten** | Track in der Bibliothek auswählen → rechts im Tag-Editor bearbeiten → **Speichern** |
| **3. Batch-Bearbeitung** | Mehrere Tracks markieren → Tag-Editor → Felder ausfüllen → **Auf Auswahl anwenden** |
| **4. Song abspielen** | Doppelklick auf einen Track in der Bibliothek |
| **5. Online-Infos** | Track auswählen → Tab **Online** → Suchen → Übernehmen |

### Tastenkürzel

| Kürzel | Aktion |
|--------|--------|
| `⌘O` | Dateien öffnen |
| `⇧⌘O` | Ordner hinzufügen |
| `⌘S` | Änderungen speichern |
| `⌘A` | Alle Tracks auswählen |
| `Space` | Wiedergabe / Pause |
| `⌘T` | Tag-Editor ein-/ausblenden |

---

## Screenshots

> *(folgen mit dem nächsten Release)*

---

## Für Entwickler

### Voraussetzungen

- Python 3.11+
- macOS (für native `.app`-Builds)

### Aus dem Quellcode starten

```bash
git clone https://github.com/Hasi1971HH/Sonoteko-Music-Library.git
cd Sonoteko-Music-Library
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python sonoteko_app.py
```

### App selbst bauen

```bash
./build.sh
```

Die fertige App liegt unter `dist/Sonoteko.app`.

### Tech Stack

| Komponente | Technologie |
|------------|-------------|
| GUI | PyQt6 |
| Audiowiedergabe | QtMultimedia |
| Tag-Verarbeitung | mutagen |
| Datenbank | SQLite (via Python stdlib) |
| Build | PyInstaller |

---

## Lizenz

MIT — freie Nutzung, Weitergabe und Modifikation erlaubt.

---

<div align="center">

Entwickelt mit ♥ von [Hasi1971HH](https://github.com/Hasi1971HH)

</div>
