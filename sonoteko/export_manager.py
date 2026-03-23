"""Export der Library nach iTunes XML, Plex, Kodi NFO und M3U."""

import os
import time
import json
import hashlib
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent
from xml.dom import minidom

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QFileDialog, QCheckBox, QRadioButton, QButtonGroup,
    QProgressBar, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from sonoteko.database import LibraryDatabase, TrackRecord
from sonoteko.tag_handler import format_duration


# ── iTunes XML ────────────────────────────────────────────────────────────────

def export_itunes_xml(tracks: list[TrackRecord], output_path: str):
    """Erzeugt eine iTunes Music Library XML Datei."""
    plist = Element("plist", version="1.0")
    root_dict = SubElement(plist, "dict")

    def add_key_val(parent, key, value, val_type="string"):
        k = SubElement(parent, "key")
        k.text = key
        v = SubElement(parent, val_type)
        if val_type not in ("true", "false"):
            v.text = str(value)

    add_key_val(root_dict, "Major Version", "1", "integer")
    add_key_val(root_dict, "Minor Version", "1", "integer")
    add_key_val(root_dict, "Application Version", "12.0")
    add_key_val(root_dict, "Music Folder", f"file://{os.path.expanduser('~/Music/Sonoteko/')}")

    tracks_key = SubElement(root_dict, "key")
    tracks_key.text = "Tracks"
    tracks_dict = SubElement(root_dict, "dict")

    for i, track in enumerate(tracks, 1):
        track_id = str(i * 100)
        SubElement(tracks_dict, "key").text = track_id
        td = SubElement(tracks_dict, "dict")

        add_key_val(td, "Track ID", track_id, "integer")
        if track.title:
            add_key_val(td, "Name", track.title)
        if track.artist:
            add_key_val(td, "Artist", track.artist)
        if track.albumartist:
            add_key_val(td, "Album Artist", track.albumartist)
        if track.album:
            add_key_val(td, "Album", track.album)
        if track.genre:
            add_key_val(td, "Genre", track.genre)
        if track.year:
            add_key_val(td, "Year", track.year, "integer")
        if track.tracknumber:
            try:
                add_key_val(td, "Track Number", track.tracknumber.split("/")[0], "integer")
            except (ValueError, AttributeError):
                pass
        if track.composer:
            add_key_val(td, "Composer", track.composer)
        if track.bpm:
            try:
                add_key_val(td, "BPM", track.bpm, "integer")
            except ValueError:
                pass
        if track.duration:
            add_key_val(td, "Total Time", str(int(track.duration * 1000)), "integer")
        if track.bitrate:
            add_key_val(td, "Bit Rate", str(track.bitrate), "integer")
        if track.samplerate:
            add_key_val(td, "Sample Rate", str(track.samplerate), "integer")
        add_key_val(td, "Play Count", str(track.play_count), "integer")
        add_key_val(td, "Rating", str(track.rating * 20), "integer")
        add_key_val(td, "Location", "file://" + track.path)
        add_key_val(td, "Kind", f"{track.format} audio file")

    tree = ElementTree(plist)
    indent(tree, space="  ")
    header = '<?xml version="1.0" encoding="UTF-8"?>\n'
    header += '<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" '
    header += '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        tree.write(f, encoding="unicode", xml_declaration=False)


# ── Kodi NFO ─────────────────────────────────────────────────────────────────

def export_kodi_nfo(track: TrackRecord, output_path: str):
    """Erzeugt eine Kodi-kompatible .nfo Datei für einen Track."""
    root = Element("song")
    if track.title:
        SubElement(root, "title").text = track.title
        SubElement(root, "sorttitle").text = track.title
    if track.artist:
        art_el = SubElement(root, "artist")
        art_el.text = track.artist
    if track.album:
        SubElement(root, "album").text = track.album
    if track.albumartist:
        SubElement(root, "albumartist").text = track.albumartist
    if track.year:
        SubElement(root, "year").text = track.year
    if track.genre:
        SubElement(root, "genre").text = track.genre
    if track.tracknumber:
        try:
            SubElement(root, "track").text = str(int(track.tracknumber.split("/")[0]))
        except (ValueError, AttributeError):
            SubElement(root, "track").text = track.tracknumber
    if track.discnumber:
        try:
            SubElement(root, "disc").text = str(int(track.discnumber.split("/")[0]))
        except (ValueError, AttributeError):
            SubElement(root, "disc").text = track.discnumber
    if track.composer:
        SubElement(root, "composer").text = track.composer
    if track.comment:
        SubElement(root, "comment").text = track.comment
    if track.bpm:
        SubElement(root, "bpm").text = track.bpm
    if track.duration:
        SubElement(root, "runtime").text = str(int(track.duration))
    if track.rating:
        SubElement(root, "userrating").text = str(track.rating * 2)

    tree = ElementTree(root)
    indent(tree, space="  ")
    with open(output_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)


def export_kodi_library(tracks: list[TrackRecord], output_dir: str):
    """Erzeugt .nfo Dateien für alle Tracks neben den Audio-Dateien."""
    created = 0
    for track in tracks:
        nfo_path = os.path.splitext(track.path)[0] + ".nfo"
        try:
            export_kodi_nfo(track, nfo_path)
            created += 1
        except Exception as e:
            print(f"[export_kodi] {track.path}: {e}")
    return created


# ── Plex ─────────────────────────────────────────────────────────────────────

def export_plex_json(tracks: list[TrackRecord], output_path: str):
    """Exportiert die Library als JSON — kann in Plex-Skripte importiert werden."""
    data = []
    for track in tracks:
        data.append({
            "file": track.path,
            "title": track.title,
            "artist": track.artist,
            "albumArtist": track.albumartist,
            "album": track.album,
            "year": track.year,
            "genre": track.genre,
            "trackNumber": track.tracknumber,
            "discNumber": track.discnumber,
            "composer": track.composer,
            "duration": track.duration,
            "bitrate": track.bitrate,
            "format": track.format,
            "hasCover": track.has_cover,
            "playCount": track.play_count,
            "rating": track.rating,
        })
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"library": data, "total": len(data)}, f, indent=2, ensure_ascii=False)


# ── Export Widget ─────────────────────────────────────────────────────────────

class ExportPanel(QWidget):
    def __init__(self, db: LibraryDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── iTunes ──
        itunes_group = QGroupBox("iTunes / Apple Music")
        itunes_layout = QVBoxLayout(itunes_group)
        itunes_layout.addWidget(QLabel(
            "Exportiert die Library als iTunes Music Library XML.\n"
            "Datei → Mediathek → Mediathek importieren in iTunes/Music."
        ))
        btn_itunes = QPushButton("iTunes XML exportieren …")
        btn_itunes.clicked.connect(self._export_itunes)
        itunes_layout.addWidget(btn_itunes)
        layout.addWidget(itunes_group)

        # ── Kodi ──
        kodi_group = QGroupBox("Kodi")
        kodi_layout = QVBoxLayout(kodi_group)
        kodi_layout.addWidget(QLabel(
            "Erzeugt .nfo Dateien neben den Audio-Dateien.\n"
            "Kodi liest diese beim Bibliotheks-Scan automatisch ein."
        ))
        btn_kodi = QPushButton(".nfo Dateien erstellen")
        btn_kodi.clicked.connect(self._export_kodi)
        kodi_layout.addWidget(btn_kodi)
        layout.addWidget(kodi_group)

        # ── Plex ──
        plex_group = QGroupBox("Plex Media Server")
        plex_layout = QVBoxLayout(plex_group)
        plex_layout.addWidget(QLabel(
            "Exportiert die Library als JSON-Datei.\n"
            "Kann mit Plex-Skripten oder dem Plex API importiert werden."
        ))
        btn_plex = QPushButton("Plex JSON exportieren …")
        btn_plex.clicked.connect(self._export_plex)
        plex_layout.addWidget(btn_plex)
        layout.addWidget(plex_group)

        # ── M3U ──
        m3u_group = QGroupBox("M3U Playlist")
        m3u_layout = QVBoxLayout(m3u_group)
        m3u_layout.addWidget(QLabel("Exportiert alle Tracks als M3U-Playlist-Datei."))
        btn_m3u = QPushButton("Gesamte Library als M3U exportieren …")
        btn_m3u.clicked.connect(self._export_m3u)
        m3u_layout.addWidget(btn_m3u)
        layout.addWidget(m3u_group)

        self._status = QLabel()
        self._status.setStyleSheet("color: #888;")
        layout.addWidget(self._status)
        layout.addStretch()

    def _export_itunes(self):
        tracks = self.db.get_all_tracks()
        if not tracks:
            QMessageBox.information(self, "Keine Tracks", "Die Library ist leer.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "iTunes XML speichern", "iTunes Music Library.xml",
            "XML Dateien (*.xml)"
        )
        if not path:
            return
        try:
            export_itunes_xml(tracks, path)
            self._status.setText(f"iTunes XML exportiert: {len(tracks)} Tracks")
            QMessageBox.information(self, "Exportiert", f"{len(tracks)} Tracks exportiert nach:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _export_kodi(self):
        tracks = self.db.get_all_tracks()
        if not tracks:
            QMessageBox.information(self, "Keine Tracks", "Die Library ist leer.")
            return
        reply = QMessageBox.question(
            self,
            "Kodi NFO erstellen",
            f".nfo Dateien neben allen {len(tracks)} Audio-Dateien erstellen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            created = export_kodi_library(tracks, "")
            self._status.setText(f"{created} .nfo Dateien erstellt")
            QMessageBox.information(self, "Fertig", f"{created} .nfo Dateien erstellt.")

    def _export_plex(self):
        tracks = self.db.get_all_tracks()
        if not tracks:
            QMessageBox.information(self, "Keine Tracks", "Die Library ist leer.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Plex JSON speichern", "sonoteko_library.json",
            "JSON Dateien (*.json)"
        )
        if not path:
            return
        try:
            export_plex_json(tracks, path)
            self._status.setText(f"Plex JSON exportiert: {len(tracks)} Tracks")
            QMessageBox.information(self, "Exportiert", f"{len(tracks)} Tracks exportiert nach:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _export_m3u(self):
        def export_m3u(tracks, extended=True):
            lines = ["#EXTM3U\n"]
            for t in tracks:
                if extended:
                    dur = int(t.duration)
                    title = f"{t.artist} - {t.title}" if t.artist else t.title
                    lines.append(f"#EXTINF:{dur},{title}\n")
                lines.append(t.path + "\n")
            return "".join(lines)
        tracks = self.db.get_all_tracks()
        if not tracks:
            QMessageBox.information(self, "Keine Tracks", "Die Library ist leer.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "M3U speichern", "Sonoteko Library.m3u8",
            "M3U Playlist (*.m3u *.m3u8)"
        )
        if not path:
            return
        content = export_m3u(tracks)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self._status.setText(f"M3U exportiert: {len(tracks)} Tracks")
        QMessageBox.information(self, "Exportiert", f"{len(tracks)} Tracks exportiert nach:\n{path}")
