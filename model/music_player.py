import vlc, threading, json, requests

class MusicPlayer:
    vlc_instance = None
    vlc_player = None

    is_spotify_playing = False
    is_vlc_playing = False

    spotify_track_duration = 0
    spotify_current_position = 0

    def __init__(self):
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()

    def play_vlc(self, local_track_path):
        self.pause_all()
        vlc_media = self.vlc_instance.media_new(local_track_path)
        self.vlc_player.set_media(vlc_media)
        self.vlc_player.play()
        self.is_vlc_playing = True

    def play_spotify(self, spotify_track_id):
        self.pause_all()
        thread = threading.Thread(target=self.spotify_play_request, args=(spotify_track_id,))
        thread.start()
        # if track is in library, get duration from its entry
        self.spotify_track_duration = self.spotify_status_request().json()["track"]["duration"]
        self.is_spotify_playing = True

    def pause_all(self):
        if self.is_vlc_playing:
            self.pause_vlc()
        elif self.is_spotify_playing:
            self.pause_spotify()
        return

    def pause_vlc(self):
        self.vlc_player.pause()
        self.is_vlc_playing = False
        return

    def pause_spotify(self):
        thread = threading.Thread(target=self.spotify_pause_request)
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

    def seek_to_position(self, curr_slider_position):
        per_thousands_position = curr_slider_position/1000

        if self.is_vlc_playing:
            self.vlc_player.set_position(per_thousands_position)
        elif self.is_spotify_playing:
            millis_to_seek = int(per_thousands_position * self.spotify_track_duration)
            thread = threading.Thread(target=self.spotify_seek_request, args=[millis_to_seek])
            thread.start()
            self.spotify_current_position = millis_to_seek # should this be part of the thread?

    def spotify_status_request(self): # librespot doesn't talk to spotify for this, so it doesn't need to be async I guess
        r = requests.get("http://127.0.0.1:24879/status")
        return r

    def spotify_play_request(self, spotify_track_id):
        bodyJson = {"uri": "spotify:track:" + spotify_track_id, "paused": False}
        bodyJsonString = json.dumps(bodyJson)
        r = requests.post("http://127.0.0.1:24879/player/play", bodyJsonString)

    def spotify_pause_request(self):
        r = requests.post("http://127.0.0.1:24879/player/pause")

    def spotify_seek_request(self, millis_to_seek):
        body_json = {"position": millis_to_seek, "relative": False}
        body_json_string = json.dumps(body_json)
        r = requests.post("http://127.0.0.1:24879/player/seek", body_json_string)