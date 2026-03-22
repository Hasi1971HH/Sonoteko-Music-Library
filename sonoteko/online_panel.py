"""Online-Panel: MusicBrainz, Cover Art Archive, AcoustID, LRClib Lyrics."""

import os
import hashlib
import subprocess
import tempfile
from typing import Optional

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLineEdit, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QTextEdit, QProgressBar, QGroupBox, QFormLayout, QCheckBox,
    QMessageBox, QSplitter
)
from PyQt6.QtGui import QPixmap, QImage

MB_BASE = "https://musicbrainz.org/ws/2"
CAA_BASE = "https://coverartarchive.org"
ACOUSTID_BASE = "https://api.acoustid.org/v2"
LRCLIB_BASE = "https://lrclib.net/api"
HEADERS = {"User-Agent": "Sonoteko/2.0 (https://github.com/Hasi1971HH/Sonoteko-Music-Library)"}


# ── Worker-Threads ────────────────────────────────────────────────────────────

class MusicBrainzSearchWorker(QThread):
    result = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, search_type: str = "recording", parent=None):
        super().__init__(parent)
        self.query = query
        self.search_type = search_type

    def run(self):
        try:
            params = {
                "query": self.query,
                "fmt": "json",
                "limit": 25,
            }
            resp = requests.get(
                f"{MB_BASE}/{self.search_type}",
                params=params,
                headers=HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            key = self.search_type + "s"
            self.result.emit(data.get(key, []))
        except Exception as e:
            self.error.emit(str(e))


class CoverFetchWorker(QThread):
    cover_ready = pyqtSignal(bytes, str)   # data, mime
    error = pyqtSignal(str)

    def __init__(self, mbid: str, parent=None):
        super().__init__(parent)
        self.mbid = mbid

    def run(self):
        try:
            resp = requests.get(
                f"{CAA_BASE}/release/{self.mbid}/front-500",
                headers=HEADERS,
                timeout=15,
                allow_redirects=True,
            )
            resp.raise_for_status()
            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
            self.cover_ready.emit(resp.content, mime)
        except Exception as e:
            self.error.emit(str(e))


class AcoustIDWorker(QThread):
    result = pyqtSignal(list)   # list of dicts with id, title, artist
    error = pyqtSignal(str)

    def __init__(self, filepath: str, api_key: str = "8XaBELgH", parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.api_key = api_key

    def run(self):
        try:
            # Try fpcalc
            fpcalc = self._find_fpcalc()
            if not fpcalc:
                self.error.emit(
                    "fpcalc nicht gefunden. Bitte Chromaprint installieren:\n"
                    "  brew install chromaprint"
                )
                return
            proc = subprocess.run(
                [fpcalc, "-json", self.filepath],
                capture_output=True, text=True, timeout=30
            )
            import json
            fp_data = json.loads(proc.stdout)
            duration = fp_data.get("duration", 0)
            fingerprint = fp_data.get("fingerprint", "")
            if not fingerprint:
                self.error.emit("Fingerprint konnte nicht berechnet werden.")
                return
            resp = requests.get(
                f"{ACOUSTID_BASE}/lookup",
                params={
                    "client": self.api_key,
                    "duration": int(duration),
                    "fingerprint": fingerprint,
                    "meta": "recordings+releasegroups+compress",
                },
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            parsed = []
            for r in results[:5]:
                score = r.get("score", 0)
                for rec in r.get("recordings", [])[:3]:
                    artists = ", ".join(a.get("name", "") for a in rec.get("artists", []))
                    parsed.append({
                        "score": score,
                        "title": rec.get("title", ""),
                        "artist": artists,
                        "mbid": rec.get("id", ""),
                    })
            self.result.emit(parsed)
        except Exception as e:
            self.error.emit(str(e))

    def _find_fpcalc(self) -> Optional[str]:
        for candidate in ["fpcalc", "/usr/local/bin/fpcalc", "/opt/homebrew/bin/fpcalc"]:
            try:
                subprocess.run([candidate, "--version"], capture_output=True, timeout=3)
                return candidate
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None


class LyricsWorker(QThread):
    result = pyqtSignal(str, bool)   # text, is_synced
    error = pyqtSignal(str)

    def __init__(self, title: str, artist: str, album: str = "",
                 duration: int = 0, parent=None):
        super().__init__(parent)
        self.title = title
        self.artist = artist
        self.album = album
        self.duration = duration

    def run(self):
        try:
            params = {
                "track_name": self.title,
                "artist_name": self.artist,
            }
            if self.album:
                params["album_name"] = self.album
            if self.duration:
                params["duration"] = self.duration
            resp = requests.get(
                f"{LRCLIB_BASE}/get",
                params=params,
                headers=HEADERS,
                timeout=10,
            )
            if resp.status_code == 404:
                self.error.emit("Keine Lyrics gefunden.")
                return
            resp.raise_for_status()
            data = resp.json()
            synced = data.get("syncedLyrics", "")
            plain = data.get("plainLyrics", "")
            if synced:
                self.result.emit(synced, True)
            elif plain:
                self.result.emit(plain, False)
            else:
                self.error.emit("Keine Lyrics gefunden.")
        except Exception as e:
            self.error.emit(str(e))


# ── MusicBrainz Panel ─────────────────────────────────────────────────────────

class MusicBrainzPanel(QWidget):
    tags_ready = pyqtSignal(dict)
    cover_ready = pyqtSignal(bytes, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[MusicBrainzSearchWorker] = None
        self._cover_worker: Optional[CoverFetchWorker] = None
        self._results: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Künstler – Album – Titel suchen …")
        self._search_input.returnPressed.connect(self._search)
        search_row.addWidget(self._search_input)
        self._search_btn = QPushButton("Suchen")
        self._search_btn.clicked.connect(self._search)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(4)
        layout.addWidget(self._progress)

        # Splitter: results list | detail
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._result_list = QListWidget()
        self._result_list.currentRowChanged.connect(self._on_result_selected)
        splitter.addWidget(self._result_list)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(8, 0, 0, 0)

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(150, 150)
        self._cover_label.setStyleSheet("background: #111; border: 1px solid #333;")
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setText("Kein Cover")
        detail_layout.addWidget(self._cover_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setMaximumHeight(120)
        detail_layout.addWidget(self._detail_text)

        btn_row = QHBoxLayout()
        self._apply_tags_btn = QPushButton("Tags übernehmen")
        self._apply_tags_btn.clicked.connect(self._apply_tags)
        self._apply_tags_btn.setEnabled(False)
        btn_row.addWidget(self._apply_tags_btn)

        self._fetch_cover_btn = QPushButton("Cover laden")
        self._fetch_cover_btn.clicked.connect(self._fetch_cover)
        self._fetch_cover_btn.setEnabled(False)
        btn_row.addWidget(self._fetch_cover_btn)

        detail_layout.addLayout(btn_row)
        detail_layout.addStretch()
        splitter.addWidget(detail_widget)
        splitter.setSizes([300, 200])

        layout.addWidget(splitter)

        self._status = QLabel()
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status)

    def set_query(self, title: str, artist: str, album: str = ""):
        parts = []
        if title:
            parts.append(title)
        if artist:
            parts.append(artist)
        if album:
            parts.append(album)
        self._search_input.setText(" ".join(parts))

    def _search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._progress.setVisible(True)
        self._search_btn.setEnabled(False)
        self._result_list.clear()
        self._results.clear()
        self._apply_tags_btn.setEnabled(False)
        self._fetch_cover_btn.setEnabled(False)

        self._worker = MusicBrainzSearchWorker(query)
        self._worker.result.connect(self._on_search_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_search_result(self, results: list):
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._results = results
        self._result_list.clear()
        for r in results:
            # Recording result
            title = r.get("title", "")
            artists = ", ".join(a.get("name", "") for a in r.get("artist-credit", [])
                               if isinstance(a, dict))
            releases = r.get("releases", [])
            album = releases[0].get("title", "") if releases else ""
            year = ""
            if releases and releases[0].get("date"):
                year = releases[0]["date"][:4]
            text = f"{artists} – {title}"
            if album:
                text += f"  [{album}]"
            if year:
                text += f"  ({year})"
            score = r.get("score", 0)
            item = QListWidgetItem(f"[{score}%] {text}")
            self._result_list.addItem(item)

        self._status.setText(f"{len(results)} Ergebnisse")

    def _on_result_selected(self, row: int):
        if row < 0 or row >= len(self._results):
            return
        r = self._results[row]
        self._apply_tags_btn.setEnabled(True)

        title = r.get("title", "")
        artists = ", ".join(a.get("name", "") for a in r.get("artist-credit", [])
                           if isinstance(a, dict))
        releases = r.get("releases", [])
        album = releases[0].get("title", "") if releases else ""
        year = releases[0].get("date", "")[:4] if releases else ""
        mb_release_id = releases[0].get("id", "") if releases else ""

        detail = f"<b>Titel:</b> {title}<br>"
        detail += f"<b>Künstler:</b> {artists}<br>"
        if album:
            detail += f"<b>Album:</b> {album}<br>"
        if year:
            detail += f"<b>Jahr:</b> {year}<br>"
        if mb_release_id:
            detail += f"<b>MBID:</b> {mb_release_id}<br>"
            self._fetch_cover_btn.setEnabled(True)
            self._fetch_cover_btn.setProperty("mbid", mb_release_id)
        else:
            self._fetch_cover_btn.setEnabled(False)

        self._detail_text.setHtml(detail)

    def _apply_tags(self):
        row = self._result_list.currentRow()
        if row < 0 or row >= len(self._results):
            return
        r = self._results[row]
        tags = {}
        tags["title"] = r.get("title", "")
        artist_credits = r.get("artist-credit", [])
        tags["artist"] = ", ".join(
            a.get("name", "") for a in artist_credits if isinstance(a, dict)
        )
        releases = r.get("releases", [])
        if releases:
            tags["album"] = releases[0].get("title", "")
            tags["date"] = releases[0].get("date", "")[:4]
            tag_fields = releases[0].get("release-group", {}).get("tags", [])
            if tag_fields:
                tags["genre"] = tag_fields[0].get("name", "")
        track_list = r.get("releases", [{}])[0].get("media", [{}])[0].get("tracks", []) if releases else []
        if track_list:
            tags["tracknumber"] = str(track_list[0].get("number", ""))
        isrcs = r.get("isrcs", [])
        if isrcs:
            tags["isrc"] = isrcs[0]
        self.tags_ready.emit(tags)

    def _fetch_cover(self):
        mbid = self._fetch_cover_btn.property("mbid")
        if not mbid:
            return
        self._fetch_cover_btn.setEnabled(False)
        self._cover_label.setText("Lade …")
        self._cover_worker = CoverFetchWorker(mbid)
        self._cover_worker.cover_ready.connect(self._on_cover_ready)
        self._cover_worker.error.connect(self._on_cover_error)
        self._cover_worker.start()

    def _on_cover_ready(self, data: bytes, mime: str):
        self._fetch_cover_btn.setEnabled(True)
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        self._cover_label.setPixmap(
            pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        )
        self.cover_ready.emit(data, mime)

    def _on_cover_error(self, msg: str):
        self._fetch_cover_btn.setEnabled(True)
        self._cover_label.setText("Fehler")
        self._status.setText(f"Cover-Fehler: {msg}")

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status.setText(f"Fehler: {msg}")


# ── AcoustID Panel ────────────────────────────────────────────────────────────

class AcoustIDPanel(QWidget):
    tags_ready = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[AcoustIDWorker] = None
        self._current_file: Optional[str] = None
        self._results: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "AcoustID erkennt Tracks anhand des Audioinhalts — auch ohne Tags.\n"
            "Voraussetzung: Chromaprint (fpcalc) muss installiert sein."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info)

        self._file_label = QLabel("Kein Track ausgewählt")
        self._file_label.setStyleSheet("font-style: italic; color: #aaa;")
        layout.addWidget(self._file_label)

        self._btn_identify = QPushButton("Track identifizieren")
        self._btn_identify.setEnabled(False)
        self._btn_identify.clicked.connect(self._identify)
        layout.addWidget(self._btn_identify)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(4)
        layout.addWidget(self._progress)

        self._result_list = QListWidget()
        self._result_list.currentRowChanged.connect(self._on_result_selected)
        layout.addWidget(self._result_list)

        self._apply_btn = QPushButton("Tags übernehmen")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply_tags)
        layout.addWidget(self._apply_btn)

        self._status = QLabel()
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status)

    def set_file(self, filepath: str):
        self._current_file = filepath
        name = os.path.basename(filepath)
        self._file_label.setText(name)
        self._btn_identify.setEnabled(True)

    def _identify(self):
        if not self._current_file:
            return
        self._progress.setVisible(True)
        self._btn_identify.setEnabled(False)
        self._result_list.clear()
        self._results.clear()
        self._apply_btn.setEnabled(False)

        self._worker = AcoustIDWorker(self._current_file)
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, results: list):
        self._progress.setVisible(False)
        self._btn_identify.setEnabled(True)
        self._results = results
        for r in results:
            score_pct = int(r["score"] * 100)
            text = f"[{score_pct}%] {r['artist']} – {r['title']}"
            self._result_list.addItem(text)
        if results:
            self._status.setText(f"{len(results)} Treffer")
        else:
            self._status.setText("Keine Treffer gefunden.")

    def _on_result_selected(self, row: int):
        self._apply_btn.setEnabled(row >= 0 and row < len(self._results))

    def _apply_tags(self):
        row = self._result_list.currentRow()
        if row < 0 or row >= len(self._results):
            return
        r = self._results[row]
        tags = {"title": r["title"], "artist": r["artist"]}
        self.tags_ready.emit(tags)

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._btn_identify.setEnabled(True)
        self._status.setText(f"Fehler: {msg}")


# ── Lyrics Panel ─────────────────────────────────────────────────────────────

class LyricsPanel(QWidget):
    lyrics_ready = pyqtSignal(str)   # lyrics text to save to tag

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[LyricsWorker] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._title_input = QLineEdit()
        self._artist_input = QLineEdit()
        self._album_input = QLineEdit()
        form.addRow("Titel:", self._title_input)
        form.addRow("Künstler:", self._artist_input)
        form.addRow("Album (optional):", self._album_input)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._search_btn = QPushButton("Lyrics suchen")
        self._search_btn.clicked.connect(self._search)
        btn_row.addWidget(self._search_btn)
        self._save_btn = QPushButton("In Tag speichern")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_to_tag)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(4)
        layout.addWidget(self._progress)

        self._synced_check = QCheckBox("Synchronisierte Lyrics (LRC)")
        self._synced_check.setEnabled(False)
        layout.addWidget(self._synced_check)

        self._lyrics_text = QTextEdit()
        self._lyrics_text.setPlaceholderText("Lyrics erscheinen hier …")
        self._lyrics_text.setReadOnly(True)
        layout.addWidget(self._lyrics_text)

        self._status = QLabel()
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status)

    def set_track_info(self, title: str, artist: str, album: str = ""):
        self._title_input.setText(title)
        self._artist_input.setText(artist)
        self._album_input.setText(album)

    def _search(self):
        title = self._title_input.text().strip()
        artist = self._artist_input.text().strip()
        if not title or not artist:
            self._status.setText("Bitte Titel und Künstler eingeben.")
            return
        self._progress.setVisible(True)
        self._search_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._lyrics_text.clear()

        self._worker = LyricsWorker(title, artist, self._album_input.text().strip())
        self._worker.result.connect(self._on_lyrics_ready)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_lyrics_ready(self, text: str, is_synced: bool):
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._lyrics_text.setReadOnly(False)
        self._lyrics_text.setPlainText(text)
        self._lyrics_text.setReadOnly(True)
        self._synced_check.setEnabled(True)
        self._synced_check.setChecked(is_synced)
        self._status.setText("Lyrics gefunden!" + (" (synchronisiert)" if is_synced else ""))

    def _save_to_tag(self):
        text = self._lyrics_text.toPlainText()
        if text:
            self.lyrics_ready.emit(text)
            self._status.setText("Lyrics in Tag geschrieben.")

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status.setText(f"Fehler: {msg}")


# ── Online Panel (Tabs) ───────────────────────────────────────────────────────

class OnlinePanel(QWidget):
    """Container für alle Online-Features als Tab-Widget."""

    tags_ready = pyqtSignal(dict)
    cover_ready = pyqtSignal(bytes, str)
    lyrics_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()

        self._mb_panel = MusicBrainzPanel()
        self._mb_panel.tags_ready.connect(self.tags_ready)
        self._mb_panel.cover_ready.connect(self.cover_ready)
        tabs.addTab(self._mb_panel, "MusicBrainz")

        self._acoustid_panel = AcoustIDPanel()
        self._acoustid_panel.tags_ready.connect(self.tags_ready)
        tabs.addTab(self._acoustid_panel, "AcoustID")

        self._lyrics_panel = LyricsPanel()
        self._lyrics_panel.lyrics_ready.connect(self.lyrics_ready)
        tabs.addTab(self._lyrics_panel, "Lyrics")

        layout.addWidget(tabs)

    def set_current_track(self, title: str, artist: str, album: str = "",
                          filepath: str = ""):
        self._mb_panel.set_query(title, artist, album)
        self._lyrics_panel.set_track_info(title, artist, album)
        if filepath:
            self._acoustid_panel.set_file(filepath)
