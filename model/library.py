import sqlite3, mutagen, re, os, json

from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

from model.track_type import TrackType

DATABASE_PATH = "library.db"

# Supported local audio extensions (case-insensitive).
_SUPPORTED_AUDIO_RE = re.compile(r"\.(flac|mp3|m4a)$", re.IGNORECASE)


class Library:
    db_connection = None
    db_cursor = None
    main_window = None
    library = []

    @staticmethod
    def _normalize_date(date_string):
        if not date_string:
            return ""
        date_string = str(date_string).strip()
        if re.match(r'^\d{4}$', date_string):
            return f"{date_string}-01-01"
        if re.match(r'^\d{4}-\d{2}$', date_string):
            return f"{date_string}-01"
        if re.match(r'^\d{4}-\d{2}-\d{2}', date_string):
            return date_string[:10]
        return date_string

    @staticmethod
    def _track_sort_key(t):
        try:
            d = int(t.get('disc') or 1)
        except (TypeError, ValueError):
            d = 1
        try:
            n = int(t.get('number') or 0)
        except (TypeError, ValueError):
            n = 0
        return (d, n)

    def __init__(self):
        self.db_connection = sqlite3.connect(DATABASE_PATH)
        self.db_cursor = self.db_connection.cursor()
        self._load_full_library()

    def _load_full_library(self):
        self.db_cursor.execute('''CREATE TABLE IF NOT EXISTS library
        (id INTEGER PRIMARY KEY AUTOINCREMENT, track TEXT, typed TEXT CHECK(typed IN ('MP3', 'FLAC', 'M4A', 'SPOTIFY')), title TEXT, number INTEGER, duration TEXT, artist TEXT, album_artist TEXT, album TEXT, date TEXT, composers TEXT, genres TEXT, og_metadata TEXT, disc INTEGER)''')

        self.db_cursor.execute('''CREATE TABLE IF NOT EXISTS views
        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, pipeline TEXT NOT NULL)''')

        self.db_cursor.execute('''CREATE TABLE IF NOT EXISTS playlists
        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)''')

        self.db_cursor.execute('''CREATE TABLE IF NOT EXISTS playlist_tracks
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         playlist_id INTEGER NOT NULL,
         track_path  TEXT NOT NULL,
         position    INTEGER NOT NULL)''')

        self.db_connection.commit()

        for row in self.db_cursor.execute('''SELECT * FROM library'''):
            self.library.append(self._row_tuple_into_dict(row))
        return

    def _row_tuple_into_dict(self, row):
        (_, track, typed, title, number, duration, artist, album_artist, album, date, composers, genres, og_metadata, disc) = row
        return {"track": track,
                "typed": TrackType(typed),
                "title": title,
                "number": number,
                "duration": duration,
                "artist": artist,
                "album_artist": album_artist,
                "album": album,
                "date": self._normalize_date(date),
                "composers": composers,
                "genres": genres,
                "og_metadata": og_metadata,
                "disc": disc}

    def _persist_to_library(self, track, typed, title, number, duration, artist, album_artist, album, date, composers, genres, og_metadata, disc=None):
        self.db_cursor.execute(
            '''INSERT INTO library (track, typed, title, number, duration, artist, album_artist, album, date, composers, genres, og_metadata, disc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (track, typed, title, number, duration, artist, album_artist, album, date, composers, genres, og_metadata, disc),
        )
        self.db_connection.commit()

    def update_track_metadata(self, track_path, updated_fields, notify=True):
        track = next((t for t in self.library if t['track'] == track_path), None)
        if track is None:
            return
        # Preserve original values in og_metadata on first edit
        if track.get('og_metadata') is None:
            original = {k: v for k, v in track.items() if k not in ('track', 'typed', 'og_metadata')}
            track['og_metadata'] = json.dumps(original)
        for key, value in updated_fields.items():
            track[key] = value
        self.db_cursor.execute(
            '''UPDATE library SET title=?, number=?, disc=?, artist=?, album_artist=?, album=?,
               date=?, composers=?, genres=?, og_metadata=? WHERE track=?''',
            (track['title'], track.get('number'), track.get('disc'),
             track['artist'], track.get('album_artist', ''),
             track['album'], track.get('date', ''), track.get('composers', ''), track.get('genres', ''),
             track['og_metadata'], track_path),
        )
        self.db_connection.commit()
        if notify:
            self._notify_changes_to_main_window()

    def remove_tracks_batch(self, track_paths):
        paths = set(track_paths)
        for path in paths:
            self.db_cursor.execute('DELETE FROM library WHERE track = ?', (path,))
        self.db_connection.commit()
        self.library = [t for t in self.library if t['track'] not in paths]
        self._notify_changes_to_main_window()

    def remove_album(self, album_title, album_artist):
        # find all tracks that belong to an album and remove them
        paths = [
            t['track'] for t in self.library
            if t.get('album') == album_title
            and (t.get('album_artist') or t.get('artist')) == album_artist
        ]
        if paths:
            self.remove_tracks_batch(paths)

    def pair_with_main_window(self, main_window):
        self.main_window = main_window

    def _notify_changes_to_main_window(self):
        self.main_window.notify_changes()

    def get_album_info(self, album_title, album_artist):
        track_list = []
        for track in self.library:
            effective = track.get('album_artist') or track.get('artist')
            if effective == album_artist and track.get('album') == album_title:
                track_list.append(track)

        sorted_list = sorted(track_list, key=self._track_sort_key)
        art = self.get_art(sorted_list[0]["track"], sorted_list[0]["typed"])
        return {"album_title": album_title,
                "artist": album_artist,
                "art": art,
                "track_list": sorted_list}

    def get_all_album_summaries(self):
        """Return one summary dict per album, efficient for grid views.

        Uses the first track seen per (album, album_artist) pair for the date and art.
        Does not load full track lists — use get_album_info() when you need those.
        """
        seen = {}
        for track in self.library:
            effective_artist = track.get('album_artist') or track.get('artist')
            key = (track.get("album"), effective_artist)
            if key not in seen:
                seen[key] = track
        summaries = []
        for (album, artist), first_track in seen.items():
            art = self.get_art(first_track["track"], first_track["typed"])
            summaries.append({
                "album_title": album or "",
                "artist": artist or "",
                "date": first_track.get("date") or "",
                "genres": first_track.get("genres") or "",
                "art": art,
            })
        return summaries

    def get_art(self, track, typed):
        try:
            match typed:
                case TrackType.MP3:
                    frames = ID3(track).getall("APIC")
                    if frames:
                        return frames[0].data
                case TrackType.M4A:
                    m_dict = mutagen.File(track)
                    for key in m_dict:
                        if "covr" in key:
                            return m_dict["covr"][0]
                case TrackType.FLAC:
                    pictures = FLAC(track).pictures
                    if pictures:
                        return pictures[0].data
                case TrackType.SPOTIFY:
                    art_path = os.path.join("spotify_art", f"{track}.jpg")
                    with open(art_path, "rb") as f:
                        return f.read()
        except Exception as e:
            print(e)
        return self.get_placeholder_art()

    def add_spotify_track(self, track_data, art_bytes):
        track_id = track_data["uri"].split(":")[-1]
        if any(t["track"] == track_id for t in self.library):
            return

        os.makedirs("spotify_art", exist_ok=True)
        art_path = os.path.join("spotify_art", f"{track_id}.jpg")
        with open(art_path, "wb") as f:
            f.write(art_bytes)

        title        = track_data.get("title", "")
        artist       = track_data.get("artist", "")
        album_artist = track_data.get("album_artist") or artist
        album        = track_data.get("album", "")
        number       = track_data.get("track_number", 0)
        disc         = track_data.get("disc_number") or None
        duration     = track_data.get("duration_ms", 0) / 1000.0
        date         = self._normalize_date(track_data.get("release_date", ""))
        serializable_data = dict(track_data)
        serializable_data.pop("art", None)
        og_metadata = json.dumps(serializable_data)

        new_track = {
            "track": track_id, "typed": TrackType.SPOTIFY,
            "title": title, "number": number, "disc": disc, "duration": duration,
            "artist": artist, "album_artist": album_artist,
            "album": album, "date": date,
            "composers": "", "genres": "",
            "og_metadata": og_metadata,
        }
        self._persist_to_library(track_id, TrackType.SPOTIFY, title, number, duration,
                                artist, album_artist, album, date, "", "", og_metadata, disc=disc)
        self.library.append(new_track)
        self._notify_changes_to_main_window()

    def save_view(self, name, pipeline_dict):
        """Persist a named view and return its new row id."""
        self.db_cursor.execute(
            '''INSERT INTO views (name, pipeline) VALUES (?, ?)''',
            (name, json.dumps(pipeline_dict))
        )
        self.db_connection.commit()
        return self.db_cursor.lastrowid

    def load_all_views(self):
        """Return all saved views as a list of {id, name, pipeline} dicts."""
        rows = self.db_cursor.execute(
            '''SELECT id, name, pipeline FROM views'''
        ).fetchall()
        return [{"id": r[0], "name": r[1], "pipeline": json.loads(r[2])}
                for r in rows]

    def update_view(self, view_id, name, pipeline_dict):
        self.db_cursor.execute(
            'UPDATE views SET name = ?, pipeline = ? WHERE id = ?',
            (name, json.dumps(pipeline_dict), view_id)
        )
        self.db_connection.commit()

    def delete_view(self, view_id):
        self.db_cursor.execute('DELETE FROM views WHERE id = ?', (view_id,))
        self.db_connection.commit()

    # ------------------------------------------------------------------
    # Playlist persistence
    # ------------------------------------------------------------------

    def create_playlist(self, name):
        self.db_cursor.execute('INSERT INTO playlists (name) VALUES (?)', (name,))
        self.db_connection.commit()
        return self.db_cursor.lastrowid

    def rename_playlist(self, playlist_id, name):
        self.db_cursor.execute('UPDATE playlists SET name = ? WHERE id = ?', (name, playlist_id))
        self.db_connection.commit()

    def delete_playlist(self, playlist_id):
        self.db_cursor.execute('DELETE FROM playlist_tracks WHERE playlist_id = ?', (playlist_id,))
        self.db_cursor.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
        self.db_connection.commit()

    def load_all_playlists(self):
        rows = self.db_cursor.execute(
            'SELECT id, name FROM playlists ORDER BY id'
        ).fetchall()
        return [{'id': r[0], 'name': r[1]} for r in rows]

    def add_track_to_playlist(self, playlist_id, track_path):
        row = self.db_cursor.execute(
            'SELECT COALESCE(MAX(position), 0) + 1 FROM playlist_tracks WHERE playlist_id = ?',
            (playlist_id,)
        ).fetchone()
        self.db_cursor.execute(
            'INSERT INTO playlist_tracks (playlist_id, track_path, position) VALUES (?, ?, ?)',
            (playlist_id, track_path, row[0])
        )
        self.db_connection.commit()

    def get_playlist_tracks(self, playlist_id):
        """Return track dicts in playlist position order, skipping removed tracks."""
        rows = self.db_cursor.execute(
            'SELECT track_path FROM playlist_tracks WHERE playlist_id = ? ORDER BY position',
            (playlist_id,)
        ).fetchall()
        track_map = {t['track']: t for t in self.library}
        return [track_map[r[0]] for r in rows if r[0] in track_map]

    def update_playlist_order(self, playlist_id, ordered_track_paths):
        """Replace the stored order for a playlist (used for drag-reorder and removals)."""
        self.db_cursor.execute('DELETE FROM playlist_tracks WHERE playlist_id = ?', (playlist_id,))
        for pos, path in enumerate(ordered_track_paths, start=1):
            self.db_cursor.execute(
                'INSERT INTO playlist_tracks (playlist_id, track_path, position) VALUES (?, ?, ?)',
                (playlist_id, path, pos)
            )
        self.db_connection.commit()

    def get_placeholder_art(self):
        with open("music_ph.png", "rb") as file:
            image_bytes = file.read()
        return image_bytes

    def preprocess_files(self, paths):
        # paths may contain both files and directories; directories are scanned
        # recursively for supported audio files.
        files = self._collect_audio_files(paths)
        existing = {t['track'] for t in self.library}
        for file in files:
            if file in existing:
                continue  # already in the library; skip

            match = _SUPPORTED_AUDIO_RE.search(file)
            if not match:
                print("Ignoring unsupported file type")
                continue

            existing.add(file)
            m_dict = mutagen.File(file)
            ext = match.group(1).lower()
            if ext == 'flac':
                self._add_flac(file, m_dict)
            elif ext == 'mp3':
                self._add_mp3(file, m_dict)
            elif ext == 'm4a':
                self._add_m4a(file, m_dict)

    @staticmethod
    def _collect_audio_files(paths):
        """Flatten files and directories into a list of supported audio files."""
        collected = []
        for path in paths:
            if os.path.isdir(path):
                for root, _dirs, names in os.walk(path):
                    for name in names:
                        if _SUPPORTED_AUDIO_RE.search(name):
                            collected.append(os.path.join(root, name))
            else:
                collected.append(path)
        return collected

    def _add_m4a(self, file, m_dict):
        new_track = {"track": file, "typed": TrackType.M4A}

        title = None
        number = None
        disc = None
        artist = None
        album_artist = None
        album = None
        date = None
        composers = None
        genres = None

        for key in m_dict:
            if "©alb" == key:
                album = m_dict["©alb"][0]
                new_track["album"] = album
            if "©ART" == key:
                artist = m_dict["©ART"][0]
                new_track["artist"] = artist
            if "aART" == key:
                album_artist = m_dict["aART"][0]
                new_track["album_artist"] = album_artist
            if "©gen" == key:
                genres = m_dict["©gen"][0]
                new_track["genres"] = genres
            if "©day" == key:
                date = self._normalize_date(m_dict["©day"][0])
                new_track["date"] = date
            if "©wrt" == key:
                composers = m_dict["©wrt"][0]
                new_track["composers"] = composers
            if "©nam" == key:
                title = m_dict["©nam"][0]
                new_track["title"] = title
            if "trkn" == key:
                number, _ = m_dict["trkn"][0]
                number = int(number)
                new_track["number"] = number
            if "disk" == key:
                disc_val, _ = m_dict["disk"][0]
                disc = int(disc_val) if disc_val else None
                new_track["disc"] = disc

        mp4 = MP4(file)
        duration = mp4.info.length
        new_track["duration"] = duration

        self._persist_to_library(file, TrackType.M4A, title, number, duration, artist, album_artist, album, date, composers, genres, None, disc=disc)
        self.library.append(new_track)
        self._notify_changes_to_main_window()

    def _add_mp3(self, file, m_dict):
        new_track = {"track": file, "typed": TrackType.MP3}

        title = None
        number = None
        disc = None
        artist = None
        album_artist = None
        album = None
        date = None
        composers = None
        genres = None

        for key in m_dict:
            if "TIT2" == key:
                title = m_dict["TIT2"][0]
                new_track["title"] = title
            if "TALB" == key:
                album =  m_dict["TALB"][0]
                new_track["album"] = album
            if "TPE1" == key:
                artist = m_dict["TPE1"][0]
                new_track["artist"] = artist
            if "TPE2" == key:
                album_artist = m_dict["TPE2"][0]
                new_track["album_artist"] = album_artist
            if "TCON" == key:
                genres = m_dict["TCON"][0]
                new_track["genres"] = genres
            if "TDRC" == key:
                date = self._normalize_date(m_dict["TDRC"][0].get_text())
                new_track["date"] = date
            if "TRCK" == key:
                number = m_dict["TRCK"][0].split("/")[0]
                new_track["number"] = number
            if "TPOS" == key:
                try:
                    disc = int(str(m_dict["TPOS"][0]).split("/")[0])
                except (ValueError, IndexError):
                    disc = None
                new_track["disc"] = disc

        mp3 = MP3(file)
        duration = mp3.info.length
        new_track["duration"] = duration

        self._persist_to_library(file, TrackType.MP3, title, number, duration, artist, album_artist, album, date, composers, genres, None, disc=disc)
        self.library.append(new_track)
        self._notify_changes_to_main_window()

    def _add_flac(self, file, m_dict):
        new_track = {"track": file, "typed": TrackType.FLAC}

        title = None
        number = None
        disc = None
        artist = None
        album_artist = None
        album = None
        date = None
        composers = None
        genres = None

        for key in m_dict:
            if "album" == key:
                album = m_dict["album"][0]
                new_track["album"] = album
            if "albumartist" == key:
                album_artist = m_dict["albumartist"][0]
                new_track["album_artist"] = album_artist
            if "performer" == key:
                artist = m_dict["performer"][0]
                new_track["artist"] = artist
            if "artist" == key:
                artist = m_dict["artist"][0]
                new_track["artist"] = artist # this is dumb. FIX IT BETTER
            if "genre" == key:
                genres = m_dict["genre"][0]
                new_track["genres"] = genres
            if "date" == key:
                date = self._normalize_date(m_dict["date"][0])
                new_track["date"] = date
            if "tracknumber" == key:
                number = m_dict["tracknumber"][0]
                new_track["number"] = number
            if "discnumber" == key:
                try:
                    disc = int(str(m_dict["discnumber"][0]).split("/")[0])
                except (ValueError, IndexError):
                    disc = None
                new_track["disc"] = disc
            if "composer" == key:
                composers = m_dict["composer"][0]
                new_track["composers"] = composers
            if "title" == key:
                title = m_dict["title"][0]
                new_track["title"] = title

        flac = FLAC(file)
        duration = flac.info.length
        new_track["duration"] = duration

        self._persist_to_library(file, TrackType.FLAC, title, number, duration, artist, album_artist, album, date, composers, genres, None, disc=disc)
        self.library.append(new_track)
        self._notify_changes_to_main_window()

# TrackData: dict
##  track: String, either a Spotify ID or a path
##  typed: TrackType
##  title: String, track name
##  number: Int, track number
##  duration: String, track duration
##  artist: List of Strings, artist name
##  album artist: String, discriminant for albums with multiple artists
##  album: String, album name
##  date: String, an ISO date string (release date)
##  composers: List of Strings, composer names
##  genres: List of Strings, musical genres
##  ...
##  original metadata: Dict, either the original IDv3 information of a local track or the Spotify metadata
