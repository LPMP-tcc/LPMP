from model.vlc_player import VlcPlayer
from model.librespot_player import LibrespotPlayer
from model.track_type import TrackType


class MusicPlayer:
    def __init__(self):
        self.vlc = VlcPlayer()
        self.librespot = LibrespotPlayer()
        self.now_playing = None
        self.queue = []
        self.queue_index = -1

    @property
    def is_playing(self):
        return self.vlc.is_playing or self.librespot.is_playing

    def play(self, track_dict, queue=None, queue_index=0):
        self.queue = list(queue) if queue else []
        self.queue_index = queue_index if queue else -1
        self._start_playback(track_dict)

    def _start_playback(self, track_dict):
        self.pause_all()
        self.now_playing = track_dict
        if track_dict["typed"] == TrackType.SPOTIFY:
            self.librespot.play(track_dict["track"])
        else:
            self.vlc.play(track_dict["track"])

    def skip_forward(self):
        if not self.queue or self.queue_index >= len(self.queue) - 1:
            self.pause_all()
            self.now_playing = None
            self.queue_index = -1
            return
        self.queue_index += 1
        self._start_playback(self.queue[self.queue_index])

    def skip_backward(self):
        if self.get_current_position_ms() > 3000:
            self.seek_to_position(0)
            return
        if self.queue and self.queue_index > 0:
            self.queue_index -= 1
            self._start_playback(self.queue[self.queue_index])
        else:
            self.seek_to_position(0)

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

    def get_current_position_ms(self):
        if self.vlc.is_playing:
            return self.vlc.get_current_position_ms()
        elif self.librespot.is_playing:
            return self.librespot.get_current_position_ms()
        return 0

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
        if not (self.vlc.check_if_ended() or self.librespot.check_if_ended()):
            return False
        if self.queue and self.queue_index < len(self.queue) - 1:
            self.queue_index += 1
            self._start_playback(self.queue[self.queue_index])
            return False
        self.now_playing = None
        return True

    def search_spotify(self, query, limit=7):
        return self.librespot.search(query, limit)

    def shutdown(self):
        self.librespot.shutdown()
