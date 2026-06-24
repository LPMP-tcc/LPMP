from model.vlc_player import VlcPlayer
from model.librespot_player import LibrespotPlayer
from model.track_type import TrackType


def _log_queue(queue, queue_index):
    if not queue:
        print("[player] queue: (empty)")
        return
    def _fmt(i):
        t = queue[i]
        marker = ">>>" if i == queue_index else "   "
        return f"  {marker} [{i}] {t.get('title', '?')} — {t.get('artist', '?')}"
    lines = [f"[player] queue: {len(queue)} tracks, index={queue_index}"]
    if queue_index > 0:
        lines.append(_fmt(queue_index - 1))
    lines.append(_fmt(queue_index))
    if queue_index < len(queue) - 1:
        lines.append(_fmt(queue_index + 1))
    print("\n".join(lines))


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
        title = track_dict.get('title', '?')
        print(f"[player] play: '{title}' (queue_index={self.queue_index})")
        _log_queue(self.queue, self.queue_index)
        self._start_playback(track_dict)

    def _start_playback(self, track_dict):
        title  = track_dict.get('title', '?')
        typed  = track_dict.get('typed', '?')
        print(f"[player] _start_playback: '{title}' typed={typed}")
        self.pause_all()
        self.now_playing = track_dict
        if track_dict["typed"] == TrackType.SPOTIFY:
            self.librespot.play(track_dict["track"])
        else:
            self.vlc.play(track_dict["track"])

    def skip_forward(self):
        print(f"[player] skip_forward: index {self.queue_index} → ", end="")
        if not self.queue or self.queue_index >= len(self.queue) - 1:
            print("end of queue")
            self.pause_all()
            self.now_playing = None
            self.queue_index = -1
            return
        self.queue_index += 1
        print(self.queue_index)
        _log_queue(self.queue, self.queue_index)
        self._start_playback(self.queue[self.queue_index])

    def skip_backward(self):
        pos = self.get_current_position_ms()
        print(f"[player] skip_backward: pos={pos}ms index={self.queue_index}")
        if pos > 3000:
            self.seek_to_position(0)
            return
        if self.queue and self.queue_index > 0:
            self.queue_index -= 1
            _log_queue(self.queue, self.queue_index)
            self._start_playback(self.queue[self.queue_index])
        else:
            self.seek_to_position(0)

    def pause_all(self):
        print(f"[player] pause_all: vlc.is_playing={self.vlc.is_playing} librespot.is_playing={self.librespot.is_playing}")
        if self.vlc.is_playing:
            self.vlc.pause()
        elif self.librespot.is_playing:
            self.librespot.pause()

    def resume_all(self):
        print(f"[player] resume_all: vlc.is_paused={self.vlc.is_paused} librespot.is_playing={self.librespot.is_playing}")
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
        print(f"[player] track ended — queue_index={self.queue_index}, queue length={len(self.queue)}")
        if self.queue and self.queue_index < len(self.queue) - 1:
            self.queue_index += 1
            print(f"[player] advancing queue to index {self.queue_index}: '{self.queue[self.queue_index].get('title', '?')}'")
            _log_queue(self.queue, self.queue_index)
            self._start_playback(self.queue[self.queue_index])
            return False
        print("[player] queue exhausted, stopping")
        self.now_playing = None
        return True

    def search_spotify(self, query, limit=7):
        return self.librespot.search(query, limit)

    def search_spotify_albums(self, query, limit=5):
        return self.librespot.search_albums(query, limit)

    def get_spotify_album_tracks(self, album_id):
        return self.librespot.get_album_tracks(album_id)

    def shutdown(self):
        self.librespot.shutdown()
