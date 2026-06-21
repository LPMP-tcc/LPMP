from enum import Enum


class TrackType(str, Enum):
    MP3     = "MP3"
    FLAC    = "FLAC"
    M4A     = "M4A"
    SPOTIFY = "SPOTIFY"
