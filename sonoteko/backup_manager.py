"""Backup und Restore aller Tags als JSON oder XML."""

import os
import json
import time
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, ElementTree, parse, indent

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QFileDialog, QProgressBar, QMessageBox, QTextEdit,
    QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from sonoteko.database import LibraryDatabase, TrackRecord
from sonoteko.tag_handler import read_tags, write_tags


# ── Worker ─────────────────────────────────────────────────────────────────────

class BackupWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, tracks: list[TrackRecord], output_path: str,
                 fmt: str = "json", parent=None):
        super().__init__(parent)
        self.tracks = tracks
        self.output_path = output_path
        self.fmt = fmt

    def run(self):
        try:
            total = len(self.tracks)
            data = []
            for i, track in enumerate(self.tracks):
                self.progress.emit(i + 1, total, track.path)
                info = read_tags(track.path)
                entry = {
                    "path": track.path,
                    "tags": info.tags,
                    "has_cover": info.cover_data is not None,
                }
                data.append(entry)

            backup = {
                "sonoteko_backup": True,
                "version": "2.0",
                "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "track_count": len(data),
                "tracks": data,
            }

            if self.fmt == "json":
                with open(self.output_path, "w", encoding="utf-8") as f:
                    json.dump(backup, f, indent=2, ensure_ascii=False)
            else:
                self._write_xml(backup)

            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))

    def _write_xml(self, backup: dict):
        root = Element("sonoteko_backup")
        root.set("version", backup["version"])
        root.set("created", backup["created"])
        root.set("track_count", str(backup["track_count"]))
        for entry in backup["tracks"]:
            track_el = SubElement(root, "track")
            path_el = SubElement(track_el, "path")
            path_el.text = entry["path"]
            tags_el = SubElement(track_el, "tags")
            for key, value in entry["tags"].items():
                tag_el = SubElement(tags_el, "tag")
                tag_el.set("name", key)
                tag_el.text = str(value)
        tree = ElementTree(root)
        indent(tree, space="  ")
        tree.write(self.output_path, encoding="utf-8", xml_declaration=True)


class RestoreWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int)   # restored, skipped
    error = pyqtSignal(str)

    def __init__(self, backup_path: str, skip_missing: bool = True, parent=None):
        super().__init__(parent)
        self.backup_path = backup_path
        self.skip_missing = skip_missing

    def run(self):
        try:
            data = self._load_backup()
            tracks = data.get("tracks", [])
            total = len(tracks)
            restored = skipped = 0

            for i, entry in enumerate(tracks):
                path = entry["path"]
                self.progress.emit(i + 1, total, path)
                if not os.path.exists(path):
                    if self.skip_missing:
                        skipped += 1
                        continue
                tags = entry.get("tags", {})
                success = write_tags(path, tags)
                if success:
                    restored += 1
                else:
                    skipped += 1

            self.finished.emit(restored, skipped)
        except Exception as e:
            self.error.emit(str(e))

    def _load_backup(self) -> dict:
        if self.backup_path.endswith(".xml"):
            return self._load_xml()
        with open(self.backup_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_xml(self) -> dict:
        tree = parse(self.backup_path)
        root = tree.getroot()
        tracks = []
        for track_el in root.findall("track"):
            path = track_el.findtext("path", "")
            tags = {}
            for tag_el in track_el.findall("tags/tag"):
                tags[tag_el.get("name", "")] = tag_el.text or ""
            tracks.append({"path": path, "tags": tags})
        return {
            "sonoteko_backup": True,
            "version": root.get("version", "?"),
            "created": root.get("created", ""),
            "track_count": int(root.get("track_count", 0)),
            "tracks": tracks,
        }


# ── UI Panel ──────────────────────────────────────────────────────────────────

class BackupPanel(QWidget):
    def __init__(self, db: LibraryDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self._worker: Optional[QThread] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Backup ──
        backup_group = QGroupBox("Backup erstellen")
        backup_layout = QVBoxLayout(backup_group)
        backup_layout.addWidget(QLabel(
            "Sichert alle Tags aller Tracks in der Library.\n"
            "Das Cover-Bild selbst wird NICHT gesichert — nur die Text-Tags."
        ))

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self._fmt_json = QPushButton("JSON")
        self._fmt_json.setCheckable(True)
        self._fmt_json.setChecked(True)
        self._fmt_xml = QPushButton("XML")
        self._fmt_xml.setCheckable(True)
        self._fmt_json.clicked.connect(lambda: self._fmt_xml.setChecked(False))
        self._fmt_xml.clicked.connect(lambda: self._fmt_json.setChecked(False))
        fmt_row.addWidget(self._fmt_json)
        fmt_row.addWidget(self._fmt_xml)
        fmt_row.addStretch()
        backup_layout.addLayout(fmt_row)

        btn_backup = QPushButton("Backup erstellen …")
        btn_backup.clicked.connect(self._create_backup)
        backup_layout.addWidget(btn_backup)
        layout.addWidget(backup_group)

        # ── Restore ──
        restore_group = QGroupBox("Backup wiederherstellen")
        restore_layout = QVBoxLayout(restore_group)
        restore_layout.addWidget(QLabel(
            "Stellt Tags aus einer Backup-Datei (JSON oder XML) wieder her.\n"
            "⚠ Vorhandene Tags werden überschrieben."
        ))
        self._skip_missing = QCheckBox("Fehlende Dateien überspringen")
        self._skip_missing.setChecked(True)
        restore_layout.addWidget(self._skip_missing)
        btn_restore = QPushButton("Backup laden und wiederherstellen …")
        btn_restore.clicked.connect(self._restore_backup)
        restore_layout.addWidget(btn_restore)
        layout.addWidget(restore_group)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setPlaceholderText("Log …")
        layout.addWidget(self._log)

        layout.addStretch()

    def _create_backup(self):
        tracks = self.db.get_all_tracks()
        if not tracks:
            QMessageBox.information(self, "Keine Tracks", "Die Library ist leer.")
            return
        fmt = "xml" if self._fmt_xml.isChecked() else "json"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_name = f"sonoteko_backup_{timestamp}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup speichern", default_name,
            "JSON (*.json);;XML (*.xml)"
        )
        if not path:
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, len(tracks))
        self._log.append(f"Backup startet: {len(tracks)} Tracks …")
        self._worker = BackupWorker(tracks, path, fmt)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_backup_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _restore_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Backup-Datei öffnen", "",
            "Backup-Dateien (*.json *.xml)"
        )
        if not path:
            return
        reply = QMessageBox.warning(
            self,
            "Tags überschreiben?",
            "Alle gesicherten Tags werden in die Dateien zurückgeschrieben.\n"
            "Bestehende Tags werden überschrieben.\n\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._log.append(f"Restore startet: {path}")
        self._worker = RestoreWorker(path, self._skip_missing.isChecked())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_restore_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int, path: str):
        self._progress.setRange(0, total)
        self._progress.setValue(current)

    def _on_backup_finished(self, output_path: str):
        self._progress.setVisible(False)
        self._log.append(f"✓ Backup gespeichert: {output_path}")
        QMessageBox.information(self, "Backup", f"Backup gespeichert:\n{output_path}")

    def _on_restore_finished(self, restored: int, skipped: int):
        self._progress.setVisible(False)
        self._log.append(f"✓ Restore: {restored} wiederhergestellt, {skipped} übersprungen")
        QMessageBox.information(
            self, "Restore",
            f"{restored} Tracks wiederhergestellt.\n{skipped} übersprungen."
        )

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._log.append(f"✗ Fehler: {msg}")
        QMessageBox.critical(self, "Fehler", msg)
