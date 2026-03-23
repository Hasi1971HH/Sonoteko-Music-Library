"""Tag-Editor Panel — Einzel- und Batch-Bearbeitung + Cover-Art + Umbenennung."""

import os
import re
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QLineEdit, QTextEdit, QPushButton, QLabel, QScrollArea,
    QGroupBox, QFileDialog, QMessageBox, QCheckBox, QSizePolicy,
    QSplitter, QFrame
)
from PyQt6.QtGui import QPixmap, QImage

from sonoteko.tag_handler import (
    AudioFileInfo, read_tags, write_tags, rename_file,
    FIELD_LABELS, format_duration
)


# Felder die im Editor angezeigt werden
EDITOR_FIELDS = [
    "title", "artist", "album", "albumartist", "date", "genre",
    "tracknumber", "discnumber", "composer", "comment", "bpm",
    "publisher", "copyright", "isrc", "key", "mood",
    "lyricist", "originalartist", "lyrics",
    "replaygain_track_gain", "replaygain_track_peak",
    "replaygain_album_gain", "replaygain_album_peak",
]

RENAME_PLACEHOLDERS = [
    "{title}", "{artist}", "{album}", "{albumartist}",
    "{date}", "{tracknumber}", "{discnumber}", "{genre}",
]


class TagEditorPanel(QWidget):
    """Panel zum Bearbeiten von Tags für einen oder mehrere Tracks."""

    tags_saved = pyqtSignal(list)   # list of filepaths that were saved

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: list[AudioFileInfo] = []
        self._modified = False
        self._cover_data: Optional[bytes] = None
        self._cover_mime: str = "image/jpeg"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()

        # ── Tab 1: Tags ──
        tags_tab = QWidget()
        tags_layout = QVBoxLayout(tags_tab)

        # File info header
        self._file_info_label = QLabel("Kein Track ausgewählt")
        self._file_info_label.setStyleSheet("color: #888; font-size: 11px;")
        tags_layout.addWidget(self._file_info_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_widget = QWidget()
        self._form = QFormLayout(form_widget)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._inputs: dict[str, QLineEdit | QTextEdit] = {}

        for field in EDITOR_FIELDS:
            label = FIELD_LABELS.get(field, field)
            if field == "lyrics":
                widget = QTextEdit()
                widget.setFixedHeight(80)
                widget.textChanged.connect(self._on_changed)
            else:
                widget = QLineEdit()
                widget.textChanged.connect(self._on_changed)
            self._inputs[field] = widget
            self._form.addRow(f"{label}:", widget)

        scroll.setWidget(form_widget)
        tags_layout.addWidget(scroll)

        tabs.addTab(tags_tab, "Tags")

        # ── Tab 2: Cover-Art ──
        cover_tab = QWidget()
        cover_layout = QVBoxLayout(cover_tab)

        self._cover_label = QLabel()
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setMinimumSize(200, 200)
        self._cover_label.setStyleSheet("background: #111; border: 1px solid #333;")
        self._cover_label.setText("Kein Cover")
        cover_layout.addWidget(self._cover_label, stretch=1)

        self._cover_info_label = QLabel()
        self._cover_info_label.setStyleSheet("color: #888; font-size: 10px;")
        cover_layout.addWidget(self._cover_info_label)

        cover_btn_row = QHBoxLayout()
        btn_load_cover = QPushButton("Cover laden …")
        btn_load_cover.clicked.connect(self._load_cover)
        cover_btn_row.addWidget(btn_load_cover)
        btn_export_cover = QPushButton("Exportieren …")
        btn_export_cover.clicked.connect(self._export_cover)
        cover_btn_row.addWidget(btn_export_cover)
        btn_remove_cover = QPushButton("Entfernen")
        btn_remove_cover.clicked.connect(self._remove_cover)
        cover_btn_row.addWidget(btn_remove_cover)
        cover_layout.addLayout(cover_btn_row)

        tabs.addTab(cover_tab, "Cover-Art")

        # ── Tab 3: Umbenennen ──
        rename_tab = QWidget()
        rename_layout = QVBoxLayout(rename_tab)

        rename_layout.addWidget(QLabel("Template:"))
        self._rename_template = QLineEdit("{tracknumber} - {title}")
        self._rename_template.textChanged.connect(self._update_rename_preview)
        rename_layout.addWidget(self._rename_template)

        placeholder_label = QLabel("Platzhalter: " + "  ".join(RENAME_PLACEHOLDERS))
        placeholder_label.setStyleSheet("color: #888; font-size: 10px;")
        placeholder_label.setWordWrap(True)
        rename_layout.addWidget(placeholder_label)

        rename_layout.addWidget(QLabel("Vorschau:"))
        self._rename_preview = QTextEdit()
        self._rename_preview.setReadOnly(True)
        self._rename_preview.setMaximumHeight(120)
        rename_layout.addWidget(self._rename_preview)

        btn_rename = QPushButton("Umbenennen")
        btn_rename.clicked.connect(self._execute_rename)
        rename_layout.addWidget(btn_rename)
        rename_layout.addStretch()

        tabs.addTab(rename_tab, "Umbenennen")

        # ── Tab 4: Batch ──
        batch_tab = QWidget()
        batch_layout = QVBoxLayout(batch_tab)
        batch_layout.addWidget(QLabel(
            "Batch-Bearbeitung: Überschreibt die gewählten Felder\n"
            "bei ALLEN ausgewählten Tracks gleichzeitig."
        ))

        batch_scroll = QScrollArea()
        batch_scroll.setWidgetResizable(True)
        batch_scroll.setFrameShape(QFrame.Shape.NoFrame)
        batch_form_widget = QWidget()
        batch_form = QFormLayout(batch_form_widget)
        batch_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._batch_inputs: dict[str, tuple[QCheckBox, QLineEdit]] = {}

        batch_fields = [
            "artist", "album", "albumartist", "date", "genre",
            "publisher", "composer", "copyright", "bpm", "mood"
        ]
        for field in batch_fields:
            label = FIELD_LABELS.get(field, field)
            check = QCheckBox()
            inp = QLineEdit()
            inp.setEnabled(False)
            check.toggled.connect(inp.setEnabled)
            row = QHBoxLayout()
            row.addWidget(check)
            row.addWidget(inp)
            row_widget = QWidget()
            row_widget.setLayout(row)
            batch_form.addRow(f"{label}:", row_widget)
            self._batch_inputs[field] = (check, inp)

        batch_scroll.setWidget(batch_form_widget)
        batch_layout.addWidget(batch_scroll)

        # Auto-Nummerierung
        autonr_group = QGroupBox("Track-Nummerierung")
        autonr_layout = QHBoxLayout(autonr_group)
        self._autonr_check = QCheckBox("Automatisch nummerieren ab")
        self._autonr_start = QLineEdit("1")
        self._autonr_start.setFixedWidth(50)
        autonr_layout.addWidget(self._autonr_check)
        autonr_layout.addWidget(self._autonr_start)
        autonr_layout.addStretch()
        batch_layout.addWidget(autonr_group)

        btn_apply_batch = QPushButton("Auf alle Tracks anwenden")
        btn_apply_batch.clicked.connect(self._apply_batch)
        batch_layout.addWidget(btn_apply_batch)

        tabs.addTab(batch_tab, "Batch")

        layout.addWidget(tabs)

        # ── Save / Revert ──
        action_row = QHBoxLayout()
        self._btn_save = QPushButton("Speichern")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._save)
        self._btn_save.setStyleSheet(
            "QPushButton { background: #e94560; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:disabled { background: #444; color: #777; }"
        )
        action_row.addStretch()
        self._btn_revert = QPushButton("Zurücksetzen")
        self._btn_revert.setEnabled(False)
        self._btn_revert.clicked.connect(self._revert)
        action_row.addWidget(self._btn_revert)
        action_row.addWidget(self._btn_save)
        layout.addLayout(action_row)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_files(self, filepaths: list[str]):
        self._files = [read_tags(f) for f in filepaths]
        self._modified = False
        if len(self._files) == 1:
            self._populate_single(self._files[0])
        elif len(self._files) > 1:
            self._populate_multi(self._files)
        else:
            self._clear()
        self._btn_save.setEnabled(False)
        self._btn_revert.setEnabled(False)
        self._update_rename_preview()

    def set_tag(self, field: str, value: str):
        """Von außen einen Tag-Wert setzen (z.B. von MusicBrainz)."""
        widget = self._inputs.get(field)
        if widget is None:
            return
        if isinstance(widget, QTextEdit):
            widget.setPlainText(value)
        else:
            widget.setText(value)

    def set_cover(self, data: bytes, mime: str):
        """Cover von außen setzen (z.B. Cover Art Archive)."""
        self._cover_data = data
        self._cover_mime = mime
        self._show_cover(data)
        self._on_changed()

    def get_current_tags(self) -> dict:
        tags = {}
        for field, widget in self._inputs.items():
            if isinstance(widget, QTextEdit):
                tags[field] = widget.toPlainText()
            else:
                tags[field] = widget.text()
        return tags

    # ── Populate ─────────────────────────────────────────────────────────────

    def _populate_single(self, info: AudioFileInfo):
        self._block_signals(True)
        for field, widget in self._inputs.items():
            value = info.tags.get(field, "")
            if isinstance(widget, QTextEdit):
                widget.setPlainText(value)
            else:
                widget.setText(value)
        self._cover_data = info.cover_data
        self._cover_mime = info.cover_mime
        if info.cover_data:
            self._show_cover(info.cover_data)
        else:
            self._cover_label.setText("Kein Cover")
            self._cover_label.setPixmap(QPixmap())
            self._cover_info_label.setText("")
        ai = info.audio_info
        info_parts = [os.path.basename(info.filepath)]
        if ai.duration:
            info_parts.append(format_duration(ai.duration))
        if ai.bitrate:
            info_parts.append(f"{ai.bitrate} kbps")
        if ai.format:
            info_parts.append(ai.format)
        self._file_info_label.setText("  ·  ".join(info_parts))
        self._block_signals(False)

    def _populate_multi(self, files: list[AudioFileInfo]):
        self._block_signals(True)
        self._cover_label.setText(f"{len(files)} Tracks ausgewählt")
        self._cover_label.setPixmap(QPixmap())
        self._file_info_label.setText(f"{len(files)} Tracks ausgewählt — Batch-Bearbeitung empfohlen")
        # Show common values
        for field, widget in self._inputs.items():
            values = set()
            for f in files:
                values.add(f.tags.get(field, ""))
            common = values.pop() if len(values) == 1 else ""
            if isinstance(widget, QTextEdit):
                widget.setPlainText(common)
            else:
                widget.setText(common)
                if len(values) > 1:
                    widget.setPlaceholderText("(verschiedene Werte)")
        self._block_signals(False)

    def _clear(self):
        self._block_signals(True)
        for widget in self._inputs.values():
            if isinstance(widget, QTextEdit):
                widget.clear()
            else:
                widget.clear()
        self._cover_label.setText("Kein Track ausgewählt")
        self._cover_label.setPixmap(QPixmap())
        self._file_info_label.setText("Kein Track ausgewählt")
        self._block_signals(False)

    # ── Cover ─────────────────────────────────────────────────────────────────

    def _show_cover(self, data: bytes):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        size = self._cover_label.size()
        scaled = pixmap.scaled(
            size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._cover_label.setPixmap(scaled)
        self._cover_info_label.setText(
            f"{pixmap.width()}×{pixmap.height()} px  ·  {len(data) // 1024} KB"
        )

    def _load_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cover laden",
            filter="Bilder (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        self._cover_data = data
        self._cover_mime = mime
        self._show_cover(data)
        self._on_changed()

    def _export_cover(self):
        if not self._cover_data:
            return
        ext = ".png" if "png" in self._cover_mime else ".jpg"
        path, _ = QFileDialog.getSaveFileName(
            self, "Cover exportieren", f"cover{ext}",
            "Bilder (*.jpg *.png)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(self._cover_data)

    def _remove_cover(self):
        self._cover_data = None
        self._cover_label.setText("Kein Cover")
        self._cover_label.setPixmap(QPixmap())
        self._cover_info_label.setText("")
        self._on_changed()

    # ── Save / Revert ─────────────────────────────────────────────────────────

    def _on_changed(self):
        if not self._modified:
            self._modified = True
            self._btn_save.setEnabled(True)
            self._btn_revert.setEnabled(True)

    def _save(self):
        if not self._files:
            return
        tags = self.get_current_tags()
        saved = []
        for info in self._files:
            success = write_tags(
                info.filepath, tags,
                cover_data=self._cover_data,
                cover_mime=self._cover_mime
            )
            if success:
                saved.append(info.filepath)
            else:
                QMessageBox.warning(
                    self, "Fehler",
                    f"Konnte Tags nicht speichern:\n{info.filepath}"
                )
        self._modified = False
        self._btn_save.setEnabled(False)
        self._btn_revert.setEnabled(False)
        self.tags_saved.emit(saved)

    def _revert(self):
        if self._files:
            filepaths = [f.filepath for f in self._files]
            self.load_files(filepaths)

    # ── Batch ─────────────────────────────────────────────────────────────────

    def _apply_batch(self):
        if not self._files:
            return
        batch_tags = {}
        for field, (check, inp) in self._batch_inputs.items():
            if check.isChecked():
                batch_tags[field] = inp.text()

        if not batch_tags and not self._autonr_check.isChecked():
            QMessageBox.information(self, "Batch", "Keine Felder ausgewählt.")
            return

        try:
            start = int(self._autonr_start.text())
        except ValueError:
            start = 1

        saved = []
        for i, info in enumerate(self._files):
            tags = dict(info.tags)
            tags.update(batch_tags)
            if self._autonr_check.isChecked():
                tags["tracknumber"] = str(start + i)
            success = write_tags(info.filepath, tags, info.cover_data, info.cover_mime)
            if success:
                saved.append(info.filepath)
        QMessageBox.information(self, "Batch", f"{len(saved)} Tracks gespeichert.")
        self.tags_saved.emit(saved)
        # Reload
        self.load_files([f.filepath for f in self._files])

    # ── Rename ────────────────────────────────────────────────────────────────

    def _update_rename_preview(self):
        template = self._rename_template.text()
        if not self._files:
            self._rename_preview.clear()
            return
        lines = []
        for info in self._files[:10]:
            ext = os.path.splitext(info.filepath)[1]
            name = template
            for key, value in info.tags.items():
                name = name.replace(f"{{{key}}}", str(value))
            old = os.path.basename(info.filepath)
            new = name + ext
            lines.append(f"{old}  →  {new}")
        if len(self._files) > 10:
            lines.append(f"… und {len(self._files) - 10} weitere")
        self._rename_preview.setPlainText("\n".join(lines))

    def _execute_rename(self):
        if not self._files:
            return
        template = self._rename_template.text()
        renamed = errors = 0
        new_paths = []
        for info in self._files:
            try:
                new_path = rename_file(info.filepath, template, info.tags)
                new_paths.append(new_path)
                renamed += 1
            except Exception as e:
                errors += 1
                print(f"[rename] {info.filepath}: {e}")
        msg = f"{renamed} Dateien umbenannt."
        if errors:
            msg += f"\n{errors} Fehler."
        QMessageBox.information(self, "Umbenennen", msg)
        if new_paths:
            self.load_files(new_paths)
            self.tags_saved.emit(new_paths)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _block_signals(self, block: bool):
        for w in self._inputs.values():
            w.blockSignals(block)
