import threading, requests, time, base64, os

LIBRESPOT_URL = "http://127.0.0.1:24879"


class LibrespotPlayer:
    def __init__(self):
        self.is_playing = False
        self._track_duration = 0
        self._current_position = 0
        self._token = None
        self._token_expiry = 0.0
        self._maybe_ended_at = None

    def play(self, track_id):
        print(f"[librespot] play: track_id={track_id} (is_playing={self.is_playing})")
        threading.Thread(target=self._play_async, args=(track_id,), daemon=True).start()

    def _play_async(self, track_id):
        self._current_position = 0
        self._track_duration = 0  # keeps check_if_ended from firing before duration is known
        self._maybe_ended_at = None
        print(f"[librespot] _play_async: sending play for {track_id}")
        try:
            requests.post(f"{LIBRESPOT_URL}/player/play",
                          json={"uri": f"spotify:track:{track_id}", "paused": False})
        except Exception as e:
            print(f"[librespot] play request failed: {e}")
            return
        self.is_playing = True
        print(f"[librespot] is_playing set to True for {track_id}")
        try:
            status = requests.get(f"{LIBRESPOT_URL}/status").json()
            self._track_duration = status["track"]["duration"]
            print(f"[librespot] track duration: {self._track_duration}ms")
            if status.get("paused") and not status.get("stopped"):
                print(f"[librespot] track loaded paused (race with auto-advance?), sending resume")
                requests.post(f"{LIBRESPOT_URL}/player/resume")
        except Exception as e:
            print(f"[librespot] could not get track status: {e}")

    def pause(self):
        print(f"[librespot] pause (was is_playing={self.is_playing})")
        threading.Thread(target=self._pause_request, daemon=True).start()
        self.is_playing = False

    def _pause_request(self):
        try:
            requests.post(f"{LIBRESPOT_URL}/player/pause")
        except Exception as e:
            print(f"[librespot] pause request failed: {e}")

    def resume(self):
        print(f"[librespot] resume (was is_playing={self.is_playing})")
        self.is_playing = True
        threading.Thread(target=self._resume_request, daemon=True).start()

    def _resume_request(self):
        try:
            requests.post(f"{LIBRESPOT_URL}/player/resume")
        except Exception as e:
            print(f"[librespot] resume request failed: {e}")

    def set_volume(self, value):
        threading.Thread(target=self._set_volume_request, args=(value,), daemon=True).start()

    def _set_volume_request(self, value):
        try:
            requests.post(f"{LIBRESPOT_URL}/player/volume",
                          json={"volume": value, "relative": False})
        except Exception:
            pass

    def get_current_position_ms(self):
        return self._current_position

    def get_position(self):
        self._current_position += 100  # tick in approx. 100 millis
        return int((self._current_position / self._track_duration) * 1000) if self._track_duration else 0

    def seek_to(self, slider_position):
        millis = int((slider_position / 1000) * self._track_duration)
        self._current_position = millis
        threading.Thread(target=self._seek_request, args=(millis,), daemon=True).start()

    def _seek_request(self, millis):
        try:
            requests.post(f"{LIBRESPOT_URL}/player/seek",
                          json={"position": millis, "relative": False})
        except Exception as e:
            print(f"[librespot] seek request failed: {e}")

    def shutdown(self):
        if self.is_playing:
            try:
                requests.post(f"{LIBRESPOT_URL}/player/pause")
            except Exception:
                pass

    def check_if_ended(self):
        if not self.is_playing or self._track_duration <= 0:
            return False
        if self._current_position < self._track_duration:
            return False

        now = time.time()
        if self._maybe_ended_at is None:
            self._maybe_ended_at = now

        try:
            status  = requests.get(f"{LIBRESPOT_URL}/status").json()
            stopped = status.get("stopped", False)
            track   = status.get("track")
            if track:
                actual_pos    = track.get("position", 0)
                actual_dur    = track.get("duration", self._track_duration)
                paused        = status.get("paused", False)
                reset_to_zero = paused and actual_pos < 2000
                print(f"[librespot] check_if_ended: librespot pos={actual_pos}ms dur={actual_dur}ms "
                      f"stopped={stopped} paused={paused} reset_to_zero={reset_to_zero}")
                if stopped or reset_to_zero:
                    print(f"[librespot] check_if_ended: confirmed ended")
                    self._maybe_ended_at = None
                    self.is_playing = False
                    return True
            elif stopped:
                print(f"[librespot] check_if_ended: stopped (no track in status)")
                self._maybe_ended_at = None
                self.is_playing = False
                return True
            else:
                print(f"[librespot] check_if_ended: status check failed: no track and not stopped")
        except Exception as e:
            print(f"[librespot] check_if_ended: status request failed: {e}")

        return False

    def search(self, query, limit=7):
        print(f"[librespot] search: '{query}'")
        try:
            token = self._get_token()
            r = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": query, "type": "track", "limit": limit},
            )
            print(f"[librespot] search response: {r.status_code}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[librespot] search exception: {e}")
            return None

    def search_albums(self, query, limit=5):
        try:
            token = self._get_token()
            r = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": query, "type": "album", "limit": limit},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[librespot] search_albums exception: {e}")
            return None

    def get_album_tracks(self, album_id):
        try:
            token = self._get_token()
            all_items = []
            url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"
            params = {"limit": 50, "offset": 0}
            while url:
                r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
                r.raise_for_status()
                page = r.json()
                all_items.extend(page.get("items", []))
                url = page.get("next")
                params = {}
            return {"items": all_items}
        except Exception as e:
            print(f"[librespot] get_album_tracks exception: {e}")
            return None

    def _get_token(self):
        if self._token and time.time() < self._token_expiry:
            return self._token
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
        self._token = data["access_token"]
        self._token_expiry = time.time() + data["expires_in"] - 30
        print(f"[librespot] got new Spotify token (expires in {data['expires_in']}s)")
        return self._token
