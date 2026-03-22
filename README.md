# Hasi's ID3-Tag-Editor

Ein benutzerfreundlicher Tag-Editor für MP3- und FLAC-Dateien mit nativer Mac-GUI.

## Features

- **MP3 & FLAC Support** — Lesen und Schreiben aller gängigen Tags (ID3v2 / Vorbis Comments)
- **Batch-Bearbeitung** — Mehrere Dateien gleichzeitig bearbeiten (z.B. Album, Künstler für eine ganze CD setzen)
- **Auto-Nummerierung** — Track-Nummern automatisch durchnummerieren
- **Cover-Art** — Cover-Bilder anzeigen, laden, exportieren und entfernen
- **Datei-Umbenennung** — Dateien nach konfigurierbaren Vorlagen umbenennen (z.B. `{tracknumber:02} - {title}`)
- **Drag & Drop** — Dateien und Ordner einfach per Drag & Drop laden
- **Alle Tag-Felder** — Titel, Künstler, Album, Jahr, Genre, Komponist, BPM, ISRC, Tonart, Stimmung und viele mehr
- **Benutzerfreundlich** — Deutsche Oberfläche, intuitive Bedienung, Fortschrittsanzeigen

## Installation

### Voraussetzungen
- Python 3.10 oder neuer
- macOS (für natives Look & Feel optimiert)

### Setup

```bash
# Repository klonen
git clone https://github.com/Hasi1971HH/Hasis-ID3-Tag-Editor.git
cd Hasis-ID3-Tag-Editor

# Virtuelle Umgebung erstellen (empfohlen)
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt
```

## Benutzung

```bash
# App starten
python -m tag_editor.main
```

### Schnellstart

1. **Dateien laden**: Über `Datei → Dateien öffnen` oder per Drag & Drop
2. **Tags bearbeiten**: Datei(en) in der Liste auswählen → Tags rechts bearbeiten
3. **Batch-Bearbeitung**: Mehrere Dateien auswählen → Tab "Batch-Bearbeitung" → Felder ausfüllen → "Anwenden"
4. **Speichern**: `💾 Speichern` oder `⌘S`

### Tastenkürzel

| Kürzel | Aktion |
|--------|--------|
| `⌘O` | Dateien öffnen |
| `⇧⌘O` | Ordner öffnen |
| `⌘S` | Speichern |
| `⌘A` | Alle auswählen |

## Projektstruktur

```
tag_editor/
├── __init__.py          # Package-Info
├── main.py              # Einstiegspunkt & Styling
├── main_window.py       # Hauptfenster (GUI)
└── tag_handler.py       # Tag-Lesen/Schreiben (mutagen)
```

## Lizenz

MIT
