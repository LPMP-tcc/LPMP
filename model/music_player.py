from model.vlc_player import VlcPlayer
from model.librespot_player import LibrespotPlayer
from model.track_type import TrackType


class MusicPlayer:
    def __init__(self):
        self.vlc = VlcPlayer()
        self.librespot = LibrespotPlayer()

    @property
    def is_playing(self):
        return self.vlc.is_playing or self.librespot.is_playing

    def play(self, track, typed):
        self.pause_all()
        if typed == TrackType.SPOTIFY:
            self.librespot.play(track)
        else:
            self.vlc.play(track)

    def pause_all(self):
        if self.vlc.is_playing:
            self.vlc.pause()
        elif self.librespot.is_playing:
            self.librespot.pause()

    def resume_all(self):
        if self.vlc.is_paused:
            self.vlc.resume()
        elif not self.vlc.is_playing and not self.librespot.is_playing:
            self.librespot.resume()

    def set_volume(self, value):
        self.vlc.set_volume(value)
        self.librespot.set_volume(value)

    def get_new_slider_position(self, curr_slider_position):
        if self.vlc.is_playing:
            return self.vlc.get_position()
        elif self.librespot.is_playing:
            return self.librespot.get_position()
        return curr_slider_position

    def seek_to_position(self, slider_position):
        if self.vlc.is_playing:
            self.vlc.seek_to(slider_position)
        elif self.librespot.is_playing:
            self.librespot.seek_to(slider_position)

    def check_if_ended(self):
        return self.vlc.check_if_ended() or self.librespot.check_if_ended()

    def search_spotify(self, query, limit=7):
        return self.librespot.search(query, limit)

    def shutdown(self):
        self.librespot.shutdown()
