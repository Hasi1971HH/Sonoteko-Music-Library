"""Einstiegspunkt für Hasi's ID3-Tag-Editor."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from tag_editor.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Hasi's ID3-Tag-Editor")
    app.setOrganizationName("Hasi")

    # Modernes Styling
    app.setStyleSheet("""
        QMainWindow {
            background: #fafafa;
        }
        QTableWidget {
            font-size: 13px;
            gridline-color: #e0e0e0;
        }
        QTableWidget::item {
            padding: 4px 8px;
        }
        QTableWidget::item:selected {
            background: #0078d4;
            color: white;
        }
        QHeaderView::section {
            background: #f0f0f0;
            padding: 6px;
            border: 1px solid #ddd;
            font-weight: bold;
        }
        QPushButton {
            padding: 6px 16px;
            border-radius: 6px;
            border: 1px solid #ccc;
            background: #fff;
        }
        QPushButton:hover {
            background: #e8f0fe;
            border-color: #0078d4;
        }
        QPushButton:pressed {
            background: #d0e0f0;
        }
        QLineEdit {
            padding: 5px 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        QLineEdit:focus {
            border-color: #0078d4;
        }
        QTabWidget::pane {
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        QTabBar::tab {
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid #ddd;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            background: #f5f5f5;
        }
        QTabBar::tab:selected {
            background: white;
            border-bottom: 2px solid #0078d4;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ddd;
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            padding: 0 8px;
        }
        QComboBox {
            padding: 5px 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        QScrollArea {
            border: none;
        }
        QStatusBar {
            background: #f0f0f0;
            border-top: 1px solid #ddd;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
