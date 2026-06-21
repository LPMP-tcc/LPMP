import threading, requests, time, base64, os

LIBRESPOT_URL = "http://127.0.0.1:24879"


class LibrespotPlayer:
    def __init__(self):
        self.is_playing = False
        self._track_duration = 0
        self._current_position = 0
        self._token = None
        self._token_expiry = 0.0

    def play(self, track_id):
        threading.Thread(target=self._play_async, args=(track_id,), daemon=True).start()

    def _play_async(self, track_id):
        self._current_position = 0
        try:
            requests.post(f"{LIBRESPOT_URL}/player/play",
                          json={"uri": f"spotify:track:{track_id}", "paused": False})
        except Exception as e:
            print(f"[librespot] play request failed: {e}")
            return
        try:
            self._track_duration = requests.get(f"{LIBRESPOT_URL}/status").json()["track"]["duration"]
        except Exception as e:
            print(f"[librespot] could not get track duration: {e}")
            self._track_duration = 0
        self.is_playing = True

    def pause(self):
        threading.Thread(target=self._pause_request, daemon=True).start()
        self.is_playing = False

    def _pause_request(self):
        try:
            requests.post(f"{LIBRESPOT_URL}/player/pause")
        except Exception as e:
            print(f"[librespot] pause request failed: {e}")

    def resume(self):
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
        if self.is_playing and self._track_duration > 0:
            if self._current_position >= self._track_duration:
                self.is_playing = False
                return True
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
