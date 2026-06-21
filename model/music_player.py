import vlc, threading, requests, time, base64, os

class MusicPlayer:
    vlc_instance = None
    vlc_player = None

    is_spotify_playing = False
    is_vlc_playing = False
    _volume = 100

    spotify_track_duration = 0
    spotify_current_position = 0

    _spotify_token = None
    _spotify_token_expiry = 0.0

    def __init__(self):
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()

    def play_vlc(self, local_track_path):
        self.pause_all()
        vlc_media = self.vlc_instance.media_new(local_track_path)
        self.vlc_player.set_media(vlc_media)
        self.vlc_player.play()
        self.is_vlc_playing = True
        threading.Thread(target=self._apply_vlc_volume_deferred, daemon=True).start()

    def _apply_vlc_volume_deferred(self):
        time.sleep(0.1)
        self.vlc_player.audio_set_volume(self._volume)

    def play_spotify(self, spotify_track_id):
        self.pause_all()
        threading.Thread(target=self._play_spotify_async, args=(spotify_track_id,), daemon=True).start()

    def _play_spotify_async(self, spotify_track_id):
        self.spotify_current_position = 0
        self._spotify_play_request(spotify_track_id)
        try:
            self.spotify_track_duration = self._spotify_status_request().json()["track"]["duration"]
        except Exception as e:
            print(f"[music_player] could not get spotify track duration: {e}")
            self.spotify_track_duration = 0
        self.is_spotify_playing = True

    def resume_all(self):
        if self.vlc_player.get_state() == vlc.State.Paused:
            self.vlc_player.play()
            self.is_vlc_playing = True
        elif not self.is_vlc_playing and not self.is_spotify_playing:
            self.is_spotify_playing = True
            threading.Thread(target=self._spotify_resume_request, daemon=True).start()

    def _spotify_resume_request(self):
        try:
            requests.post("http://127.0.0.1:24879/player/resume")
        except Exception as e:
            print(f"[music_player] resume request failed: {e}")

    def pause_all(self):
        if self.is_vlc_playing:
            self._pause_vlc()
        elif self.is_spotify_playing:
            self._pause_spotify()
        return

    def _pause_vlc(self):
        self.vlc_player.pause()
        self.is_vlc_playing = False
        return

    def _pause_spotify(self):
        thread = threading.Thread(target=self._spotify_pause_request)
        thread.start()
        self.is_spotify_playing = False # should this be part of the thread?

    def get_new_slider_position(self, curr_slider_position):
        if self.is_vlc_playing:
            new_slider_position = self.vlc_player.get_position()*1000
        elif self.is_spotify_playing:
            self.spotify_current_position += 100 # tick in approx. 100 millis
            new_slider_position = int((self.spotify_current_position / self.spotify_track_duration) * 1000)
        else:
            new_slider_position = curr_slider_position

        return new_slider_position

    def check_if_ended(self):
        if self.is_vlc_playing:
            if self.vlc_player.get_state() in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
                self.is_vlc_playing = False
                return True
        if self.is_spotify_playing and self.spotify_track_duration > 0:
            if self.spotify_current_position >= self.spotify_track_duration:
                self.is_spotify_playing = False
                return True
        return False

    def seek_to_position(self, curr_slider_position):
        per_thousands_position = curr_slider_position/1000

        if self.is_vlc_playing:
            self.vlc_player.set_position(per_thousands_position)
        elif self.is_spotify_playing:
            millis_to_seek = int(per_thousands_position * self.spotify_track_duration)
            thread = threading.Thread(target=self._spotify_seek_request, args=[millis_to_seek])
            thread.start()
            self.spotify_current_position = millis_to_seek # should this be part of the thread?

    def _spotify_status_request(self): # librespot doesn't talk to spotify for this, so it doesn't need to be async I guess
        r = requests.get("http://127.0.0.1:24879/status")
        return r

    def _spotify_play_request(self, spotify_track_id):
        r = requests.post("http://127.0.0.1:24879/player/play",
                          json={"uri": "spotify:track:" + spotify_track_id, "paused": False})

    def _spotify_pause_request(self):
        r = requests.post("http://127.0.0.1:24879/player/pause")

    def set_volume(self, value):
        self._volume = value
        if self.is_vlc_playing:
            threading.Thread(target=self.vlc_player.audio_set_volume, args=(value,), daemon=True).start()
        threading.Thread(target=self._spotify_set_volume_request, args=(value,), daemon=True).start()

    def _spotify_set_volume_request(self, value):
        try:
            requests.post(
                "http://127.0.0.1:24879/player/volume",
                json={"volume": value, "relative": False},
            )
        except Exception:
            pass

    def _spotify_seek_request(self, millis_to_seek):
        r = requests.post("http://127.0.0.1:24879/player/seek",
                          json={"position": millis_to_seek, "relative": False})

    def _get_spotify_token(self):
        if self._spotify_token and time.time() < self._spotify_token_expiry:
            return self._spotify_token
        client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {credentials}"},
            data={"grant_type": "client_credentials"},
        )
        r.raise_for_status()
        data = r.json()
        self._spotify_token = data["access_token"]
        self._spotify_token_expiry = time.time() + data["expires_in"] - 30
        print(f"[music_player] got new Spotify token (expires in {data['expires_in']}s)")
        return self._spotify_token

    def search_spotify(self, query, limit=7):
        print(f"[music_player] search_spotify: '{query}'")
        try:
            token = self._get_spotify_token()
            r = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": query, "type": "track", "limit": limit},
            )
            print(f"[music_player] response status: {r.status_code}")
            print(f"[music_player] response body: {r.text[:500]}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[music_player] search_spotify exception: {e}")
            return None