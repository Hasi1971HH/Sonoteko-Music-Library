"""SQLite-Datenbank für die Sonoteko Music Library."""

import sqlite3
import os
import time
from typing import Optional
from dataclasses import dataclass, field


DB_PATH = os.path.join(os.path.expanduser("~"), ".sonoteko", "library.db")


@dataclass
class TrackRecord:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    albumartist: str = ""
    year: str = ""
    genre: str = ""
    tracknumber: str = ""
    discnumber: str = ""
    composer: str = ""
    comment: str = ""
    bpm: str = ""
    isrc: str = ""
    duration: float = 0.0
    bitrate: int = 0
    samplerate: int = 0
    channels: int = 0
    format: str = ""
    filesize: int = 0
    has_cover: bool = False
    replaygain_track_gain: str = ""
    replaygain_track_peak: str = ""
    replaygain_album_gain: str = ""
    replaygain_album_peak: str = ""
    date_added: float = field(default_factory=time.time)
    date_modified: float = 0.0
    play_count: int = 0
    rating: int = 0


class LibraryDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                path TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                artist TEXT DEFAULT '',
                album TEXT DEFAULT '',
                albumartist TEXT DEFAULT '',
                year TEXT DEFAULT '',
                genre TEXT DEFAULT '',
                tracknumber TEXT DEFAULT '',
                discnumber TEXT DEFAULT '',
                composer TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                bpm TEXT DEFAULT '',
                isrc TEXT DEFAULT '',
                duration REAL DEFAULT 0,
                bitrate INTEGER DEFAULT 0,
                samplerate INTEGER DEFAULT 0,
                channels INTEGER DEFAULT 0,
                format TEXT DEFAULT '',
                filesize INTEGER DEFAULT 0,
                has_cover INTEGER DEFAULT 0,
                replaygain_track_gain TEXT DEFAULT '',
                replaygain_track_peak TEXT DEFAULT '',
                replaygain_album_gain TEXT DEFAULT '',
                replaygain_album_peak TEXT DEFAULT '',
                date_added REAL DEFAULT 0,
                date_modified REAL DEFAULT 0,
                play_count INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at REAL DEFAULT 0,
                updated_at REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS playlist_tracks (
                playlist_id INTEGER NOT NULL,
                track_path TEXT NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY (playlist_id, track_path),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (track_path) REFERENCES tracks(path) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
            CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album);
            CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
        """)
        conn.commit()

    # ── Track operations ──────────────────────────────────────────────────────

    def upsert_track(self, record: TrackRecord):
        conn = self._connect()
        conn.execute("""
            INSERT INTO tracks (
                path, title, artist, album, albumartist, year, genre,
                tracknumber, discnumber, composer, comment, bpm, isrc,
                duration, bitrate, samplerate, channels, format, filesize,
                has_cover, replaygain_track_gain, replaygain_track_peak,
                replaygain_album_gain, replaygain_album_peak,
                date_added, date_modified, play_count, rating
            ) VALUES (
                :path, :title, :artist, :album, :albumartist, :year, :genre,
                :tracknumber, :discnumber, :composer, :comment, :bpm, :isrc,
                :duration, :bitrate, :samplerate, :channels, :format, :filesize,
                :has_cover, :replaygain_track_gain, :replaygain_track_peak,
                :replaygain_album_gain, :replaygain_album_peak,
                :date_added, :date_modified, :play_count, :rating
            ) ON CONFLICT(path) DO UPDATE SET
                title=excluded.title, artist=excluded.artist,
                album=excluded.album, albumartist=excluded.albumartist,
                year=excluded.year, genre=excluded.genre,
                tracknumber=excluded.tracknumber, discnumber=excluded.discnumber,
                composer=excluded.composer, comment=excluded.comment,
                bpm=excluded.bpm, isrc=excluded.isrc,
                duration=excluded.duration, bitrate=excluded.bitrate,
                samplerate=excluded.samplerate, channels=excluded.channels,
                format=excluded.format, filesize=excluded.filesize,
                has_cover=excluded.has_cover,
                replaygain_track_gain=excluded.replaygain_track_gain,
                replaygain_track_peak=excluded.replaygain_track_peak,
                replaygain_album_gain=excluded.replaygain_album_gain,
                replaygain_album_peak=excluded.replaygain_album_peak,
                date_modified=excluded.date_modified
        """, record.__dict__)
        conn.commit()

    def get_all_tracks(self) -> list[TrackRecord]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM tracks ORDER BY artist, album, tracknumber"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_track(self, path: str) -> Optional[TrackRecord]:
        conn = self._connect()
        row = conn.execute("SELECT * FROM tracks WHERE path=?", (path,)).fetchone()
        return self._row_to_record(row) if row else None

    def search_tracks(self, query: str) -> list[TrackRecord]:
        q = f"%{query}%"
        conn = self._connect()
        rows = conn.execute("""
            SELECT * FROM tracks
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
               OR genre LIKE ? OR composer LIKE ?
            ORDER BY artist, album, tracknumber
        """, (q, q, q, q, q)).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_tracks_by_artist(self, artist: str) -> list[TrackRecord]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM tracks WHERE artist=? ORDER BY album, tracknumber",
            (artist,)
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_tracks_by_album(self, album: str) -> list[TrackRecord]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM tracks WHERE album=? ORDER BY tracknumber",
            (album,)
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def delete_track(self, path: str):
        conn = self._connect()
        conn.execute("DELETE FROM tracks WHERE path=?", (path,))
        conn.commit()

    def delete_missing_tracks(self):
        """Entfernt alle Tracks aus der DB deren Datei nicht mehr existiert."""
        conn = self._connect()
        all_paths = conn.execute("SELECT path FROM tracks").fetchall()
        removed = 0
        for row in all_paths:
            if not os.path.exists(row["path"]):
                conn.execute("DELETE FROM tracks WHERE path=?", (row["path"],))
                removed += 1
        conn.commit()
        return removed

    def update_play_count(self, path: str):
        conn = self._connect()
        conn.execute(
            "UPDATE tracks SET play_count = play_count + 1 WHERE path=?",
            (path,)
        )
        conn.commit()

    def update_rating(self, path: str, rating: int):
        conn = self._connect()
        conn.execute(
            "UPDATE tracks SET rating=? WHERE path=?",
            (max(0, min(5, rating)), path)
        )
        conn.commit()

    def get_all_artists(self) -> list[str]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT artist FROM tracks WHERE artist != '' ORDER BY artist"
        ).fetchall()
        return [r["artist"] for r in rows]

    def get_all_albums(self) -> list[str]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT album FROM tracks WHERE album != '' ORDER BY album"
        ).fetchall()
        return [r["album"] for r in rows]

    def get_all_genres(self) -> list[str]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT genre FROM tracks WHERE genre != '' ORDER BY genre"
        ).fetchall()
        return [r["genre"] for r in rows]

    def get_stats(self) -> dict:
        conn = self._connect()
        row = conn.execute("""
            SELECT
                COUNT(*) as total_tracks,
                COUNT(DISTINCT artist) as total_artists,
                COUNT(DISTINCT album) as total_albums,
                SUM(duration) as total_duration,
                SUM(filesize) as total_size
            FROM tracks
        """).fetchone()
        return dict(row)

    # ── Playlist operations ───────────────────────────────────────────────────

    def create_playlist(self, name: str, description: str = "") -> int:
        conn = self._connect()
        now = time.time()
        cur = conn.execute(
            "INSERT INTO playlists (name, description, created_at, updated_at) VALUES (?,?,?,?)",
            (name, description, now, now)
        )
        conn.commit()
        return cur.lastrowid

    def get_all_playlists(self) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM playlists ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_playlist(self, playlist_id: int) -> Optional[dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM playlists WHERE id=?", (playlist_id,)
        ).fetchone()
        return dict(row) if row else None

    def rename_playlist(self, playlist_id: int, name: str):
        conn = self._connect()
        conn.execute(
            "UPDATE playlists SET name=?, updated_at=? WHERE id=?",
            (name, time.time(), playlist_id)
        )
        conn.commit()

    def delete_playlist(self, playlist_id: int):
        conn = self._connect()
        conn.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
        conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
        conn.commit()

    def add_track_to_playlist(self, playlist_id: int, track_path: str):
        conn = self._connect()
        row = conn.execute(
            "SELECT MAX(position) FROM playlist_tracks WHERE playlist_id=?",
            (playlist_id,)
        ).fetchone()
        pos = (row[0] or 0) + 1
        conn.execute(
            "INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_path, position) VALUES (?,?,?)",
            (playlist_id, track_path, pos)
        )
        conn.execute(
            "UPDATE playlists SET updated_at=? WHERE id=?",
            (time.time(), playlist_id)
        )
        conn.commit()

    def remove_track_from_playlist(self, playlist_id: int, track_path: str):
        conn = self._connect()
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id=? AND track_path=?",
            (playlist_id, track_path)
        )
        conn.commit()

    def get_playlist_tracks(self, playlist_id: int) -> list[TrackRecord]:
        conn = self._connect()
        rows = conn.execute("""
            SELECT t.* FROM tracks t
            JOIN playlist_tracks pt ON t.path = pt.track_path
            WHERE pt.playlist_id = ?
            ORDER BY pt.position
        """, (playlist_id,)).fetchall()
        return [self._row_to_record(r) for r in rows]

    def reorder_playlist(self, playlist_id: int, ordered_paths: list[str]):
        conn = self._connect()
        for i, path in enumerate(ordered_paths):
            conn.execute(
                "UPDATE playlist_tracks SET position=? WHERE playlist_id=? AND track_path=?",
                (i + 1, playlist_id, path)
            )
        conn.commit()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _row_to_record(self, row: sqlite3.Row) -> TrackRecord:
        d = dict(row)
        d["has_cover"] = bool(d.get("has_cover", 0))
        return TrackRecord(**d)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
