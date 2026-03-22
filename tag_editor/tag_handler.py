"""Tag-Handler für MP3 (ID3) und FLAC (Vorbis Comments) Dateien."""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field

from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (
    ID3, APIC, TIT2, TPE1, TPE2, TALB, TDRC, TCON, TRCK, TPOS,
    TCOM, COMM, TBPM, TPUB, TCOP, TENC, TSRC, TKEY, TMOO,
    TIPL, TEXT, TOLY, TOPE, TSST, TDOR, TDRL, TMED, TFLT,
    PictureType,
)


# Standard-Tag-Felder mit deutschen Labels
TAG_FIELDS = {
    "title": "Titel",
    "artist": "Künstler",
    "album": "Album",
    "albumartist": "Album-Künstler",
    "date": "Jahr",
    "genre": "Genre",
    "tracknumber": "Track-Nr.",
    "discnumber": "Disc-Nr.",
    "composer": "Komponist",
    "comment": "Kommentar",
    "bpm": "BPM",
    "publisher": "Label/Verlag",
    "copyright": "Copyright",
    "encoder": "Encoder",
    "isrc": "ISRC",
    "key": "Tonart",
    "mood": "Stimmung",
    "lyricist": "Texter",
    "originalartist": "Original-Künstler",
    "subtitle": "Untertitel",
    "originaldate": "Original-Datum",
    "releasedate": "Veröffentlichungsdatum",
    "media": "Medium",
    "filetype": "Dateityp",
}

# Mapping: Unser Feld-Name -> ID3-Frame-Klasse
_ID3_MAP = {
    "title": TIT2,
    "artist": TPE1,
    "album": TALB,
    "albumartist": TPE2,
    "date": TDRC,
    "genre": TCON,
    "tracknumber": TRCK,
    "discnumber": TPOS,
    "composer": TCOM,
    "bpm": TBPM,
    "publisher": TPUB,
    "copyright": TCOP,
    "encoder": TENC,
    "isrc": TSRC,
    "key": TKEY,
    "mood": TMOO,
    "originalartist": TOPE,
    "subtitle": TSST,
    "originaldate": TDOR,
    "releasedate": TDRL,
    "media": TMED,
    "filetype": TFLT,
}

# Mapping: Unser Feld-Name -> FLAC/Vorbis Comment Key
_VORBIS_MAP = {
    "title": "TITLE",
    "artist": "ARTIST",
    "album": "ALBUM",
    "albumartist": "ALBUMARTIST",
    "date": "DATE",
    "genre": "GENRE",
    "tracknumber": "TRACKNUMBER",
    "discnumber": "DISCNUMBER",
    "composer": "COMPOSER",
    "comment": "COMMENT",
    "bpm": "BPM",
    "publisher": "PUBLISHER",
    "copyright": "COPYRIGHT",
    "encoder": "ENCODER",
    "isrc": "ISRC",
    "key": "KEY",
    "mood": "MOOD",
    "lyricist": "LYRICIST",
    "originalartist": "ORIGINALARTIST",
    "subtitle": "SUBTITLE",
    "originaldate": "ORIGINALDATE",
    "releasedate": "RELEASEDATE",
    "media": "MEDIA",
    "filetype": "FILETYPE",
}


@dataclass
class AudioFileInfo:
    """Informationen über eine Audio-Datei."""
    filepath: str
    filename: str
    file_format: str  # "mp3" oder "flac"
    tags: dict = field(default_factory=dict)
    cover_data: bytes | None = None
    cover_mime: str = ""
    extra_tags: dict = field(default_factory=dict)  # nicht-standard Tags
    bitrate: int = 0
    sample_rate: int = 0
    duration: float = 0.0
    channels: int = 0


def get_supported_extensions():
    """Gibt die unterstützten Dateiendungen zurück."""
    return {".mp3", ".flac"}


def is_supported_file(filepath: str) -> bool:
    """Prüft ob eine Datei unterstützt wird."""
    return Path(filepath).suffix.lower() in get_supported_extensions()


def read_tags(filepath: str) -> AudioFileInfo:
    """Liest alle Tags aus einer MP3- oder FLAC-Datei."""
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext == ".mp3":
        return _read_mp3_tags(filepath)
    elif ext == ".flac":
        return _read_flac_tags(filepath)
    else:
        raise ValueError(f"Nicht unterstütztes Format: {ext}")


def _read_mp3_tags(filepath: str) -> AudioFileInfo:
    """Liest Tags aus einer MP3-Datei."""
    audio = MP3(filepath)
    info = AudioFileInfo(
        filepath=filepath,
        filename=Path(filepath).name,
        file_format="mp3",
        bitrate=audio.info.bitrate // 1000 if audio.info.bitrate else 0,
        sample_rate=audio.info.sample_rate,
        duration=audio.info.length,
        channels=audio.info.channels if hasattr(audio.info, 'channels') else 2,
    )

    if audio.tags is None:
        return info

    tags = audio.tags

    # Standard-Felder auslesen
    for field_name, frame_class in _ID3_MAP.items():
        frame_id = frame_class.__name__
        if frame_id in tags:
            frame = tags[frame_id]
            info.tags[field_name] = str(frame)

    # Kommentar (COMM hat spezielle Struktur)
    for key in tags:
        if key.startswith("COMM"):
            info.tags["comment"] = str(tags[key])
            break

    # Texter (TEXT)
    if "TEXT" in tags:
        info.tags["lyricist"] = str(tags["TEXT"])

    # Cover-Art
    for key in tags:
        if key.startswith("APIC"):
            apic = tags[key]
            info.cover_data = apic.data
            info.cover_mime = apic.mime
            break

    # Extra-Tags (nicht in unserem Standard-Mapping)
    known_prefixes = set()
    for frame_class in _ID3_MAP.values():
        known_prefixes.add(frame_class.__name__)
    known_prefixes.add("APIC")
    known_prefixes.add("COMM")
    known_prefixes.add("TEXT")

    for key in tags:
        prefix = key.split(":")[0] if ":" in key else key
        if prefix not in known_prefixes:
            info.extra_tags[key] = str(tags[key])

    return info


def _read_flac_tags(filepath: str) -> AudioFileInfo:
    """Liest Tags aus einer FLAC-Datei."""
    audio = FLAC(filepath)
    info = AudioFileInfo(
        filepath=filepath,
        filename=Path(filepath).name,
        file_format="flac",
        bitrate=audio.info.bitrate // 1000 if hasattr(audio.info, 'bitrate') and audio.info.bitrate else 0,
        sample_rate=audio.info.sample_rate,
        duration=audio.info.length,
        channels=audio.info.channels,
    )

    if audio.tags is not None:
        # Standard-Felder auslesen
        for field_name, vorbis_key in _VORBIS_MAP.items():
            values = audio.tags.get(vorbis_key, [])
            if values:
                info.tags[field_name] = values[0]

        # Extra-Tags
        known_keys = set(v.upper() for v in _VORBIS_MAP.values())
        for key in audio.tags:
            if key.upper() not in known_keys:
                values = audio.tags[key]
                if values:
                    info.extra_tags[key] = values[0]

    # Cover-Art
    if audio.pictures:
        pic = audio.pictures[0]
        info.cover_data = pic.data
        info.cover_mime = pic.mime

    return info


def write_tags(filepath: str, tags: dict, cover_data: bytes | None = None,
               cover_mime: str = "image/jpeg") -> None:
    """Schreibt Tags in eine MP3- oder FLAC-Datei."""
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext == ".mp3":
        _write_mp3_tags(filepath, tags, cover_data, cover_mime)
    elif ext == ".flac":
        _write_flac_tags(filepath, tags, cover_data, cover_mime)
    else:
        raise ValueError(f"Nicht unterstütztes Format: {ext}")


def _write_mp3_tags(filepath: str, tags: dict, cover_data: bytes | None,
                    cover_mime: str) -> None:
    """Schreibt Tags in eine MP3-Datei."""
    audio = MP3(filepath)

    if audio.tags is None:
        audio.add_tags()

    id3 = audio.tags

    for field_name, value in tags.items():
        if field_name in _ID3_MAP:
            frame_class = _ID3_MAP[field_name]
            frame_id = frame_class.__name__
            if value.strip():
                id3[frame_id] = frame_class(encoding=3, text=value)
            else:
                id3.pop(frame_id, None)
        elif field_name == "comment":
            # Alte Kommentare entfernen
            keys_to_remove = [k for k in id3 if k.startswith("COMM")]
            for k in keys_to_remove:
                del id3[k]
            if value.strip():
                id3.add(COMM(encoding=3, lang="deu", desc="", text=value))
        elif field_name == "lyricist":
            if value.strip():
                id3["TEXT"] = TEXT(encoding=3, text=value)
            else:
                id3.pop("TEXT", None)

    if cover_data is not None:
        # Alte Cover entfernen
        keys_to_remove = [k for k in id3 if k.startswith("APIC")]
        for k in keys_to_remove:
            del id3[k]
        if cover_data:
            id3.add(APIC(
                encoding=3,
                mime=cover_mime,
                type=PictureType.COVER_FRONT,
                desc="Cover",
                data=cover_data,
            ))

    audio.save()


def _write_flac_tags(filepath: str, tags: dict, cover_data: bytes | None,
                     cover_mime: str) -> None:
    """Schreibt Tags in eine FLAC-Datei."""
    audio = FLAC(filepath)

    if audio.tags is None:
        audio.add_tags()

    for field_name, value in tags.items():
        if field_name in _VORBIS_MAP:
            vorbis_key = _VORBIS_MAP[field_name]
            if value.strip():
                audio.tags[vorbis_key] = [value]
            else:
                audio.tags.pop(vorbis_key, None)

    if cover_data is not None:
        audio.clear_pictures()
        if cover_data:
            pic = Picture()
            pic.type = PictureType.COVER_FRONT
            pic.mime = cover_mime
            pic.desc = "Cover"
            pic.data = cover_data
            audio.add_picture(pic)

    audio.save()


def rename_file(filepath: str, template: str, tags: dict) -> str:
    """Benennt eine Datei basierend auf einem Template und Tags um.

    Template-Variablen: {title}, {artist}, {album}, {tracknumber}, {date}, etc.
    Gibt den neuen Dateipfad zurück.
    """
    path = Path(filepath)
    ext = path.suffix

    # Template-Variablen ersetzen
    new_name = template
    for key, value in tags.items():
        placeholder = "{" + key + "}"
        if placeholder in new_name:
            # Ungültige Zeichen aus Dateinamen entfernen
            safe_value = _sanitize_filename(str(value))
            new_name = new_name.replace(placeholder, safe_value)

    # Track-Nummer mit führender Null
    if "{tracknumber:02}" in template:
        tn = tags.get("tracknumber", "0")
        # Track-Nummer kann "3/12" Format sein
        tn = tn.split("/")[0].strip()
        try:
            tn_int = int(tn)
            new_name = new_name.replace("{tracknumber:02}", f"{tn_int:02d}")
        except ValueError:
            new_name = new_name.replace("{tracknumber:02}", tn)

    new_name = new_name + ext
    new_path = path.parent / new_name

    if new_path == path:
        return filepath

    # Sicherstellen, dass keine Datei überschrieben wird
    if new_path.exists():
        raise FileExistsError(f"Datei existiert bereits: {new_path}")

    path.rename(new_path)
    return str(new_path)


def _sanitize_filename(name: str) -> str:
    """Entfernt ungültige Zeichen aus einem Dateinamen."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip(". ")


def scan_directory(dirpath: str, recursive: bool = True) -> list[str]:
    """Scannt ein Verzeichnis nach unterstützten Audio-Dateien."""
    results = []
    path = Path(dirpath)

    if recursive:
        for ext in get_supported_extensions():
            results.extend(str(p) for p in path.rglob(f"*{ext}"))
    else:
        for ext in get_supported_extensions():
            results.extend(str(p) for p in path.glob(f"*{ext}"))

    results.sort()
    return results
