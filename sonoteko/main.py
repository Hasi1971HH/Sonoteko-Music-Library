"""Sonoteko — Einstiegspunkt."""

import os
import sys


def main():
    # macOS: Crash-Prävention für PyInstaller-Bundles
    os.environ.setdefault("QT_QPA_NO_BUNDLE_LOOKUP", "1")

    # Qt-Framework-Pfad für macOS setzen
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        bundle_dir = os.path.dirname(sys.executable)
        frameworks_dir = os.path.join(bundle_dir, "..", "Frameworks")
        if os.path.exists(frameworks_dir):
            qt_plugin_path = os.path.join(frameworks_dir, "PyQt6", "Qt6", "plugins")
            if os.path.exists(qt_plugin_path):
                os.environ.setdefault("QT_PLUGIN_PATH", qt_plugin_path)

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QCoreApplication
    from PyQt6.QtGui import QIcon, QPixmap

    QCoreApplication.setApplicationName("Sonoteko")
    QCoreApplication.setOrganizationName("Sonoteko")
    QCoreApplication.setApplicationVersion("2.0.0")

    app = QApplication(sys.argv)
    app.setApplicationName("Sonoteko")

    # App-Icon
    icon_path = _find_asset("icon.svg")
    if icon_path and os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    from .main_window import MainWindow, STYLE
    app.setStyleSheet(STYLE)

    window = MainWindow()
    window.show()

    # Dateien/Ordner die per CLI übergeben wurden direkt öffnen
    args = sys.argv[1:]
    if args:
        dirs = [a for a in args if os.path.isdir(a)]
        files = [a for a in args if os.path.isfile(a)]
        if dirs:
            window._library_view.start_scan(dirs)
        if files:
            window._tag_editor.load_files(files)

    sys.exit(app.exec())


def _find_asset(name: str) -> str:
    """Sucht eine Asset-Datei im Bundle oder im Projektverzeichnis."""
    candidates = [
        # PyInstaller frozen bundle
        os.path.join(getattr(sys, "_MEIPASS", ""), "assets", name),
        # Entwicklung: relativ zu diesem Modul
        os.path.join(os.path.dirname(__file__), "..", "assets", name),
        os.path.join(os.path.dirname(__file__), "assets", name),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


if __name__ == "__main__":
    main()
