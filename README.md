# Hasi's ID3-Tag-Editor

Ein benutzerfreundlicher Tag-Editor für MP3- und FLAC-Dateien mit nativer Mac-GUI.

## Download & Installation

1. Gehe zu [**Releases**](../../releases)
2. Lade die Datei `Hasis-ID3-Tag-Editor-macOS.zip` herunter
3. ZIP entpacken
4. `Hasi's ID3-Tag-Editor.app` in den Programme-Ordner ziehen
5. Fertig — einfach doppelklicken!

> **Hinweis beim ersten Start:** macOS zeigt möglicherweise eine Warnung, da die App nicht über den App Store installiert wurde. In diesem Fall: Rechtsklick auf die App → "Öffnen" → "Öffnen" bestätigen. Das muss nur beim ersten Mal gemacht werden.

## Features

- **MP3 & FLAC Support** — Lesen und Schreiben aller gängigen Tags (ID3v2 / Vorbis Comments)
- **Batch-Bearbeitung** — Mehrere Dateien gleichzeitig bearbeiten (z.B. Album, Künstler für eine ganze CD setzen)
- **Auto-Nummerierung** — Track-Nummern automatisch durchnummerieren
- **Cover-Art** — Cover-Bilder anzeigen, laden, exportieren und entfernen
- **Datei-Umbenennung** — Dateien nach konfigurierbaren Vorlagen umbenennen (z.B. `{tracknumber:02} - {title}`)
- **Drag & Drop** — Dateien und Ordner einfach per Drag & Drop laden
- **Alle Tag-Felder** — Titel, Künstler, Album, Jahr, Genre, Komponist, BPM, ISRC, Tonart, Stimmung und viele mehr
- **Benutzerfreundlich** — Deutsche Oberfläche, intuitive Bedienung, Fortschrittsanzeigen

## Schnellstart

1. **Dateien laden**: Über `Datei → Dateien öffnen` oder per Drag & Drop
2. **Tags bearbeiten**: Datei(en) in der Liste auswählen → Tags rechts bearbeiten
3. **Batch-Bearbeitung**: Mehrere Dateien auswählen → Tab "Batch-Bearbeitung" → Felder ausfüllen → "Anwenden"
4. **Speichern**: `Speichern` oder `⌘S`

### Tastenkürzel

| Kürzel | Aktion |
|--------|--------|
| `⌘O` | Dateien öffnen |
| `⇧⌘O` | Ordner öffnen |
| `⌘S` | Speichern |
| `⌘A` | Alle auswählen |

## Für Entwickler

### Aus dem Quellcode starten

```bash
git clone https://github.com/Hasi1971HH/Hasis-ID3-Tag-Editor.git
cd Hasis-ID3-Tag-Editor
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m tag_editor.main
```

### App selbst bauen

```bash
./build.sh
```

Die fertige App liegt dann unter `dist/Hasi's ID3-Tag-Editor.app`.

## Lizenz

MIT
