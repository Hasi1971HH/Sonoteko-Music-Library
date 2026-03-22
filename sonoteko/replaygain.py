"""ReplayGain-Analyse und Tag-Schreiben via ffmpeg oder rgain3."""

import os
import subprocess
import json
import re
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QTextEdit, QCheckBox, QMessageBox, QRadioButton,
    QButtonGroup
)

from .database import LibraryDatabase, TrackRecord
from .tag_handler import write_tags, read_tags


# ── Analysis ───────────────────────────────────────────────────────────────────

def _find_ffmpeg() -> Optional[str]:
    for candidate in ["ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        try:
            result = subprocess.run(
                [candidate, "-version"], capture_output=True, timeout=3
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def analyze_replaygain_ffmpeg(filepath: str) -> Optional[dict]:
    """
    Analysiert ReplayGain via ffmpeg ebur128 filter.
    Gibt dict mit track_gain, track_peak zurück oder None.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None
    try:
        result = subprocess.run(
            [
                ffmpeg, "-i", filepath,
                "-filter:a", "ebur128=peak=sample",
                "-f", "null", "-"
            ],
            capture_output=True, text=True, timeout=120
        )
        output = result.stderr
        # Parse integrated loudness (I)
        integrated = re.search(r"I:\s*([-\d.]+)\s*LUFS", output)
        # Parse true peak
        peak = re.search(r"Peak:\s*([-\d.]+)\s*dBFS", output)

        if not integrated:
            return None

        loudness = float(integrated.group(1))
        # ReplayGain target is -18 LUFS (EBU R128 reference -23, but RG uses -18)
        target_loudness = -18.0
        gain = target_loudness - loudness

        peak_dbfs = float(peak.group(1)) if peak else 0.0
        # Convert dBFS to linear
        import math
        peak_linear = 10 ** (peak_dbfs / 20)

        return {
            "track_gain": f"{gain:+.2f} dB",
            "track_peak": f"{peak_linear:.6f}",
            "loudness_lufs": loudness,
        }
    except Exception as e:
        print(f"[replaygain] ffmpeg error for {filepath}: {e}")
        return None


# ── Worker ─────────────────────────────────────────────────────────────────────

class ReplayGainWorker(QThread):
    progress = pyqtSignal(int, int, str)
    track_done = pyqtSignal(str, str, str)   # path, gain, peak
    finished = pyqtSignal(int, int)           # done, failed
    error = pyqtSignal(str)

    def __init__(self, tracks: list[TrackRecord], write_to_file: bool = True,
                 parent=None):
        super().__init__(parent)
        self.tracks = tracks
        self.write_to_file = write_to_file
        self._abort = False

    def run(self):
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            self.error.emit(
                "ffmpeg nicht gefunden.\n"
                "Bitte installieren: brew install ffmpeg"
            )
            return

        total = len(self.tracks)
        done = failed = 0

        for i, track in enumerate(self.tracks):
            if self._abort:
                break
            self.progress.emit(i + 1, total, track.path)
            rg = analyze_replaygain_ffmpeg(track.path)
            if rg is None:
                failed += 1
                continue
            gain = rg["track_gain"]
            peak = rg["track_peak"]
            if self.write_to_file:
                tags = read_tags(track.path).tags
                tags["replaygain_track_gain"] = gain
                tags["replaygain_track_peak"] = peak
                write_tags(track.path, tags)
            self.track_done.emit(track.path, gain, peak)
            done += 1

        self.finished.emit(done, failed)

    def abort(self):
        self._abort = True


# ── UI Panel ──────────────────────────────────────────────────────────────────

class ReplayGainPanel(QWidget):
    def __init__(self, db: LibraryDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self._worker: Optional[ReplayGainWorker] = None
        self._pending_tracks: list[TrackRecord] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(
            "ReplayGain analysiert die wahrgenommene Lautstärke und schreibt\n"
            "Gain- und Peak-Werte direkt in die Audio-Tags.\n\n"
            "Voraussetzung: ffmpeg muss installiert sein."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Options
        self._write_check = QCheckBox("Werte direkt in Tags schreiben")
        self._write_check.setChecked(True)
        layout.addWidget(self._write_check)

        # Buttons
        btn_row = QHBoxLayout()
        self._btn_selected = QPushButton("Ausgewählte Tracks analysieren")
        self._btn_selected.clicked.connect(self._analyze_selected)
        btn_row.addWidget(self._btn_selected)

        self._btn_all = QPushButton("Gesamte Library analysieren")
        self._btn_all.clicked.connect(self._analyze_all)
        btn_row.addWidget(self._btn_all)

        self._btn_abort = QPushButton("Abbrechen")
        self._btn_abort.setEnabled(False)
        self._btn_abort.clicked.connect(self._abort)
        btn_row.addWidget(self._btn_abort)
        layout.addLayout(btn_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel()
        self._status.setStyleSheet("color: #888;")
        layout.addWidget(self._status)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Ergebnisse erscheinen hier …")
        layout.addWidget(self._log)

    def set_selected_tracks(self, tracks: list[TrackRecord]):
        self._pending_tracks = tracks
        self._btn_selected.setText(
            f"Ausgewählte Tracks analysieren ({len(tracks)})"
        )
        self._btn_selected.setEnabled(len(tracks) > 0)

    def _analyze_selected(self):
        if not self._pending_tracks:
            return
        self._start_analysis(self._pending_tracks)

    def _analyze_all(self):
        tracks = self.db.get_all_tracks()
        if not tracks:
            QMessageBox.information(self, "Keine Tracks", "Die Library ist leer.")
            return
        reply = QMessageBox.question(
            self,
            "Gesamte Library analysieren?",
            f"{len(tracks)} Tracks analysieren? Das kann je nach Library länger dauern.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_analysis(tracks)

    def _start_analysis(self, tracks: list[TrackRecord]):
        self._progress.setVisible(True)
        self._progress.setRange(0, len(tracks))
        self._btn_all.setEnabled(False)
        self._btn_selected.setEnabled(False)
        self._btn_abort.setEnabled(True)
        self._log.append(f"Analyse startet: {len(tracks)} Tracks …")

        self._worker = ReplayGainWorker(
            tracks, write_to_file=self._write_check.isChecked()
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.track_done.connect(self._on_track_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int, path: str):
        self._progress.setValue(current)
        name = os.path.basename(path)
        self._status.setText(f"Analysiere: {name}  ({current}/{total})")

    def _on_track_done(self, path: str, gain: str, peak: str):
        name = os.path.basename(path)
        self._log.append(f"✓  {name}  →  Gain: {gain}  Peak: {peak}")

    def _on_finished(self, done: int, failed: int):
        self._progress.setVisible(False)
        self._btn_all.setEnabled(True)
        self._btn_selected.setEnabled(True)
        self._btn_abort.setEnabled(False)
        msg = f"Fertig: {done} analysiert"
        if failed:
            msg += f", {failed} fehlgeschlagen"
        self._status.setText(msg)
        self._log.append(f"\n{msg}")

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._btn_all.setEnabled(True)
        self._btn_selected.setEnabled(True)
        self._btn_abort.setEnabled(False)
        self._status.setText(f"Fehler: {msg}")
        QMessageBox.critical(self, "Fehler", msg)

    def _abort(self):
        if self._worker:
            self._worker.abort()
        self._btn_abort.setEnabled(False)
        self._status.setText("Abgebrochen.")
