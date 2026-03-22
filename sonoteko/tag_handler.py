"""Tag-Lesen und -Schreiben für MP3 und FLAC, inkl. ReplayGain und Audio-Info."""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, TPOS,
    TCOM, COMM, TBPM, TPUB, TCOP, TENC, TSRC, TKEY,
    APIC, TXXX, RVA2, RGAD,
    ID3NoHeaderError
)
from mutagen.ogg import OggFileType
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4, MP4Cover


# ── Feldnamen → Beschriftungen ────────────────────────────────────────────────

FIELD_LABELS: dict[str, str] = {
    "title":         "Titel",
    "artist":        "Künstler",
    "album":         "Album",
    "albumartist":   "Album-Künstler",
    "date":          "Jahr",
    "genre":         "Genre",
    "tracknumber":   "Track-Nr.",
    "discnumber":    "Disc-Nr.",
    "composer":      "Komponist",
    "comment":       "Kommentar",
    "bpm":           "BPM",
    "publisher":     "Label / Publisher",
    "copyright":     "Copyright",
    "encoder":       "Encoder",
    "isrc":          "ISRC",
    "key":           "Tonart",
    "mood":          "Stimmung",
    "lyricist":      "Texter",
    "originalartist":"Original-Künstler",
    "subtitle":      "Untertitel",
    "originaldate":  "Original-Jahr",
    "releasedate":   "Veröffentlichungsdatum",
    "media":         "Medientyp",
    "lyrics":        "Lyrics",
    "replaygain_track_gain": "RG Track Gain",
    "replaygain_track_peak": "RG Track Peak",
    "replaygain_album_gain": "RG Album Gain",
    "replaygain_album_peak": "RG Album Peak",
}

# ID3 Frame → Feldname
ID3_MAP: dict[str, str] = {
    "TIT2": "title",
    "TPE1": "artist",
    "TALB": "album",
    "TPE2": "albumartist",
    "TDRC": "date",
    "TCON": "genre",
    "TRCK": "tracknumber",
    "TPOS": "discnumber",
    "TCOM": "composer",
    "TBPM": "bpm",
    "TPUB": "publisher",
    "TCOP": "copyright",
    "TENC": "encoder",
    "TSRC": "isrc",
    "TKEY": "key",
}

ID3_REVERSE: dict[str, type] = {
    "title":       TIT2,
    "artist":      TPE1,
    "album":       TALB,
    "albumartist": TPE2,
    "date":        TDRC,
    "genre":       TCON,
    "tracknumber": TRCK,
    "discnumber":  TPOS,
    "composer":    TCOM,
    "bpm":         TBPM,
    "publisher":   TPUB,
    "copyright":   TCOP,
    "encoder":     TENC,
    "isrc":        TSRC,
    "key":         TKEY,
}

# TXXX descriptions for extra fields
TXXX_FIELDS = {"mood", "lyricist", "originalartist", "subtitle",
               "originaldate", "releasedate", "media"}

# Vorbis Comment → Feldname
VORBIS_MAP: dict[str, str] = {
    "title":                "title",
    "artist":               "artist",
    "album":                "album",
    "albumartist":          "albumartist",
    "date":                 "date",
    "genre":                "genre",
    "tracknumber":          "tracknumber",
    "discnumber":           "discnumber",
    "composer":             "composer",
    "comment":              "comment",
    "bpm":                  "bpm",
    "organization":         "publisher",
    "copyright":            "copyright",
    "encoder":              "encoder",
    "isrc":                 "isrc",
    "initialkey":           "key",
    "mood":                 "mood",
    "lyricist":             "lyricist",
    "originalartist":       "originalartist",
    "subtitle":             "subtitle",
    "originaldate":         "originaldate",
    "releasedate":          "releasedate",
    "media":                "media",
    "lyrics":               "lyrics",
    "replaygain_track_gain":"replaygain_track_gain",
    "replaygain_track_peak":"replaygain_track_peak",
    "replaygain_album_gain":"replaygain_album_gain",
    "replaygain_album_peak":"replaygain_album_peak",
}


@dataclass
class AudioInfo:
    duration: float = 0.0       # Sekunden
    bitrate: int = 0             # kbps
    samplerate: int = 0          # Hz
    channels: int = 0
    format: str = ""
    filesize: int = 0


@dataclass
class AudioFileInfo:
    filepath: str
    format: str = ""
    tags: dict = field(default_factory=dict)
    cover_data: Optional[bytes] = None
    cover_mime: str = "image/jpeg"
    audio_info: AudioInfo = field(default_factory=AudioInfo)
    is_modified: bool = False


# ── Public API ────────────────────────────────────────────────────────────────

def read_tags(filepath: str) -> AudioFileInfo:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mp3":
        return _read_mp3(filepath)
    elif ext == ".flac":
        return _read_flac(filepath)
    elif ext in (".ogg", ".oga"):
        return _read_ogg(filepath)
    elif ext in (".m4a", ".aac", ".mp4"):
        return _read_m4a(filepath)
    else:
        return AudioFileInfo(filepath=filepath, format=ext.lstrip(".").upper())


def write_tags(filepath: str, tags: dict, cover_data: Optional[bytes] = None,
               cover_mime: str = "image/jpeg") -> bool:
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".mp3":
            _write_mp3(filepath, tags, cover_data, cover_mime)
        elif ext == ".flac":
            _write_flac(filepath, tags, cover_data, cover_mime)
        elif ext in (".ogg", ".oga"):
            _write_ogg(filepath, tags, cover_data, cover_mime)
        elif ext in (".m4a", ".aac", ".mp4"):
            _write_m4a(filepath, tags, cover_data, cover_mime)
        return True
    except Exception as e:
        print(f"[tag_handler] write_tags error for {filepath}: {e}")
        return False


def scan_directory(directory: str) -> list[str]:
    """Gibt alle Audio-Dateien in einem Verzeichnis (rekursiv) zurück."""
    supported = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".aac"}
    result = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if os.path.splitext(f)[1].lower() in supported:
                result.append(os.path.join(root, f))
    return sorted(result)


def rename_file(filepath: str, template: str, tags: dict) -> str:
    """Benennt eine Datei nach Template um. Gibt den neuen Pfad zurück."""
    ext = os.path.splitext(filepath)[1]
    name = template
    for key, value in tags.items():
        name = name.replace(f"{{{key}}}", _sanitize(str(value)))
    name = _sanitize(name) + ext
    new_path = os.path.join(os.path.dirname(filepath), name)
    if new_path != filepath:
        os.rename(filepath, new_path)
    return new_path


# ── MP3 ───────────────────────────────────────────────────────────────────────

def _read_mp3(filepath: str) -> AudioFileInfo:
    info = AudioFileInfo(filepath=filepath, format="MP3")
    try:
        audio = MP3(filepath)
        info.audio_info = AudioInfo(
            duration=audio.info.length,
            bitrate=int(audio.info.bitrate / 1000),
            samplerate=audio.info.sample_rate,
            channels=audio.info.channels,
            format="MP3",
            filesize=os.path.getsize(filepath),
        )
        tags = audio.tags
        if tags is None:
            return info
        for frame_id, field_name in ID3_MAP.items():
            frame = tags.get(frame_id)
            if frame:
                info.tags[field_name] = str(frame.text[0]) if hasattr(frame, "text") else str(frame)
        # Comment
        for key in tags:
            if key.startswith("COMM:"):
                frame = tags[key]
                info.tags["comment"] = str(frame.text[0]) if frame.text else ""
                break
        # TXXX extras
        for key in tags:
            if key.startswith("TXXX:"):
                desc = key[5:].lower()
                if desc in TXXX_FIELDS:
                    frame = tags[key]
                    info.tags[desc] = str(frame.text[0]) if frame.text else ""
        # Lyrics USLT
        for key in tags:
            if key.startswith("USLT:"):
                frame = tags[key]
                info.tags["lyrics"] = str(frame.text)
                break
        # ReplayGain
        for key in tags:
            if key.startswith("RVA2:"):
                frame = tags[key]
                if hasattr(frame, "gain"):
                    info.tags["replaygain_track_gain"] = f"{frame.gain:.2f} dB"
                    info.tags["replaygain_track_peak"] = str(frame.peak)
        # TXXX ReplayGain fallback
        for key in tags:
            if key == "TXXX:REPLAYGAIN_TRACK_GAIN":
                info.tags["replaygain_track_gain"] = str(tags[key].text[0])
            elif key == "TXXX:REPLAYGAIN_TRACK_PEAK":
                info.tags["replaygain_track_peak"] = str(tags[key].text[0])
            elif key == "TXXX:REPLAYGAIN_ALBUM_GAIN":
                info.tags["replaygain_album_gain"] = str(tags[key].text[0])
            elif key == "TXXX:REPLAYGAIN_ALBUM_PEAK":
                info.tags["replaygain_album_peak"] = str(tags[key].text[0])
        # Cover
        for key in tags:
            if key.startswith("APIC:"):
                frame = tags[key]
                info.cover_data = frame.data
                info.cover_mime = frame.mime
                break
    except Exception as e:
        print(f"[tag_handler] read_mp3 error: {e}")
    return info


def _write_mp3(filepath: str, tags: dict, cover_data: Optional[bytes],
               cover_mime: str):
    try:
        audio = ID3(filepath)
    except ID3NoHeaderError:
        audio = ID3()
    # Standard fields
    for field_name, frame_cls in ID3_REVERSE.items():
        value = tags.get(field_name, "").strip()
        if value:
            audio[frame_cls.__name__] = frame_cls(encoding=3, text=[value])
        else:
            audio.delall(frame_cls.__name__)
    # Comment
    comment = tags.get("comment", "").strip()
    audio.delall("COMM")
    if comment:
        from mutagen.id3 import COMM as COMM_
        audio["COMM::eng"] = COMM_(encoding=3, lang="eng", desc="", text=[comment])
    # TXXX extras
    for field_name in TXXX_FIELDS:
        value = tags.get(field_name, "").strip()
        key = f"TXXX:{field_name.upper()}"
        audio.delall(key)
        if value:
            audio[key] = TXXX(encoding=3, desc=field_name.upper(), text=[value])
    # Lyrics
    lyrics = tags.get("lyrics", "").strip()
    audio.delall("USLT")
    if lyrics:
        from mutagen.id3 import USLT
        audio["USLT::eng"] = USLT(encoding=3, lang="eng", desc="", text=lyrics)
    # ReplayGain as TXXX
    for rg_field in ("replaygain_track_gain", "replaygain_track_peak",
                     "replaygain_album_gain", "replaygain_album_peak"):
        value = tags.get(rg_field, "").strip()
        key = f"TXXX:{rg_field.upper()}"
        audio.delall(key)
        if value:
            audio[key] = TXXX(encoding=3, desc=rg_field.upper(), text=[value])
    # Cover
    audio.delall("APIC")
    if cover_data:
        audio["APIC:"] = APIC(
            encoding=3,
            mime=cover_mime,
            type=3,
            desc="Cover",
            data=cover_data,
        )
    audio.save(filepath)


# ── FLAC ──────────────────────────────────────────────────────────────────────

def _read_flac(filepath: str) -> AudioFileInfo:
    info = AudioFileInfo(filepath=filepath, format="FLAC")
    try:
        audio = FLAC(filepath)
        info.audio_info = AudioInfo(
            duration=audio.info.length,
            bitrate=int(audio.info.bits_per_sample * audio.info.sample_rate / 1000),
            samplerate=audio.info.sample_rate,
            channels=audio.info.channels,
            format="FLAC",
            filesize=os.path.getsize(filepath),
        )
        for vorbis_key, field_name in VORBIS_MAP.items():
            values = audio.tags.get(vorbis_key, []) if audio.tags else []
            if values:
                val = values[0]
                info.tags[field_name] = str(val) if not isinstance(val, str) else val
        # Cover
        if audio.pictures:
            pic = audio.pictures[0]
            info.cover_data = pic.data
            info.cover_mime = pic.mime
    except Exception as e:
        print(f"[tag_handler] read_flac error: {e}")
    return info


def _write_flac(filepath: str, tags: dict, cover_data: Optional[bytes],
                cover_mime: str):
    audio = FLAC(filepath)
    audio.clear()
    reverse_vorbis = {v: k for k, v in VORBIS_MAP.items()}
    for field_name, value in tags.items():
        value = str(value).strip()
        vorbis_key = reverse_vorbis.get(field_name, field_name.lower())
        if value:
            audio[vorbis_key] = [value]
    audio.clear_pictures()
    if cover_data:
        pic = Picture()
        pic.data = cover_data
        pic.mime = cover_mime
        pic.type = 3
        pic.desc = "Cover"
        audio.add_picture(pic)
    audio.save()


# ── OGG Vorbis ────────────────────────────────────────────────────────────────

def _read_ogg(filepath: str) -> AudioFileInfo:
    info = AudioFileInfo(filepath=filepath, format="OGG")
    try:
        audio = OggVorbis(filepath)
        info.audio_info = AudioInfo(
            duration=audio.info.length,
            bitrate=int(audio.info.bitrate / 1000),
            samplerate=audio.info.sample_rate,
            channels=audio.info.channels,
            format="OGG",
            filesize=os.path.getsize(filepath),
        )
        if audio.tags:
            for vorbis_key, field_name in VORBIS_MAP.items():
                values = audio.tags.get(vorbis_key, [])
                if values:
                    info.tags[field_name] = str(values[0])
    except Exception as e:
        print(f"[tag_handler] read_ogg error: {e}")
    return info


def _write_ogg(filepath: str, tags: dict, cover_data: Optional[bytes],
               cover_mime: str):
    audio = OggVorbis(filepath)
    reverse_vorbis = {v: k for k, v in VORBIS_MAP.items()}
    for field_name, value in tags.items():
        value = str(value).strip()
        vorbis_key = reverse_vorbis.get(field_name, field_name.lower())
        if value:
            audio[vorbis_key] = [value]
        elif vorbis_key in audio:
            del audio[vorbis_key]
    audio.save()


# ── M4A / AAC ─────────────────────────────────────────────────────────────────

M4A_MAP = {
    "\xa9nam": "title",
    "\xa9ART": "artist",
    "\xa9alb": "album",
    "aART":    "albumartist",
    "\xa9day": "date",
    "\xa9gen": "genre",
    "trkn":    "tracknumber",
    "disk":    "discnumber",
    "\xa9wrt": "composer",
    "\xa9cmt": "comment",
    "tmpo":    "bpm",
    "\xa9lyr": "lyrics",
    "cprt":    "copyright",
}


def _read_m4a(filepath: str) -> AudioFileInfo:
    info = AudioFileInfo(filepath=filepath, format="M4A")
    try:
        audio = MP4(filepath)
        info.audio_info = AudioInfo(
            duration=audio.info.length,
            bitrate=int(audio.info.bitrate / 1000),
            samplerate=audio.info.sample_rate,
            channels=audio.info.channels,
            format="M4A",
            filesize=os.path.getsize(filepath),
        )
        for m4a_key, field_name in M4A_MAP.items():
            val = audio.tags.get(m4a_key) if audio.tags else None
            if val:
                if isinstance(val, list):
                    v = val[0]
                    if isinstance(v, tuple):
                        info.tags[field_name] = str(v[0])
                    else:
                        info.tags[field_name] = str(v)
        if audio.tags and "covr" in audio.tags:
            cover = audio.tags["covr"][0]
            info.cover_data = bytes(cover)
            info.cover_mime = "image/png" if cover.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
    except Exception as e:
        print(f"[tag_handler] read_m4a error: {e}")
    return info


def _write_m4a(filepath: str, tags: dict, cover_data: Optional[bytes],
               cover_mime: str):
    audio = MP4(filepath)
    reverse = {v: k for k, v in M4A_MAP.items()}
    for field_name, value in tags.items():
        m4a_key = reverse.get(field_name)
        if not m4a_key:
            continue
        value = str(value).strip()
        if value:
            if m4a_key == "trkn" or m4a_key == "disk":
                try:
                    audio[m4a_key] = [(int(value.split("/")[0]), 0)]
                except ValueError:
                    pass
            elif m4a_key == "tmpo":
                try:
                    audio[m4a_key] = [int(value)]
                except ValueError:
                    pass
            else:
                audio[m4a_key] = [value]
        elif m4a_key in audio:
            del audio[m4a_key]
    if cover_data:
        fmt = MP4Cover.FORMAT_PNG if "png" in cover_mime else MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(cover_data, imageformat=fmt)]
    audio.save()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.strip(". ")


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
