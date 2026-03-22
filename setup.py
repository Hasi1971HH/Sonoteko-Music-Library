from setuptools import setup, find_packages

setup(
    name="hasis-id3-tag-editor",
    version="1.0.0",
    description="Ein benutzerfreundlicher ID3-Tag-Editor für MP3 und FLAC Dateien",
    author="Hasi",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.5.0",
        "mutagen>=1.47.0",
        "Pillow>=10.0.0",
    ],
    entry_points={
        "console_scripts": [
            "hasi-tag-editor=tag_editor.main:main",
        ],
    },
    python_requires=">=3.10",
)
