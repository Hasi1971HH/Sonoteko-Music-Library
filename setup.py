from setuptools import setup, find_packages

setup(
    name="sonoteko",
    version="2.0.0",
    description="Sonoteko — Musik-Library-Software mit Tag-Editor, MusicBrainz, AcoustID, Lyrics, ReplayGain und mehr",
    author="Hasi",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.7.2",
        "mutagen>=1.47.0",
        "Pillow>=10.0.0",
        "requests>=2.31.0",
        "pyacoustid>=1.3.0",
    ],
    entry_points={
        "console_scripts": [
            "sonoteko=sonoteko.main:main",
        ],
    },
    python_requires=">=3.10",
)
