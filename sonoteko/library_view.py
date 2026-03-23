"""Library-Tabelle mit Scan-Worker und Filter-Funktion."""

import os
import time
from typing import Optional

from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
    QThread, pyqtSignal, QMimeData, QUrl
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QLineEdit, QPushButton, QLabel, QAbstractItemView, QMenu,
    QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtGui import QAction, QKeySequence, QColor, QBrush

from sonoteko.database import LibraryDatabase, TrackRecord
from sonoteko.tag_handler import read_tags, format_duration


# ── Scan-Worker ───────────────────────────────────────────────────────────────

class ScanWorker(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, path
    finished = pyqtSignal(int, int)        # added, updated

    def __init__(self, directories: list[str], db: LibraryDatabase, parent=None):
        super().__init__(parent)
        self.directories = directories
        self.db = db
        self._abort = False

    def run(self):
        from sonoteko.tag_handler import scan_directory
        all_files: list[str] = []
        for d in self.directories:
            all_files.extend(scan_directory(d))

        total = len(all_files)
        added = updated = 0

        for i, filepath in enumerate(all_files):
            if self._abort:
                break
            self.progress.emit(i + 1, total, filepath)
            try:
                mtime = os.path.getmtime(filepath)
                existing = self.db.get_track(filepath)
                if existing and existing.date_modified >= mtime:
                    continue
                info = read_tags(filepath)
                rec = TrackRecord(
                    path=filepath,
                    title=info.tags.get("title", ""),
                    artist=info.tags.get("artist", ""),
                    album=info.tags.get("album", ""),
                    albumartist=info.tags.get("albumartist", ""),
                    year=info.tags.get("date", ""),
                    genre=info.tags.get("genre", ""),
                    tracknumber=info.tags.get("tracknumber", ""),
                    discnumber=info.tags.get("discnumber", ""),
                    composer=info.tags.get("composer", ""),
                    comment=info.tags.get("comment", ""),
                    bpm=info.tags.get("bpm", ""),
                    isrc=info.tags.get("isrc", ""),
                    duration=info.audio_info.duration,
                    bitrate=info.audio_info.bitrate,
                    samplerate=info.audio_info.samplerate,
                    channels=info.audio_info.channels,
                    format=info.audio_info.format,
                    filesize=info.audio_info.filesize,
                    has_cover=info.cover_data is not None,
                    replaygain_track_gain=info.tags.get("replaygain_track_gain", ""),
                    replaygain_track_peak=info.tags.get("replaygain_track_peak", ""),
                    replaygain_album_gain=info.tags.get("replaygain_album_gain", ""),
                    replaygain_album_peak=info.tags.get("replaygain_album_peak", ""),
                    date_added=time.time() if existing is None else existing.date_added,
                    date_modified=mtime,
                )
                self.db.upsert_track(rec)
                if existing is None:
                    added += 1
                else:
                    updated += 1
            except Exception as e:
                print(f"[ScanWorker] {filepath}: {e}")

        self.finished.emit(added, updated)

    def abort(self):
        self._abort = True


# ── Tabellen-Modell ───────────────────────────────────────────────────────────

COLUMNS = [
    ("title",       "Titel"),
    ("artist",      "Künstler"),
    ("album",       "Album"),
    ("year",        "Jahr"),
    ("genre",       "Genre"),
    ("duration",    "Dauer"),
    ("bitrate",     "kbps"),
    ("format",      "Format"),
    ("tracknumber", "Nr."),
    ("has_cover",   "Cover"),
    ("path",        "Pfad"),
]
COL_IDX = {name: i for i, (name, _) in enumerate(COLUMNS)}


class LibraryModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[TrackRecord] = []

    def set_tracks(self, tracks: list[TrackRecord]):
        self.beginResetModel()
        self._tracks = tracks
        self.endResetModel()

    def track_at(self, row: int) -> Optional[TrackRecord]:
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def track_for_index(self, index: QModelIndex) -> Optional[TrackRecord]:
        return self.track_at(index.row())

    # ── QAbstractTableModel interface ─────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._tracks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        track = self._tracks[index.row()]
        col_name = COLUMNS[index.column()][0]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_name == "duration":
                return format_duration(track.duration)
            if col_name == "has_cover":
                return "✓" if track.has_cover else ""
            if col_name == "bitrate":
                return str(track.bitrate) if track.bitrate else ""
            return str(getattr(track, col_name, ""))

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_name == "has_cover" and track.has_cover:
                return QBrush(QColor("#4CAF50"))
            if col_name == "path":
                return QBrush(QColor("#888888"))

        if role == Qt.ItemDataRole.UserRole:
            return track

        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        col_name = COLUMNS[column][0]
        reverse = order == Qt.SortOrder.DescendingOrder
        self.beginResetModel()
        if col_name == "duration":
            self._tracks.sort(key=lambda t: t.duration, reverse=reverse)
        elif col_name == "bitrate":
            self._tracks.sort(key=lambda t: t.bitrate, reverse=reverse)
        elif col_name == "tracknumber":
            def track_num(t):
                try:
                    return int(t.tracknumber.split("/")[0])
                except (ValueError, AttributeError):
                    return 0
            self._tracks.sort(key=track_num, reverse=reverse)
        else:
            self._tracks.sort(
                key=lambda t: str(getattr(t, col_name, "")).lower(),
                reverse=reverse
            )
        self.endResetModel()


# ── Library-Widget ────────────────────────────────────────────────────────────

class LibraryView(QWidget):
    tracks_selected = pyqtSignal(list)       # list[TrackRecord]
    track_activated = pyqtSignal(object)     # TrackRecord (double click / play)
    scan_started = pyqtSignal()
    scan_finished = pyqtSignal(int, int)     # added, updated

    def __init__(self, db: LibraryDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self._worker: Optional[ScanWorker] = None
        self._setup_ui()
        self._load_from_db()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Suchen (Titel, Künstler, Album, Genre …)")
        self._search.textChanged.connect(self._on_search)
        self._search.setClearButtonEnabled(True)
        toolbar.addWidget(self._search)

        self._btn_scan = QPushButton("Ordner scannen …")
        self._btn_scan.clicked.connect(self._scan_folder)
        toolbar.addWidget(self._btn_scan)

        self._btn_cleanup = QPushButton("Fehlende entfernen")
        self._btn_cleanup.setToolTip("Entfernt Tracks aus der Library, deren Datei nicht mehr existiert")
        self._btn_cleanup.clicked.connect(self._cleanup_missing)
        toolbar.addWidget(self._btn_cleanup)

        layout.addLayout(toolbar)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(4)
        layout.addWidget(self._progress)

        self._status_label = QLabel()
        self._status_label.setVisible(False)
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status_label)

        # ── Tabelle ──
        self._model = LibraryModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            COL_IDX["title"], QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            COL_IDX["path"], QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setColumnWidth(COL_IDX["has_cover"], 50)
        self._table.setColumnWidth(COL_IDX["bitrate"], 50)
        self._table.setColumnWidth(COL_IDX["format"], 55)
        self._table.setColumnWidth(COL_IDX["tracknumber"], 40)
        self._table.setColumnWidth(COL_IDX["duration"], 55)
        self._table.setColumnWidth(COL_IDX["year"], 48)
        self._table.verticalHeader().setDefaultSectionSize(22)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        # Drag & Drop for adding files
        self._table.setAcceptDrops(True)
        self._table.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

        layout.addWidget(self._table)

        # ── Footer ──
        footer = QHBoxLayout()
        self._track_count_label = QLabel()
        footer.addWidget(self._track_count_label)
        footer.addStretch()
        layout.addLayout(footer)

        self._update_count_label()

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_from_db(self):
        tracks = self.db.get_all_tracks()
        self._model.set_tracks(tracks)
        self._update_count_label()

    def refresh(self):
        self._load_from_db()

    def show_tracks(self, tracks: list[TrackRecord]):
        self._model.set_tracks(tracks)
        self._update_count_label()

    # ── Scanning ─────────────────────────────────────────────────────────────

    def _scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner für Scan auswählen")
        if folder:
            self.start_scan([folder])

    def start_scan(self, directories: list[str]):
        if self._worker and self._worker.isRunning():
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._status_label.setVisible(True)
        self._btn_scan.setEnabled(False)
        self.scan_started.emit()

        self._worker = ScanWorker(directories, self.db)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()

    def _on_scan_progress(self, current: int, total: int, path: str):
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        name = os.path.basename(path)
        self._status_label.setText(f"Scanne: {name}  ({current}/{total})")

    def _on_scan_finished(self, added: int, updated: int):
        self._progress.setVisible(False)
        self._status_label.setVisible(False)
        self._btn_scan.setEnabled(True)
        self._load_from_db()
        self.scan_finished.emit(added, updated)

    def _cleanup_missing(self):
        removed = self.db.delete_missing_tracks()
        self._load_from_db()
        QMessageBox.information(self, "Bereinigung", f"{removed} fehlende Tracks entfernt.")

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search(self, text: str):
        self._proxy.setFilterFixedString(text)
        self._update_count_label()

    # ── Selection ─────────────────────────────────────────────────────────────

    def _on_selection(self, *_):
        records = self._selected_records()
        self.tracks_selected.emit(records)

    def _on_double_click(self, proxy_index: QModelIndex):
        source_index = self._proxy.mapToSource(proxy_index)
        track = self._model.track_at(source_index.row())
        if track:
            self.track_activated.emit(track)

    def _selected_records(self) -> list[TrackRecord]:
        rows = {
            self._proxy.mapToSource(idx).row()
            for idx in self._table.selectedIndexes()
        }
        return [self._model.track_at(r) for r in rows if self._model.track_at(r)]

    def selected_tracks(self) -> list[TrackRecord]:
        return self._selected_records()

    # ── Context menu ──────────────────────────────────────────────────────────

    def _context_menu(self, pos):
        records = self._selected_records()
        if not records:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("Tags bearbeiten …")
        act_play = menu.addAction("Abspielen")
        menu.addSeparator()
        act_reveal = menu.addAction("Im Finder zeigen")
        act_remove = menu.addAction("Aus Library entfernen")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == act_edit:
            self.tracks_selected.emit(records)
        elif action == act_play and records:
            self.track_activated.emit(records[0])
        elif action == act_reveal and records:
            self._reveal_in_finder(records[0].path)
        elif action == act_remove:
            for r in records:
                self.db.delete_track(r.path)
            self._load_from_db()

    def _reveal_in_finder(self, path: str):
        import subprocess
        subprocess.Popen(["open", "-R", path])

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        dirs = []
        files = []
        for url in urls:
            path = url.toLocalFile()
            if os.path.isdir(path):
                dirs.append(path)
            elif os.path.isfile(path):
                files.append(path)
        if dirs:
            self.start_scan(dirs)
        if files:
            self.start_scan([os.path.dirname(f) for f in files])

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_count_label(self):
        visible = self._proxy.rowCount()
        total = self._model.rowCount()
        if visible == total:
            self._track_count_label.setText(f"{total} Tracks")
        else:
            self._track_count_label.setText(f"{visible} von {total} Tracks")
