"""Playlist-Manager: Erstellen, Bearbeiten, Exportieren (M3U/PLS/XSPF)."""

import os
import time
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QFileDialog, QMessageBox,
    QSplitter, QMenu, QAbstractItemView
)

from .database import LibraryDatabase, TrackRecord
from .tag_handler import format_duration


class PlaylistManager(QWidget):
    playlist_selected = pyqtSignal(list)         # list[TrackRecord]
    track_activated = pyqtSignal(object)         # TrackRecord

    def __init__(self, db: LibraryDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self._current_playlist_id: Optional[int] = None
        self._setup_ui()
        self._load_playlists()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: playlist list ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_toolbar = QHBoxLayout()
        lbl = QLabel("Playlists")
        lbl.setStyleSheet("font-weight: bold;")
        left_toolbar.addWidget(lbl)
        left_toolbar.addStretch()
        btn_new = QPushButton("+")
        btn_new.setToolTip("Neue Playlist")
        btn_new.setFixedWidth(28)
        btn_new.clicked.connect(self._create_playlist)
        left_toolbar.addWidget(btn_new)
        left_layout.addLayout(left_toolbar)

        self._playlist_list = QListWidget()
        self._playlist_list.currentRowChanged.connect(self._on_playlist_selected)
        self._playlist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._playlist_list.customContextMenuRequested.connect(self._playlist_context_menu)
        left_layout.addWidget(self._playlist_list)

        splitter.addWidget(left)

        # ── Right: track list ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_toolbar = QHBoxLayout()
        self._playlist_name_label = QLabel("Keine Playlist ausgewählt")
        self._playlist_name_label.setStyleSheet("font-weight: bold;")
        right_toolbar.addWidget(self._playlist_name_label)
        right_toolbar.addStretch()

        btn_export = QPushButton("Exportieren …")
        btn_export.clicked.connect(self._export_playlist)
        right_toolbar.addWidget(btn_export)

        btn_remove = QPushButton("Track entfernen")
        btn_remove.clicked.connect(self._remove_selected_track)
        right_toolbar.addWidget(btn_remove)

        right_layout.addLayout(right_toolbar)

        self._track_list = QListWidget()
        self._track_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._track_list.model().rowsMoved.connect(self._on_tracks_reordered)
        self._track_list.doubleClicked.connect(self._on_track_activated)
        self._track_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._track_list.customContextMenuRequested.connect(self._track_context_menu)
        right_layout.addWidget(self._track_list)

        self._duration_label = QLabel()
        self._duration_label.setStyleSheet("color: #888; font-size: 11px;")
        right_layout.addWidget(self._duration_label)

        splitter.addWidget(right)
        splitter.setSizes([180, 400])
        layout.addWidget(splitter)

    # ── Playlist management ───────────────────────────────────────────────────

    def _load_playlists(self):
        self._playlist_list.clear()
        playlists = self.db.get_all_playlists()
        for pl in playlists:
            item = QListWidgetItem(pl["name"])
            item.setData(Qt.ItemDataRole.UserRole, pl["id"])
            self._playlist_list.addItem(item)

    def _create_playlist(self):
        name, ok = QInputDialog.getText(self, "Neue Playlist", "Name:")
        if ok and name.strip():
            pl_id = self.db.create_playlist(name.strip())
            self._load_playlists()
            # Select the new playlist
            for i in range(self._playlist_list.count()):
                if self._playlist_list.item(i).data(Qt.ItemDataRole.UserRole) == pl_id:
                    self._playlist_list.setCurrentRow(i)
                    break

    def _on_playlist_selected(self, row: int):
        if row < 0:
            return
        item = self._playlist_list.item(row)
        if not item:
            return
        pl_id = item.data(Qt.ItemDataRole.UserRole)
        self._current_playlist_id = pl_id
        self._playlist_name_label.setText(item.text())
        self._load_tracks(pl_id)

    def _load_tracks(self, pl_id: int):
        self._track_list.clear()
        tracks = self.db.get_playlist_tracks(pl_id)
        total_duration = 0.0
        for track in tracks:
            text = f"{track.artist} – {track.title}" if track.artist else track.title
            if not text.strip():
                text = os.path.basename(track.path)
            dur = format_duration(track.duration)
            item = QListWidgetItem(f"{text}  [{dur}]")
            item.setData(Qt.ItemDataRole.UserRole, track.path)
            self._track_list.addItem(item)
            total_duration += track.duration
        self._duration_label.setText(
            f"{len(tracks)} Tracks · Gesamtdauer: {format_duration(total_duration)}"
        )
        self.playlist_selected.emit(tracks)

    def add_tracks(self, tracks: list[TrackRecord], playlist_id: Optional[int] = None):
        """Tracks zu einer Playlist hinzufügen. Wenn keine ID angegeben, wird gefragt."""
        pl_id = playlist_id or self._current_playlist_id
        if pl_id is None:
            # Create a new playlist or ask
            playlists = self.db.get_all_playlists()
            if not playlists:
                name, ok = QInputDialog.getText(
                    self, "Neue Playlist", "Name für neue Playlist:"
                )
                if not ok or not name.strip():
                    return
                pl_id = self.db.create_playlist(name.strip())
                self._load_playlists()
            else:
                # Use current or first
                pl_id = playlists[0]["id"]
        for track in tracks:
            self.db.add_track_to_playlist(pl_id, track.path)
        if self._current_playlist_id == pl_id:
            self._load_tracks(pl_id)

    def _remove_selected_track(self):
        if self._current_playlist_id is None:
            return
        item = self._track_list.currentItem()
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        self.db.remove_track_from_playlist(self._current_playlist_id, path)
        self._load_tracks(self._current_playlist_id)

    def _on_tracks_reordered(self, *_):
        if self._current_playlist_id is None:
            return
        paths = [
            self._track_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._track_list.count())
        ]
        self.db.reorder_playlist(self._current_playlist_id, paths)

    def _on_track_activated(self, index):
        item = self._track_list.currentItem()
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        track = self.db.get_track(path)
        if track:
            self.track_activated.emit(track)

    # ── Context menus ─────────────────────────────────────────────────────────

    def _playlist_context_menu(self, pos):
        item = self._playlist_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_rename = menu.addAction("Umbenennen")
        act_delete = menu.addAction("Löschen")
        action = menu.exec(self._playlist_list.viewport().mapToGlobal(pos))
        pl_id = item.data(Qt.ItemDataRole.UserRole)
        if action == act_rename:
            name, ok = QInputDialog.getText(
                self, "Umbenennen", "Neuer Name:", text=item.text()
            )
            if ok and name.strip():
                self.db.rename_playlist(pl_id, name.strip())
                self._load_playlists()
        elif action == act_delete:
            reply = QMessageBox.question(
                self, "Playlist löschen",
                f'Playlist \u201e{item.text()}\u201c wirklich löschen?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.db.delete_playlist(pl_id)
                self._current_playlist_id = None
                self._track_list.clear()
                self._playlist_name_label.setText("Keine Playlist ausgewählt")
                self._load_playlists()

    def _track_context_menu(self, pos):
        item = self._track_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_remove = menu.addAction("Aus Playlist entfernen")
        action = menu.exec(self._track_list.viewport().mapToGlobal(pos))
        if action == act_remove:
            self._remove_selected_track()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_playlist(self):
        if self._current_playlist_id is None:
            return
        tracks = self.db.get_playlist_tracks(self._current_playlist_id)
        pl_info = self.db.get_playlist(self._current_playlist_id)
        if not tracks or not pl_info:
            return
        path, fmt = QFileDialog.getSaveFileName(
            self,
            "Playlist exportieren",
            pl_info["name"],
            "M3U Playlist (*.m3u);;Extended M3U (*.m3u8);;PLS Playlist (*.pls);;XSPF Playlist (*.xspf)"
        )
        if not path:
            return
        if path.endswith(".pls"):
            content = export_pls(tracks, pl_info["name"])
        elif path.endswith(".xspf"):
            content = export_xspf(tracks, pl_info["name"])
        else:
            content = export_m3u(tracks)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        QMessageBox.information(self, "Exportiert", f"Playlist gespeichert:\n{path}")


# ── Export functions ──────────────────────────────────────────────────────────

def export_m3u(tracks: list[TrackRecord], extended: bool = True) -> str:
    lines = ["#EXTM3U\n"]
    for t in tracks:
        if extended:
            dur = int(t.duration)
            title = f"{t.artist} - {t.title}" if t.artist else t.title
            lines.append(f"#EXTINF:{dur},{title}\n")
        lines.append(t.path + "\n")
    return "".join(lines)


def export_pls(tracks: list[TrackRecord], playlist_name: str = "") -> str:
    lines = ["[playlist]\n"]
    for i, t in enumerate(tracks, 1):
        lines.append(f"File{i}={t.path}\n")
        title = f"{t.artist} - {t.title}" if t.artist else t.title
        lines.append(f"Title{i}={title}\n")
        lines.append(f"Length{i}={int(t.duration)}\n")
    lines.append(f"NumberOfEntries={len(tracks)}\n")
    lines.append("Version=2\n")
    return "".join(lines)


def export_xspf(tracks: list[TrackRecord], playlist_name: str = "") -> str:
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom import minidom
    root = Element("playlist", version="1", xmlns="http://xspf.org/ns/0/")
    if playlist_name:
        title_el = SubElement(root, "title")
        title_el.text = playlist_name
    track_list = SubElement(root, "trackList")
    for t in tracks:
        track_el = SubElement(track_list, "track")
        loc = SubElement(track_el, "location")
        loc.text = "file://" + t.path
        if t.title:
            SubElement(track_el, "title").text = t.title
        if t.artist:
            SubElement(track_el, "creator").text = t.artist
        if t.album:
            SubElement(track_el, "album").text = t.album
        if t.duration:
            SubElement(track_el, "duration").text = str(int(t.duration * 1000))
    raw = tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")
