"""Hauptfenster der Tag-Editor-Anwendung."""

import os
from pathlib import Path
from functools import partial

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QLabel, QLineEdit, QComboBox, QGroupBox,
    QFormLayout, QDialog, QDialogButtonBox, QCheckBox,
    QMenu, QProgressDialog, QApplication, QAbstractItemView,
    QScrollArea, QFrame, QTabWidget, QSpinBox,
)
from PyQt6.QtCore import Qt, QSize, QMimeData
from PyQt6.QtGui import (
    QPixmap, QImage, QAction, QIcon, QKeySequence, QDragEnterEvent,
    QDropEvent, QFont,
)

from tag_editor.tag_handler import (
    AudioFileInfo, read_tags, write_tags, rename_file, scan_directory,
    is_supported_file, TAG_FIELDS,
)


class MainWindow(QMainWindow):
    """Hauptfenster des ID3-Tag-Editors."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hasi's ID3-Tag-Editor")
        self.setMinimumSize(1100, 700)
        self.resize(1300, 800)

        self._files: list[AudioFileInfo] = []
        self._modified: set[int] = set()  # Indices der geänderten Dateien
        self._cover_data: bytes | None = None
        self._cover_mime: str = ""
        self._cover_changed: bool = False

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_drag_drop()

    # ── UI-Aufbau ──────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ── Linke Seite: Dateiliste ──
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Dateiliste
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels([
            "Dateiname", "Titel", "Künstler", "Album", "Format"
        ])
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.file_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_table.customContextMenuRequested.connect(self._show_context_menu)
        self.file_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.file_table)

        splitter.addWidget(left_panel)

        # ── Rechte Seite: Tag-Editor ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        # Tab 1: Tags bearbeiten
        tag_tab = QWidget()
        tag_layout = QVBoxLayout(tag_tab)

        # Info-Label (zeigt an, wie viele Dateien ausgewählt sind)
        self.info_label = QLabel("Keine Dateien geladen")
        self.info_label.setStyleSheet("font-weight: bold; padding: 4px;")
        tag_layout.addWidget(self.info_label)

        # Scrollbarer Tag-Bereich
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.tag_form = QFormLayout(scroll_widget)
        self.tag_form.setSpacing(6)

        self.tag_inputs: dict[str, QLineEdit] = {}
        for field_key, field_label in TAG_FIELDS.items():
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"{field_label} eingeben...")
            line_edit.textChanged.connect(partial(self._on_tag_changed, field_key))
            self.tag_inputs[field_key] = line_edit
            self.tag_form.addRow(f"{field_label}:", line_edit)

        scroll.setWidget(scroll_widget)
        tag_layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("💾 Speichern")
        self.btn_save.setToolTip("Änderungen in die Dateien schreiben (⌘S)")
        self.btn_save.clicked.connect(self._save_tags)
        self.btn_save.setEnabled(False)
        self.btn_save.setMinimumHeight(36)
        btn_layout.addWidget(self.btn_save)

        self.btn_revert = QPushButton("↩ Zurücksetzen")
        self.btn_revert.setToolTip("Änderungen verwerfen")
        self.btn_revert.clicked.connect(self._revert_tags)
        self.btn_revert.setEnabled(False)
        self.btn_revert.setMinimumHeight(36)
        btn_layout.addWidget(self.btn_revert)

        tag_layout.addLayout(btn_layout)
        self.tabs.addTab(tag_tab, "Tags bearbeiten")

        # Tab 2: Cover-Art
        cover_tab = QWidget()
        cover_layout = QVBoxLayout(cover_tab)

        self.cover_label = QLabel("Kein Cover")
        self.cover_label.setFixedSize(300, 300)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(
            "border: 2px dashed #999; background: #f0f0f0; border-radius: 8px;"
        )
        self.cover_label.setScaledContents(False)
        cover_layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignCenter)

        cover_btn_layout = QHBoxLayout()
        btn_load_cover = QPushButton("🖼 Cover laden...")
        btn_load_cover.clicked.connect(self._load_cover)
        btn_load_cover.setMinimumHeight(32)
        cover_btn_layout.addWidget(btn_load_cover)

        btn_remove_cover = QPushButton("🗑 Cover entfernen")
        btn_remove_cover.clicked.connect(self._remove_cover)
        btn_remove_cover.setMinimumHeight(32)
        cover_btn_layout.addWidget(btn_remove_cover)

        btn_export_cover = QPushButton("📤 Cover exportieren...")
        btn_export_cover.clicked.connect(self._export_cover)
        btn_export_cover.setMinimumHeight(32)
        cover_btn_layout.addWidget(btn_export_cover)

        cover_layout.addLayout(cover_btn_layout)
        cover_layout.addStretch()
        self.tabs.addTab(cover_tab, "Cover-Art")

        # Tab 3: Umbenennung
        rename_tab = QWidget()
        rename_layout = QVBoxLayout(rename_tab)

        info_box = QGroupBox("Datei-Umbenennung nach Vorlage")
        info_form = QFormLayout(info_box)

        self.rename_template = QComboBox()
        self.rename_template.setEditable(True)
        self.rename_template.addItems([
            "{tracknumber:02} - {title}",
            "{artist} - {title}",
            "{tracknumber:02} - {artist} - {title}",
            "{album} - {tracknumber:02} - {title}",
            "{artist}/{album}/{tracknumber:02} - {title}",
        ])
        info_form.addRow("Vorlage:", self.rename_template)

        help_label = QLabel(
            "<small>Verfügbare Platzhalter: "
            "{title}, {artist}, {album}, {albumartist}, {date}, "
            "{genre}, {tracknumber}, {tracknumber:02}, {discnumber}, "
            "{composer}</small>"
        )
        help_label.setWordWrap(True)
        info_form.addRow(help_label)

        rename_layout.addWidget(info_box)

        # Vorschau
        self.rename_preview = QTableWidget()
        self.rename_preview.setColumnCount(2)
        self.rename_preview.setHorizontalHeaderLabels(["Aktueller Name", "Neuer Name"])
        self.rename_preview.horizontalHeader().setStretchLastSection(True)
        self.rename_preview.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        rename_layout.addWidget(self.rename_preview)

        rename_btn_layout = QHBoxLayout()
        btn_preview = QPushButton("👁 Vorschau")
        btn_preview.clicked.connect(self._preview_rename)
        btn_preview.setMinimumHeight(32)
        rename_btn_layout.addWidget(btn_preview)

        btn_rename = QPushButton("✏️ Umbenennen")
        btn_rename.clicked.connect(self._execute_rename)
        btn_rename.setMinimumHeight(32)
        rename_btn_layout.addWidget(btn_rename)

        rename_layout.addLayout(rename_btn_layout)
        self.tabs.addTab(rename_tab, "Umbenennung")

        # Tab 4: Batch-Bearbeitung
        batch_tab = QWidget()
        batch_layout = QVBoxLayout(batch_tab)

        batch_info = QLabel(
            "Hier kannst du Felder für alle ausgewählten Dateien auf einmal setzen.\n"
            "Nur ausgefüllte Felder werden überschrieben."
        )
        batch_info.setWordWrap(True)
        batch_info.setStyleSheet("padding: 8px; background: #e8f4fd; border-radius: 4px;")
        batch_layout.addWidget(batch_info)

        batch_scroll = QScrollArea()
        batch_scroll.setWidgetResizable(True)
        batch_widget = QWidget()
        self.batch_form = QFormLayout(batch_widget)

        self.batch_inputs: dict[str, QLineEdit] = {}
        for field_key, field_label in TAG_FIELDS.items():
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"Leer lassen = nicht ändern")
            self.batch_inputs[field_key] = line_edit
            self.batch_form.addRow(f"{field_label}:", line_edit)

        batch_scroll.setWidget(batch_widget)
        batch_layout.addWidget(batch_scroll)

        # Auto-Nummerierung
        num_box = QGroupBox("Auto-Nummerierung")
        num_layout = QHBoxLayout(num_box)
        self.auto_number_check = QCheckBox("Track-Nummern automatisch setzen")
        num_layout.addWidget(self.auto_number_check)
        self.auto_number_start = QSpinBox()
        self.auto_number_start.setMinimum(1)
        self.auto_number_start.setValue(1)
        self.auto_number_start.setPrefix("Start: ")
        num_layout.addWidget(self.auto_number_start)
        batch_layout.addWidget(num_box)

        btn_batch_apply = QPushButton("✅ Auf alle ausgewählten Dateien anwenden")
        btn_batch_apply.setMinimumHeight(40)
        btn_batch_apply.setStyleSheet("font-weight: bold;")
        btn_batch_apply.clicked.connect(self._apply_batch)
        batch_layout.addWidget(btn_batch_apply)

        self.tabs.addTab(batch_tab, "Batch-Bearbeitung")

        splitter.addWidget(right_panel)
        splitter.setSizes([500, 600])

    def _setup_menu(self):
        menubar = self.menuBar()

        # Datei-Menü
        file_menu = menubar.addMenu("Datei")

        act_open_files = QAction("Dateien öffnen...", self)
        act_open_files.setShortcut(QKeySequence("Ctrl+O"))
        act_open_files.triggered.connect(self._open_files)
        file_menu.addAction(act_open_files)

        act_open_dir = QAction("Ordner öffnen...", self)
        act_open_dir.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_dir.triggered.connect(self._open_directory)
        file_menu.addAction(act_open_dir)

        file_menu.addSeparator()

        act_save = QAction("Speichern", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._save_tags)
        file_menu.addAction(act_save)

        file_menu.addSeparator()

        act_clear = QAction("Liste leeren", self)
        act_clear.triggered.connect(self._clear_files)
        file_menu.addAction(act_clear)

        # Bearbeiten-Menü
        edit_menu = menubar.addMenu("Bearbeiten")

        act_select_all = QAction("Alles auswählen", self)
        act_select_all.setShortcut(QKeySequence("Ctrl+A"))
        act_select_all.triggered.connect(self.file_table.selectAll)
        edit_menu.addAction(act_select_all)

        act_remove_tags = QAction("Tags der Auswahl entfernen", self)
        act_remove_tags.triggered.connect(self._remove_all_tags)
        edit_menu.addAction(act_remove_tags)

    def _setup_toolbar(self):
        toolbar = QToolBar("Hauptleiste")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        btn_open_files = QPushButton("📂 Dateien")
        btn_open_files.setToolTip("Audio-Dateien öffnen")
        btn_open_files.clicked.connect(self._open_files)
        toolbar.addWidget(btn_open_files)

        btn_open_dir = QPushButton("📁 Ordner")
        btn_open_dir.setToolTip("Ordner mit Audio-Dateien öffnen")
        btn_open_dir.clicked.connect(self._open_directory)
        toolbar.addWidget(btn_open_dir)

        toolbar.addSeparator()

        btn_save = QPushButton("💾 Speichern")
        btn_save.setToolTip("Alle Änderungen speichern")
        btn_save.clicked.connect(self._save_tags)
        toolbar.addWidget(btn_save)

        toolbar.addSeparator()

        btn_remove = QPushButton("🗑 Auswahl entfernen")
        btn_remove.setToolTip("Ausgewählte Dateien aus der Liste entfernen")
        btn_remove.clicked.connect(self._remove_selected)
        toolbar.addWidget(btn_remove)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Bereit — Dateien per Drag & Drop oder über Datei-Menü laden")

    def _setup_drag_drop(self):
        self.setAcceptDrops(True)

    # ── Drag & Drop ────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                paths.extend(scan_directory(path))
            elif is_supported_file(path):
                paths.append(path)
        if paths:
            self._load_files(paths)

    # ── Datei-Operationen ──────────────────────────────────────

    def _open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Audio-Dateien öffnen", "",
            "Audio-Dateien (*.mp3 *.flac);;MP3-Dateien (*.mp3);;FLAC-Dateien (*.flac);;Alle Dateien (*)"
        )
        if files:
            self._load_files(files)

    def _open_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Ordner mit Audio-Dateien öffnen"
        )
        if directory:
            files = scan_directory(directory)
            if files:
                self._load_files(files)
            else:
                QMessageBox.information(
                    self, "Keine Dateien gefunden",
                    "Im gewählten Ordner wurden keine MP3- oder FLAC-Dateien gefunden."
                )

    def _load_files(self, filepaths: list[str]):
        # Duplikate vermeiden
        existing = {f.filepath for f in self._files}
        new_paths = [p for p in filepaths if p not in existing]

        if not new_paths:
            self.statusbar.showMessage("Alle Dateien sind bereits geladen.")
            return

        progress = QProgressDialog(
            "Lade Dateien...", "Abbrechen", 0, len(new_paths), self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        errors = []
        for i, path in enumerate(new_paths):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            progress.setLabelText(f"Lade: {Path(path).name}")
            QApplication.processEvents()

            try:
                info = read_tags(path)
                self._files.append(info)
            except Exception as e:
                errors.append(f"{Path(path).name}: {e}")

        progress.setValue(len(new_paths))
        self._refresh_file_table()

        msg = f"{len(new_paths) - len(errors)} Dateien geladen."
        if errors:
            msg += f" {len(errors)} Fehler."
            QMessageBox.warning(
                self, "Fehler beim Laden",
                "Folgende Dateien konnten nicht geladen werden:\n\n" +
                "\n".join(errors[:20])
            )
        self.statusbar.showMessage(msg)

    def _refresh_file_table(self):
        self.file_table.setRowCount(len(self._files))
        for row, info in enumerate(self._files):
            self.file_table.setItem(row, 0, QTableWidgetItem(info.filename))
            self.file_table.setItem(row, 1, QTableWidgetItem(info.tags.get("title", "")))
            self.file_table.setItem(row, 2, QTableWidgetItem(info.tags.get("artist", "")))
            self.file_table.setItem(row, 3, QTableWidgetItem(info.tags.get("album", "")))
            self.file_table.setItem(row, 4, QTableWidgetItem(info.file_format.upper()))

            # Geänderte Zeilen hervorheben
            if row in self._modified:
                for col in range(5):
                    item = self.file_table.item(row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.yellow)

    def _clear_files(self):
        if self._modified:
            reply = QMessageBox.question(
                self, "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen. Trotzdem fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self._files.clear()
        self._modified.clear()
        self.file_table.setRowCount(0)
        self._clear_tag_inputs()
        self.info_label.setText("Keine Dateien geladen")
        self.statusbar.showMessage("Liste geleert.")

    def _remove_selected(self):
        rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()), reverse=True)
        if not rows:
            return
        for row in rows:
            self._files.pop(row)
            self._modified.discard(row)
        # Indices in _modified anpassen
        new_modified = set()
        for idx in self._modified:
            offset = sum(1 for r in rows if r < idx)
            new_modified.add(idx - offset)
        self._modified = new_modified
        self._refresh_file_table()

    # ── Tag-Bearbeitung ────────────────────────────────────────

    def _on_selection_changed(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        if not selected_rows:
            self._clear_tag_inputs()
            self.info_label.setText("Keine Datei ausgewählt")
            return

        if len(selected_rows) == 1:
            info = self._files[selected_rows[0]]
            self.info_label.setText(
                f"{info.filename}  •  {info.file_format.upper()}  •  "
                f"{info.bitrate} kbps  •  {info.sample_rate} Hz  •  "
                f"{int(info.duration // 60)}:{int(info.duration % 60):02d}"
            )
            self._block_signals(True)
            for field_key, line_edit in self.tag_inputs.items():
                line_edit.setText(info.tags.get(field_key, ""))
            self._block_signals(False)

            # Cover anzeigen
            self._display_cover(info.cover_data)
            self._cover_data = info.cover_data
            self._cover_mime = info.cover_mime
            self._cover_changed = False
        else:
            self.info_label.setText(f"{len(selected_rows)} Dateien ausgewählt")
            # Bei Mehrfachauswahl: gemeinsame Werte anzeigen
            self._block_signals(True)
            for field_key, line_edit in self.tag_inputs.items():
                values = set()
                for row in selected_rows:
                    values.add(self._files[row].tags.get(field_key, ""))
                if len(values) == 1:
                    line_edit.setText(values.pop())
                else:
                    line_edit.setText("")
                    line_edit.setPlaceholderText("< verschiedene Werte >")
            self._block_signals(False)

            # Cover: erstes mit Cover nehmen
            cover_shown = False
            for row in selected_rows:
                if self._files[row].cover_data:
                    self._display_cover(self._files[row].cover_data)
                    cover_shown = True
                    break
            if not cover_shown:
                self._display_cover(None)
            self._cover_changed = False

        self.btn_save.setEnabled(True)
        self.btn_revert.setEnabled(True)

    def _on_tag_changed(self, field_key: str, text: str):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        for row in selected_rows:
            self._files[row].tags[field_key] = text
            self._modified.add(row)
        self._refresh_file_table()

    def _clear_tag_inputs(self):
        self._block_signals(True)
        for field_key, line_edit in self.tag_inputs.items():
            line_edit.setText("")
            line_edit.setPlaceholderText(f"{TAG_FIELDS[field_key]} eingeben...")
        self._block_signals(False)
        self.btn_save.setEnabled(False)
        self.btn_revert.setEnabled(False)

    def _block_signals(self, block: bool):
        for line_edit in self.tag_inputs.values():
            line_edit.blockSignals(block)

    def _save_tags(self):
        if not self._modified:
            self.statusbar.showMessage("Keine Änderungen zum Speichern.")
            return

        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))

        progress = QProgressDialog(
            "Speichere Tags...", "Abbrechen", 0, len(self._modified), self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        errors = []
        for i, row in enumerate(sorted(self._modified)):
            if progress.wasCanceled():
                break
            progress.setValue(i)

            info = self._files[row]
            try:
                cover = None
                cover_mime = "image/jpeg"
                if self._cover_changed and row in selected_rows:
                    cover = self._cover_data
                    cover_mime = self._cover_mime or "image/jpeg"

                write_tags(info.filepath, info.tags, cover, cover_mime)
            except Exception as e:
                errors.append(f"{info.filename}: {e}")

        progress.setValue(len(self._modified))
        self._modified.clear()
        self._cover_changed = False
        self._refresh_file_table()

        if errors:
            QMessageBox.warning(
                self, "Fehler beim Speichern",
                "Folgende Dateien konnten nicht gespeichert werden:\n\n" +
                "\n".join(errors[:20])
            )
        else:
            self.statusbar.showMessage(
                f"Tags erfolgreich gespeichert."
            )

    def _revert_tags(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        for row in selected_rows:
            try:
                self._files[row] = read_tags(self._files[row].filepath)
                self._modified.discard(row)
            except Exception:
                pass
        self._refresh_file_table()
        self._on_selection_changed()
        self.statusbar.showMessage("Tags zurückgesetzt.")

    def _remove_all_tags(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        if not selected_rows:
            return

        reply = QMessageBox.question(
            self, "Tags entfernen",
            f"Alle Tags von {len(selected_rows)} Datei(en) entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        for row in selected_rows:
            for key in list(self._files[row].tags.keys()):
                self._files[row].tags[key] = ""
            self._modified.add(row)
        self._on_selection_changed()
        self._refresh_file_table()
        self.statusbar.showMessage(f"Tags von {len(selected_rows)} Datei(en) zum Entfernen markiert. Bitte speichern.")

    # ── Cover-Art ──────────────────────────────────────────────

    def _display_cover(self, data: bytes | None):
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            scaled = pixmap.scaled(
                280, 280,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.cover_label.setPixmap(scaled)
            self.cover_label.setStyleSheet(
                "border: 1px solid #ccc; border-radius: 8px;"
            )
        else:
            self.cover_label.clear()
            self.cover_label.setText("Kein Cover")
            self.cover_label.setStyleSheet(
                "border: 2px dashed #999; background: #f0f0f0; border-radius: 8px;"
            )

    def _load_cover(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Cover-Bild laden", "",
            "Bilder (*.jpg *.jpeg *.png *.bmp);;Alle Dateien (*)"
        )
        if not filepath:
            return

        with open(filepath, "rb") as f:
            self._cover_data = f.read()

        ext = Path(filepath).suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".bmp": "image/bmp"}
        self._cover_mime = mime_map.get(ext, "image/jpeg")
        self._cover_changed = True

        self._display_cover(self._cover_data)

        # Markiere ausgewählte Dateien als geändert
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        for row in selected_rows:
            self._modified.add(row)
        self._refresh_file_table()
        self.statusbar.showMessage("Cover geladen. Bitte speichern um es zu übernehmen.")

    def _remove_cover(self):
        self._cover_data = b""  # Leere Bytes = Cover entfernen
        self._cover_mime = ""
        self._cover_changed = True
        self._display_cover(None)

        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        for row in selected_rows:
            self._modified.add(row)
        self._refresh_file_table()
        self.statusbar.showMessage("Cover zum Entfernen markiert. Bitte speichern.")

    def _export_cover(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        if not selected_rows:
            return

        info = self._files[selected_rows[0]]
        if not info.cover_data:
            QMessageBox.information(self, "Kein Cover", "Diese Datei hat kein Cover-Bild.")
            return

        ext = ".jpg"
        if info.cover_mime == "image/png":
            ext = ".png"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Cover exportieren", f"cover{ext}",
            f"Bilder (*{ext});;Alle Dateien (*)"
        )
        if filepath:
            with open(filepath, "wb") as f:
                f.write(info.cover_data)
            self.statusbar.showMessage(f"Cover exportiert: {filepath}")

    # ── Umbenennung ────────────────────────────────────────────

    def _preview_rename(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        if not selected_rows:
            selected_rows = list(range(len(self._files)))

        template = self.rename_template.currentText()
        self.rename_preview.setRowCount(len(selected_rows))

        for i, row in enumerate(selected_rows):
            info = self._files[row]
            old_name = info.filename

            # Neuen Namen generieren
            new_name = template
            for key, value in info.tags.items():
                placeholder = "{" + key + "}"
                if placeholder in new_name:
                    safe = value.replace("/", "_").replace("\\", "_")
                    for c in '<>:"|?*':
                        safe = safe.replace(c, "_")
                    new_name = new_name.replace(placeholder, safe)

            if "{tracknumber:02}" in new_name:
                tn = info.tags.get("tracknumber", "0").split("/")[0].strip()
                try:
                    new_name = new_name.replace("{tracknumber:02}", f"{int(tn):02d}")
                except ValueError:
                    new_name = new_name.replace("{tracknumber:02}", tn)

            new_name += Path(info.filepath).suffix

            self.rename_preview.setItem(i, 0, QTableWidgetItem(old_name))
            self.rename_preview.setItem(i, 1, QTableWidgetItem(new_name))

    def _execute_rename(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        if not selected_rows:
            selected_rows = list(range(len(self._files)))

        if not selected_rows:
            return

        reply = QMessageBox.question(
            self, "Dateien umbenennen",
            f"{len(selected_rows)} Datei(en) umbenennen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        template = self.rename_template.currentText()
        errors = []
        renamed = 0

        for row in selected_rows:
            info = self._files[row]
            try:
                new_path = rename_file(info.filepath, template, info.tags)
                # AudioFileInfo aktualisieren
                info.filepath = new_path
                info.filename = Path(new_path).name
                renamed += 1
            except Exception as e:
                errors.append(f"{info.filename}: {e}")

        self._refresh_file_table()

        if errors:
            QMessageBox.warning(
                self, "Fehler beim Umbenennen",
                "Folgende Dateien konnten nicht umbenannt werden:\n\n" +
                "\n".join(errors[:20])
            )

        self.statusbar.showMessage(f"{renamed} Datei(en) umbenannt.")

    # ── Batch-Bearbeitung ──────────────────────────────────────

    def _apply_batch(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        if not selected_rows:
            QMessageBox.information(
                self, "Keine Auswahl",
                "Bitte wähle zuerst Dateien in der Liste aus.\n"
                "Tipp: Mit Strg+A (⌘A) kannst du alle auswählen."
            )
            return

        # Batch-Werte sammeln
        batch_values = {}
        for field_key, line_edit in self.batch_inputs.items():
            text = line_edit.text()
            if text:
                batch_values[field_key] = text

        auto_number = self.auto_number_check.isChecked()

        if not batch_values and not auto_number:
            QMessageBox.information(
                self, "Keine Änderungen",
                "Bitte fülle mindestens ein Feld aus oder aktiviere die Auto-Nummerierung."
            )
            return

        # Bestätigung
        reply = QMessageBox.question(
            self, "Batch-Bearbeitung",
            f"Sollen die Änderungen auf {len(selected_rows)} Datei(en) angewendet werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        start_num = self.auto_number_start.value()

        for i, row in enumerate(selected_rows):
            for key, value in batch_values.items():
                self._files[row].tags[key] = value
            if auto_number:
                self._files[row].tags["tracknumber"] = str(start_num + i)
            self._modified.add(row)

        self._refresh_file_table()
        self._on_selection_changed()

        # Batch-Felder leeren
        for line_edit in self.batch_inputs.values():
            line_edit.clear()
        self.auto_number_check.setChecked(False)

        self.statusbar.showMessage(
            f"Batch-Änderungen auf {len(selected_rows)} Datei(en) angewendet. "
            "Bitte speichern um die Änderungen zu übernehmen."
        )

    # ── Kontextmenü ────────────────────────────────────────────

    def _show_context_menu(self, pos):
        menu = QMenu(self)

        act_open_folder = QAction("Im Finder öffnen", self)
        act_open_folder.triggered.connect(self._open_in_finder)
        menu.addAction(act_open_folder)

        menu.addSeparator()

        act_remove = QAction("Aus Liste entfernen", self)
        act_remove.triggered.connect(self._remove_selected)
        menu.addAction(act_remove)

        menu.exec(self.file_table.viewport().mapToGlobal(pos))

    def _open_in_finder(self):
        selected_rows = sorted(set(idx.row() for idx in self.file_table.selectedIndexes()))
        if selected_rows:
            path = self._files[selected_rows[0]].filepath
            os.system(f'open -R "{path}"')

    # ── Fenster schließen ──────────────────────────────────────

    def closeEvent(self, event):
        if self._modified:
            reply = QMessageBox.question(
                self, "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen. Wirklich beenden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()
