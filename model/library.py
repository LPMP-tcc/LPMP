import sqlite3, mutagen, re, io

from PIL import Image
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

DATABASE_PATH = "library.db"

class Library:
    db_connection = None
    db_cursor = None
    main_window = None
    library = []

    def __init__(self):
        self.db_connection = sqlite3.connect(DATABASE_PATH)
        self.db_cursor = self.db_connection.cursor()
        self.load_full_library()

    def load_full_library(self):
        self.db_cursor.execute('''CREATE TABLE IF NOT EXISTS library 
        (track text, typed text, title text, number integer, text duration, artist text, album_arist text, album text, date text, composers text, genres text, og_metadata text)''')

        self.db_connection.commit()

        for row in self.db_cursor.execute('''SELECT * FROM library'''):
            self.library.append(self.row_tuple_into_dict(row))
        return

    def row_tuple_into_dict(self, row):
        (track, typed, title, number, duration, artist, album_artist, album, date, composers, genres, og_metadata) = row
        return {"track": track,
                "typed": typed,
                "title": title,
                "number": number,
                "duration": duration,
                "artist": artist,
                "album_artist": album_artist,
                "album": album,
                "date": date,
                "composers": composers,
                "genres": genres,
                "og_metadata": og_metadata}

    def persist_to_library(self, track, typed, title, number, duration, artist, album_artist, album, date, composers, genres, og_metadata):
        self.db_cursor.execute('''INSERT INTO library VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                               (track, typed, title, number, duration, artist, album_artist, album, date, composers, genres,
                                og_metadata))
        self.db_connection.commit()
        pass

    def remove_from_library(self, track):
        self.db_cursor.execute('''DELETE FROM library WHERE track = (?)''', track)
        self.db_connection.commit()
        pass

    def pair_with_main_window(self, main_window):
        self.main_window = main_window

    def notify_changes_to_main_window(self):
        self.main_window.notify_changes()

    def get_album_info(self, album_title, artist):
        track_list = []
        for track in self.library:
            if track["artist"] == artist and track["album"] == album_title:
                track_list.append(track)

        sorted_list = sorted(track_list, key = lambda d: d["number"])
        art = self.get_art(sorted_list[0]["track"], sorted_list[0]["typed"])
        return {"album_title": album_title,
                "artist": artist,
                "art": art,
                "track_list": sorted_list}

    def get_art(self, track, typed):
        image_bytes = None
        try:
            if typed == "MP3":
                image_bytes = ID3(track).getall("APIC")[0].data
                return image_bytes
            elif typed == "M4A":
                m_dict = mutagen.File(track)
                for key in m_dict:
                    if "covr" in key:
                        image_bytes = m_dict["covr"][0]
                        return image_bytes
            elif typed == "FLAC":
                image_bytes = FLAC(track).pictures[0].data
                return image_bytes
        except Exception as e:
            print(e)
            return self.get_placeholder_art()
        if image_bytes is None:
            return self.get_placeholder_art()
        print("Something went wrong loading art for track " + track)
        return None

    def get_placeholder_art(self):
        with open("music_ph.png", "rb") as file:
            image_bytes = file.read()
        return image_bytes

    def preprocess_files(self, files):
        for file in files:
            match = re.search("(\\.flac$)|(\\.mp3$)|(\\.m4a$)", file)
            if not match:
                print("Ignoring unsupported file type")
                continue

            m_dict = mutagen.File(file)
            if match.group(1):
                self.add_flac(file, m_dict)
            elif match.group(2):
                self.add_mp3(file, m_dict)
            elif match.group(3):
                self.add_m4a(file, m_dict)

    def add_m4a(self, file, m_dict):
        new_track = {"track": file, "typed": "M4A"}

        title = None
        number = None
        artist = None
        album_artist = None
        album = None
        date = None
        composers = None
        genres = None
        og_metadata = None

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
                date = m_dict["©day"][0]
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

        #im = Image.open(io.BytesIO(pict))
        #im.show()

        mp4 = MP4(file)
        duration = mp4.info.length
        new_track["duration"] = duration

        self.persist_to_library(file, "M4A", title, number, duration, artist, album_artist, album, date, composers, genres, None)
        self.library.append(new_track)
        self.notify_changes_to_main_window()

    def add_mp3(self, file, m_dict):
        new_track = {"track": file, "typed": "MP3"}

        title = None
        number = None
        artist = None
        album_artist = None
        album = None
        date = None
        composers = None
        genres = None
        og_metadata = None

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
                date = m_dict["TDRC"][0].get_text()
                new_track["date"] = date
            if "TRCK" == key:
                number = m_dict["TRCK"][0].split("/")[0]
                new_track["number"] = number

        mp3 = MP3(file)
        duration = mp3.info.length
        new_track["duration"] = duration

        self.persist_to_library(file, "MP3", title, number, duration, artist, album_artist, album, date, composers, genres,None)
        self.library.append(new_track)
        self.notify_changes_to_main_window()

        #pict = tags.getall('APIC')[0].data
        #im = Image.open(BytesIO(pict))
        #im.show()

    def add_flac(self, file, m_dict):
        new_track = {"track": file, "typed": "FLAC"}

        title = None
        number = None
        artist = None
        album_artist = None
        album = None
        date = None
        composers = None
        genres = None
        og_metadata = None

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
            if "tracknumber" == key:
                number = m_dict["tracknumber"][0]
                new_track["number"] = number
            if "composers" == key:
                composers = m_dict["composer"][0]
                new_track["composers"] = composers
            if "title" == key:
                title = m_dict["title"][0]
                new_track["title"] = title

        flac = FLAC(file)
        duration = flac.info.length
        new_track["duration"] = duration

        self.persist_to_library(file, "FLAC", title, number, duration, artist, album_artist, album, date, composers, genres, None)
        self.library.append(new_track)
        self.notify_changes_to_main_window()

# TrackData: dict
##  track: String, either a Spotify ID or a path
##  typed: String, either "MP3", "FLAC", "M4A", or "SPOTIFY"
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
