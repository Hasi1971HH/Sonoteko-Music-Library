"""Audio-Preview-Player Widget (nutzt QtMultimedia)."""

import os
from typing import Optional

from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSlider, QLabel,
    QPushButton, QSizePolicy
)
from PyQt6.QtGui import QIcon, QPixmap

from sonoteko.tag_handler import format_duration, read_tags


class PlayerWidget(QWidget):
    """Kompakter Player am unteren Rand des Hauptfensters."""

    track_changed = pyqtSignal(str)  # filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.7)
        self._current_path: Optional[str] = None
        self._seeking = False
        self._cover_pixmap: Optional[QPixmap] = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet("""
            QWidget {
                background: #1a1a2e;
                border-top: 1px solid #0f3460;
            }
            QLabel { color: #ccc; font-size: 11px; }
            QPushButton {
                background: transparent;
                border: none;
                color: #e94560;
                font-size: 18px;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(233,69,96,0.15); }
            QPushButton:disabled { color: #555; }
            QSlider::groove:horizontal {
                height: 4px;
                background: #0f3460;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #e94560;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #e94560;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
        """)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 12, 6)
        outer.setSpacing(8)

        # ── Cover Art ──
        self._cover_label = QLabel()
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet(
            "background: #0f3460; border-radius: 4px; color: #445; font-size: 22px;"
        )
        self._cover_label.setText("♪")
        self._cover_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        outer.addWidget(self._cover_label)

        # ── Track info ──
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self._title_label = QLabel("Kein Track")
        self._title_label.setStyleSheet("color: #eee; font-weight: bold; font-size: 12px;")
        self._artist_label = QLabel("")
        info_col.addWidget(self._title_label)
        info_col.addWidget(self._artist_label)
        outer.addLayout(info_col, stretch=2)

        # ── Controls ──
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        self._btn_prev = QPushButton("⏮")
        self._btn_play = QPushButton("▶")
        self._btn_play.setFixedWidth(40)
        self._btn_stop = QPushButton("⏹")
        self._btn_next = QPushButton("⏭")
        ctrl.addWidget(self._btn_prev)
        ctrl.addWidget(self._btn_play)
        ctrl.addWidget(self._btn_stop)
        ctrl.addWidget(self._btn_next)
        outer.addLayout(ctrl)

        # ── Seek slider ──
        seek_col = QVBoxLayout()
        seek_col.setSpacing(2)
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        time_row = QHBoxLayout()
        self._time_label = QLabel("0:00")
        self._duration_label = QLabel("0:00")
        time_row.addWidget(self._time_label)
        time_row.addStretch()
        time_row.addWidget(self._duration_label)
        seek_col.addWidget(self._seek_slider)
        seek_col.addLayout(time_row)
        outer.addLayout(seek_col, stretch=3)

        # ── Volume ──
        vol_col = QVBoxLayout()
        vol_col.setSpacing(2)
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(70)
        self._vol_slider.setFixedWidth(80)
        vol_label = QLabel("🔊")
        vol_label.setStyleSheet("color: #888; font-size: 13px;")
        vol_row = QHBoxLayout()
        vol_row.setSpacing(4)
        vol_row.addWidget(vol_label)
        vol_row.addWidget(self._vol_slider)
        vol_col.addStretch()
        vol_col.addLayout(vol_row)
        vol_col.addStretch()
        outer.addLayout(vol_col)

    def _connect_signals(self):
        self._btn_play.clicked.connect(self.toggle_play)
        self._btn_stop.clicked.connect(self.stop)
        self._btn_prev.clicked.connect(self._on_prev)
        self._btn_next.clicked.connect(self._on_next)

        self._seek_slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._vol_slider.valueChanged.connect(
            lambda v: self._audio_output.setVolume(v / 100.0)
        )

        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    # ── Public API ────────────────────────────────────────────────────────────

    def play_file(self, filepath: str, title: str = "", artist: str = ""):
        self._current_path = filepath
        self._player.setSource(QUrl.fromLocalFile(filepath))
        self._player.play()
        name = title or os.path.splitext(os.path.basename(filepath))[0]
        self._title_label.setText(name)
        self._artist_label.setText(artist)
        self._btn_play.setText("⏸")
        self._update_cover(filepath)
        self.track_changed.emit(filepath)

    def _update_cover(self, filepath: str):
        """Liest das Cover-Bild aus den Tags und zeigt es an."""
        self._cover_pixmap = None
        try:
            info = read_tags(filepath)
            if info.cover_data:
                px = QPixmap()
                px.loadFromData(info.cover_data)
                if not px.isNull():
                    self._cover_pixmap = px
        except Exception:
            pass
        self._scale_cover()

    def _scale_cover(self):
        """Skaliert das gespeicherte Cover auf die aktuelle Label-Größe."""
        size = self._cover_label.width()
        if size < 1:
            return
        if self._cover_pixmap and not self._cover_pixmap.isNull():
            self._cover_label.setText("")
            self._cover_label.setPixmap(
                self._cover_pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._cover_label.setPixmap(QPixmap())
            self._cover_label.setText("♪")

    def resizeEvent(self, event):
        """Passt die Cover-Größe an die Player-Höhe an."""
        super().resizeEvent(event)
        inner_h = self.height() - 12          # 6px Margin oben + unten
        cover_size = max(44, min(inner_h, 96))  # zwischen 44 und 96 px
        self._cover_label.setFixedSize(cover_size, cover_size)
        self._scale_cover()

    def toggle_play(self):
        state = self._player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._player.play()
        elif self._current_path:
            self._player.play()

    def stop(self):
        self._player.stop()

    def set_playlist(self, tracks: list):
        """Setzt eine Liste von TrackRecord-Objekten als Playlist."""
        self._playlist = tracks
        self._playlist_index = -1

    def play_next(self):
        self._on_next()

    def play_prev(self):
        self._on_prev()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._btn_play.setText("⏸")
        else:
            self._btn_play.setText("▶")

    def _on_position_changed(self, pos_ms: int):
        if self._seeking:
            return
        duration_ms = self._player.duration()
        if duration_ms > 0:
            self._seek_slider.setValue(int(pos_ms / duration_ms * 1000))
        self._time_label.setText(format_duration(pos_ms / 1000))

    def _on_duration_changed(self, duration_ms: int):
        self._duration_label.setText(format_duration(duration_ms / 1000))

    def _on_seek_released(self):
        self._seeking = False
        duration_ms = self._player.duration()
        if duration_ms > 0:
            target = int(self._seek_slider.value() / 1000 * duration_ms)
            self._player.setPosition(target)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            playlist = getattr(self, "_playlist", [])
            if playlist and self._playlist_index < len(playlist) - 1:
                self._on_next()

    def _on_prev(self):
        if hasattr(self, "_playlist") and self._playlist:
            self._playlist_index = max(0, self._playlist_index - 1)
            t = self._playlist[self._playlist_index]
            self.play_file(t.path, t.title, t.artist)

    def _on_next(self):
        if hasattr(self, "_playlist") and self._playlist:
            self._playlist_index = min(
                len(self._playlist) - 1,
                self._playlist_index + 1
            )
            t = self._playlist[self._playlist_index]
            self.play_file(t.path, t.title, t.artist)
