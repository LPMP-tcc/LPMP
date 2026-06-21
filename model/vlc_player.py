import threading, time
import vlc


class VlcPlayer:
    def __init__(self):
        self._instance = vlc.Instance()
        self._player = self._instance.media_player_new()
        self._volume = 100
        self.is_playing = False

    def play(self, path):
        media = self._instance.media_new(path)
        self._player.set_media(media)
        self._player.play()
        self.is_playing = True
        threading.Thread(target=self._apply_volume_deferred, daemon=True).start()

    def _apply_volume_deferred(self):
        time.sleep(0.1)
        self._player.audio_set_volume(self._volume)

    def pause(self):
        self._player.pause()
        self.is_playing = False

    def resume(self):
        self._player.play()
        self.is_playing = True

    @property
    def is_paused(self):
        return self._player.get_state() == vlc.State.Paused

    def set_volume(self, value):
        self._volume = value
        if self.is_playing:
            threading.Thread(target=self._player.audio_set_volume, args=(value,), daemon=True).start()

    def get_position(self):
        return int(self._player.get_position() * 1000)

    def seek_to(self, slider_position):
        self._player.set_position(slider_position / 1000)

    def check_if_ended(self):
        if self.is_playing:
            if self._player.get_state() in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
                self.is_playing = False
                return True
        return False
