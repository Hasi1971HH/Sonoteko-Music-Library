"""Sonoteko Hauptfenster."""

import os
from typing import Optional

from PyQt6.QtCore import Qt, QSettings, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QStatusBar, QToolBar, QLabel, QMessageBox,
    QFileDialog, QApplication, QDockWidget
)
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QPixmap

from sonoteko import APP_NAME, __version__
from sonoteko.database import LibraryDatabase
from sonoteko.library_view import LibraryView
from sonoteko.tag_editor_panel import TagEditorPanel
from sonoteko.player_widget import PlayerWidget
from sonoteko.online_panel import OnlinePanel
from sonoteko.playlist_manager import PlaylistManager
from sonoteko.export_manager import ExportPanel
from sonoteko.backup_manager import BackupPanel
from sonoteko.replaygain import ReplayGainPanel


STYLE = """
QMainWindow, QWidget {
    background: #12121e;
    color: #ddd;
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #1e3a5f;
    border-radius: 4px;
}
QTabBar::tab {
    background: #1a1a2e;
    color: #aaa;
    padding: 6px 14px;
    border: 1px solid #1e3a5f;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
}
QTabBar::tab:selected {
    background: #0f3460;
    color: #fff;
}
QTabBar::tab:hover {
    background: #16213e;
    color: #ddd;
}
QGroupBox {
    border: 1px solid #1e3a5f;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 6px;
    color: #ccc;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
}
QLineEdit, QTextEdit {
    background: #1a1a2e;
    border: 1px solid #2a3a5e;
    border-radius: 3px;
    color: #eee;
    padding: 3px 6px;
    selection-background-color: #e94560;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #e94560;
}
QPushButton {
    background: #0f3460;
    color: #eee;
    border: 1px solid #1e5080;
    border-radius: 4px;
    padding: 5px 12px;
}
QPushButton:hover { background: #1a4a7a; }
QPushButton:pressed { background: #0a2a50; }
QPushButton:disabled { background: #1a1a2e; color: #555; border-color: #333; }
QTableView {
    background: #12121e;
    alternate-background-color: #161626;
    gridline-color: #1e2a3e;
    selection-background-color: #0f3460;
    selection-color: #fff;
}
QHeaderView::section {
    background: #0f3460;
    color: #ccc;
    padding: 4px 8px;
    border: none;
    border-right: 1px solid #1e5080;
    font-weight: bold;
}
QScrollBar:vertical {
    background: #1a1a2e;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #0f3460;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #e94560; }
QScrollBar:horizontal {
    background: #1a1a2e;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #0f3460;
    border-radius: 5px;
}
QSplitter::handle { background: #1e3a5f; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QStatusBar {
    background: #0d0d1a;
    color: #888;
    font-size: 11px;
}
QToolBar {
    background: #0d0d1a;
    border-bottom: 1px solid #1e3a5f;
    spacing: 4px;
    padding: 2px;
}
QToolBar QToolButton {
    background: transparent;
    color: #ccc;
    border: none;
    padding: 4px 8px;
    border-radius: 3px;
}
QToolBar QToolButton:hover { background: #1a3a5e; color: #fff; }
QListWidget {
    background: #12121e;
    alternate-background-color: #161626;
    border: 1px solid #1e3a5f;
    border-radius: 3px;
}
QListWidget::item:selected {
    background: #0f3460;
    color: #fff;
}
QListWidget::item:hover { background: #1a2a4e; }
QCheckBox { color: #ccc; }
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #2a4a7e;
    border-radius: 2px;
    background: #1a1a2e;
}
QCheckBox::indicator:checked {
    background: #e94560;
    border-color: #e94560;
}
QProgressBar {
    background: #1a1a2e;
    border: 1px solid #1e3a5f;
    border-radius: 3px;
    text-align: center;
    color: #888;
}
QProgressBar::chunk {
    background: #e94560;
    border-radius: 2px;
}
QMessageBox { background: #1a1a2e; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = LibraryDatabase()
        self._current_tracks = []
        self._setup_window()
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._restore_geometry()

    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setMinimumSize(1024, 680)
        self.resize(1280, 800)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Main splitter: left sidebar | center content | right panel ──
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Center: stacked tabs ──
        self._center_tabs = QTabWidget()
        self._center_tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Library tab
        self._library_view = LibraryView(self.db)
        self._library_view.tracks_selected.connect(self._on_tracks_selected)
        self._library_view.track_activated.connect(self._on_track_activated)
        self._library_view.scan_finished.connect(self._on_scan_finished)
        self._center_tabs.addTab(self._library_view, "Library")

        # Playlists tab
        self._playlist_mgr = PlaylistManager(self.db)
        self._playlist_mgr.track_activated.connect(self._on_track_activated)
        self._center_tabs.addTab(self._playlist_mgr, "Playlists")

        # Export tab
        self._export_panel = ExportPanel(self.db)
        self._center_tabs.addTab(self._export_panel, "Export")

        # Backup tab
        self._backup_panel = BackupPanel(self.db)
        self._center_tabs.addTab(self._backup_panel, "Backup")

        self._main_splitter.addWidget(self._center_tabs)

        # ── Right panel: Tag Editor + Online ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._right_tabs = QTabWidget()

        # Tag Editor
        self._tag_editor = TagEditorPanel()
        self._tag_editor.tags_saved.connect(self._on_tags_saved)
        self._right_tabs.addTab(self._tag_editor, "Tag-Editor")

        # Online
        self._online_panel = OnlinePanel()
        self._online_panel.tags_ready.connect(self._on_online_tags_ready)
        self._online_panel.cover_ready.connect(self._on_online_cover_ready)
        self._online_panel.lyrics_ready.connect(self._on_online_lyrics_ready)
        self._right_tabs.addTab(self._online_panel, "Online")

        # ReplayGain
        self._rg_panel = ReplayGainPanel(self.db)
        self._right_tabs.addTab(self._rg_panel, "ReplayGain")

        right_layout.addWidget(self._right_tabs)
        right_panel.setMinimumWidth(360)

        self._main_splitter.addWidget(right_panel)
        self._main_splitter.setSizes([720, 420])
        self._main_splitter.setStretchFactor(0, 1)

        root_layout.addWidget(self._main_splitter, stretch=1)

        # ── Player ──
        self._player = PlayerWidget()
        root_layout.addWidget(self._player)

        # ── Status bar ──
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._track_count_status = QLabel()
        self._status.addPermanentWidget(self._track_count_status)
        self._update_status()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _setup_menu(self):
        menubar = self.menuBar()

        # Datei
        file_menu = menubar.addMenu("Datei")
        act_open_files = QAction("Dateien öffnen …", self)
        act_open_files.setShortcut(QKeySequence.StandardKey.Open)
        act_open_files.triggered.connect(self._open_files)
        file_menu.addAction(act_open_files)

        act_open_dir = QAction("Ordner hinzufügen …", self)
        act_open_dir.triggered.connect(self._open_directory)
        file_menu.addAction(act_open_dir)

        file_menu.addSeparator()
        act_quit = QAction("Beenden", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Library
        lib_menu = menubar.addMenu("Library")
        act_rescan = QAction("Library aktualisieren", self)
        act_rescan.setShortcut("Ctrl+R")
        act_rescan.triggered.connect(self._library_view.refresh)
        lib_menu.addAction(act_rescan)

        act_cleanup = QAction("Fehlende Tracks entfernen", self)
        act_cleanup.triggered.connect(self._library_view._cleanup_missing)
        lib_menu.addAction(act_cleanup)

        # Playlist
        pl_menu = menubar.addMenu("Playlist")
        act_new_pl = QAction("Neue Playlist …", self)
        act_new_pl.triggered.connect(self._playlist_mgr._create_playlist)
        pl_menu.addAction(act_new_pl)

        act_add_to_pl = QAction("Auswahl zu Playlist hinzufügen", self)
        act_add_to_pl.triggered.connect(self._add_to_playlist)
        pl_menu.addAction(act_add_to_pl)

        # Info
        help_menu = menubar.addMenu("Hilfe")
        act_about = QAction(f"Über {APP_NAME}", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _setup_toolbar(self):
        tb = QToolBar("Hauptwerkzeuge")
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        act_open = QAction("📂  Ordner", self)
        act_open.setToolTip("Ordner zur Library hinzufügen")
        act_open.triggered.connect(self._open_directory)
        tb.addAction(act_open)

        act_files = QAction("🎵  Dateien", self)
        act_files.setToolTip("Einzelne Dateien öffnen")
        act_files.triggered.connect(self._open_files)
        tb.addAction(act_files)

        tb.addSeparator()

        act_save = QAction("💾  Speichern", self)
        act_save.setToolTip("Tags speichern (Ctrl+S)")
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._tag_editor._save)
        tb.addAction(act_save)

        tb.addSeparator()

        act_online = QAction("🔍  Online", self)
        act_online.setToolTip("Online-Panel öffnen (MusicBrainz, AcoustID, Lyrics)")
        act_online.triggered.connect(
            lambda: self._right_tabs.setCurrentWidget(self._online_panel)
        )
        tb.addAction(act_online)

        act_pl = QAction("🎧  Playlist", self)
        act_pl.setToolTip("Zu Playlist hinzufügen")
        act_pl.triggered.connect(self._add_to_playlist)
        tb.addAction(act_pl)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Dateien öffnen",
            filter="Audio-Dateien (*.mp3 *.flac *.ogg *.m4a *.aac)"
        )
        if paths:
            self._tag_editor.load_files(paths)
            self._right_tabs.setCurrentWidget(self._tag_editor)

    def _open_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner öffnen")
        if folder:
            self._library_view.start_scan([folder])
            self._center_tabs.setCurrentWidget(self._library_view)

    def _on_tracks_selected(self, tracks):
        self._current_tracks = tracks
        if tracks:
            paths = [t.path for t in tracks]
            self._tag_editor.load_files(paths)
            self._rg_panel.set_selected_tracks(tracks)
            if len(tracks) == 1:
                t = tracks[0]
                self._online_panel.set_current_track(
                    t.title, t.artist, t.album, t.path
                )

    def _on_track_activated(self, track):
        self._player.set_playlist([track])
        self._player._playlist_index = 0
        self._player.play_file(track.path, track.title, track.artist)
        self.db.update_play_count(track.path)

    def _on_tags_saved(self, paths: list[str]):
        self._library_view.refresh()
        self._update_status(f"Gespeichert: {len(paths)} Track(s)")

    def _on_scan_finished(self, added: int, updated: int):
        self._update_status(f"Scan: {added} neu, {updated} aktualisiert")

    def _on_online_tags_ready(self, tags: dict):
        for field, value in tags.items():
            self._tag_editor.set_tag(field, value)
        self._right_tabs.setCurrentWidget(self._tag_editor)
        self._status.showMessage("Tags von Online-Quelle übernommen. Bitte prüfen und speichern.", 5000)

    def _on_online_cover_ready(self, data: bytes, mime: str):
        self._tag_editor.set_cover(data, mime)
        self._right_tabs.setCurrentWidget(self._tag_editor)
        self._status.showMessage("Cover geladen. Bitte speichern.", 5000)

    def _on_online_lyrics_ready(self, text: str):
        self._tag_editor.set_tag("lyrics", text)
        self._right_tabs.setCurrentWidget(self._tag_editor)

    def _add_to_playlist(self):
        if not self._current_tracks:
            return
        self._playlist_mgr.add_tracks(self._current_tracks)
        self._center_tabs.setCurrentWidget(self._playlist_mgr)

    def _update_status(self, message: str = ""):
        stats = self.db.get_stats()
        total = stats.get("total_tracks", 0)
        artists = stats.get("total_artists", 0)
        albums = stats.get("total_albums", 0)
        self._track_count_status.setText(
            f"{total} Tracks  ·  {artists} Künstler  ·  {albums} Alben"
        )
        if message:
            self._status.showMessage(message, 4000)

    # ── Drag & Drop auf Hauptfenster ──────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        dirs = []
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                dirs.append(path)
            elif os.path.isfile(path):
                files.append(path)
        if dirs:
            self._library_view.start_scan(dirs)
        if files:
            self._tag_editor.load_files(files)
            self._right_tabs.setCurrentWidget(self._tag_editor)

    # ── About ─────────────────────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self,
            f"Über {APP_NAME}",
            f"<h2>{APP_NAME} {__version__}</h2>"
            "<p>Musik-Library-Software mit Tag-Editor,<br>"
            "MusicBrainz-Anbindung, AcoustID, Lyrics,<br>"
            "ReplayGain, Playlists und mehr.</p>"
            "<p>Gebaut mit Python · PyQt6 · Mutagen</p>"
            "<p><a href='https://github.com/Hasi1971HH/Sonoteko-Music-Library'>"
            "github.com/Hasi1971HH/Sonoteko-Music-Library</a></p>"
        )

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _restore_geometry(self):
        settings = QSettings("Sonoteko", APP_NAME)
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        splitter_state = settings.value("splitter")
        if splitter_state:
            self._main_splitter.restoreState(splitter_state)

    def closeEvent(self, event):
        settings = QSettings("Sonoteko", APP_NAME)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("splitter", self._main_splitter.saveState())
        self.db.close()
        event.accept()
