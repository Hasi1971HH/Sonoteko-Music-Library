# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec für Hasi's ID3-Tag-Editor — erzeugt eine standalone .app."""

import sys
from pathlib import Path
import PyQt6 as _pyqt6

block_cipher = None

# Locate Qt frameworks bundled with PyQt6.
# PyInstaller does not always follow rpath-based Qt framework dependencies
# automatically; QtDBus is required by QtGui but is often missed.
_qt_lib = Path(_pyqt6.__file__).parent / 'Qt6' / 'lib'
_qt_frameworks = []
for _fw in ('QtDBus',):
    _binary = _qt_lib / f'{_fw}.framework' / 'Versions' / 'A' / _fw
    if _binary.exists():
        _qt_frameworks.append((str(_binary), f'{_fw}.framework/Versions/A'))

a = Analysis(
    ['tag_editor/main.py'],
    pathex=[],
    binaries=_qt_frameworks,
    # qt.conf must land *next to the executable* (destination '.') so that Qt
    # finds it before it falls back to CFBundleGetMainBundle().  That CFBundle
    # call crashes on macOS 15+ / 26.x due to PAC-protected CoreFoundation
    # objects.  Providing qt.conf here is the version-independent safeguard;
    # the QT_QPA_NO_BUNDLE_LOOKUP env-var set in main.py covers Qt 6.7.2+.
    datas=[('qt.conf', '.')],
    hiddenimports=[
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.id3',
        'mutagen.id3._frames',
        'PIL',
    ],
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
    name='HasisTagEditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='universal2',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='HasisTagEditor',
)

app = BUNDLE(
    coll,
    name="Hasi's ID3-Tag-Editor.app",
    icon=None,
    bundle_identifier='de.hasi.id3tageditor',
    info_plist={
        'CFBundleName': "Hasi's ID3-Tag-Editor",
        'CFBundleDisplayName': "Hasi's ID3-Tag-Editor",
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # Dark Mode Support
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
        ],
    },
)
