# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec für Sonoteko — erzeugt eine standalone macOS .app."""

import sys
from pathlib import Path
import PyQt6 as _pyqt6
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Locate Qt frameworks bundled with PyQt6.
# QtDBus is required by QtGui but is often missed.
_qt_lib = Path(_pyqt6.__file__).parent / 'Qt6' / 'lib'
_qt_frameworks = []
for _fw in ('QtDBus',):
    _binary = _qt_lib / f'{_fw}.framework' / 'Versions' / 'A' / _fw
    if _binary.exists():
        _qt_frameworks.append((str(_binary), f'{_fw}.framework/Versions/A'))

a = Analysis(
    ['sonoteko/main.py'],
    pathex=[str(Path('.').resolve())],
    target_arch='arm64',
    binaries=_qt_frameworks,
    datas=[
        ('qt.conf', '.'),
        ('assets/icon.svg', 'assets'),
    ],
    hiddenimports=(
        collect_submodules('sonoteko') +
        collect_submodules('mutagen') +
        [
            'PIL',
            'PIL.Image',
            'requests',
            'PyQt6.QtMultimedia',
            'PyQt6.QtMultimediaWidgets',
            'xml.etree.ElementTree',
            'xml.dom.minidom',
            'sqlite3',
            'json',
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Sonoteko',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='Sonoteko',
)

app = BUNDLE(
    coll,
    name='Sonoteko.app',
    icon='assets/icon.icns',
    bundle_identifier='de.hasi.sonoteko',
    info_plist={
        'CFBundleName': 'Sonoteko',
        'CFBundleDisplayName': 'Sonoteko',
        'CFBundleShortVersionString': '2.0.0',
        'CFBundleVersion': '2.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'MP3 Audio',
                'CFBundleTypeExtensions': ['mp3'],
                'CFBundleTypeRole': 'Editor',
            },
            {
                'CFBundleTypeName': 'FLAC Audio',
                'CFBundleTypeExtensions': ['flac'],
                'CFBundleTypeRole': 'Editor',
            },
            {
                'CFBundleTypeName': 'OGG Audio',
                'CFBundleTypeExtensions': ['ogg', 'oga'],
                'CFBundleTypeRole': 'Editor',
            },
            {
                'CFBundleTypeName': 'M4A Audio',
                'CFBundleTypeExtensions': ['m4a', 'aac'],
                'CFBundleTypeRole': 'Editor',
            },
        ],
    },
)
