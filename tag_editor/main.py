"""Einstiegspunkt für Hasi's ID3-Tag-Editor."""

import sys
import os

# macOS crash prevention: on macOS 15+ / 26.x CoreFoundation uses PAC-signed
# CFInfo structures.  Qt's static initialiser in QtCore.abi3.so calls
# CFBundleCopyBundleURL(CFBundleGetMainBundle()) during QLoggingRegistry
# setup – before any user code runs.  When the returned CFBundleRef carries a
# PAC signature that the current OS rejects, the process crashes at address
# 0x8 (SIGSEGV / KERN_INVALID_ADDRESS).
#
# Two-pronged workaround (both must be set *before* the first PyQt6 import):
#   1. QT_QPA_NO_BUNDLE_LOOKUP=1  – Qt 6.7.2+ skips CFBundleGetMainBundle()
#      entirely when this is set.
#   2. QT_PLUGIN_PATH               – lets Qt locate its plugins without
#      falling back to the CFBundle lookup for older Qt builds.
if sys.platform == "darwin" and getattr(sys, "frozen", False):
    os.environ.setdefault("QT_QPA_NO_BUNDLE_LOOKUP", "1")

    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    for _candidate in (
        # PyInstaller 6.x  (_internal sub-directory layout)
        os.path.join(_exe_dir, "_internal", "PyQt6", "Qt6", "plugins"),
        # PyInstaller 5.x  (everything next to the executable)
        os.path.join(_exe_dir, "PyQt6", "Qt6", "plugins"),
        # Alternative Qt path name used by some wheels
        os.path.join(_exe_dir, "PyQt6", "Qt", "plugins"),
        # .app bundle: Contents/Frameworks/PyQt6/…
        os.path.normpath(
            os.path.join(_exe_dir, "..", "Frameworks", "PyQt6", "Qt6", "plugins")
        ),
    ):
        if os.path.isdir(_candidate):
            os.environ.setdefault("QT_PLUGIN_PATH", _candidate)
            break

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
