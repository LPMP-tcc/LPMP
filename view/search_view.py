import threading, rapidfuzz, requests

import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw

from model.track_type import TrackType
from view.widgets import ElidedLabel, ArtArea


class SearchViewWidget(Qtw.QFrame):
    def __init__(self, parent):
        super().__init__()
        v_layout = Qtw.QVBoxLayout()
        self.setStyleSheet("background-color:white")
        self.setLayout(v_layout)
        self.parent_widget = parent

        search_h_layout = Qtw.QHBoxLayout()
        back_button = Qtw.QPushButton("<")
        back_button.setMaximumWidth(20)
        back_button.clicked.connect(self.parent_widget.change_to_album_grid_view)
        search_h_layout.addWidget(back_button, alignment=Qtc.Qt.AlignmentFlag.AlignTop)

        self.search_bar = Qtw.QLineEdit()
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        search_h_layout.addWidget(self.search_bar)

        self.local_search_scroll_area = LocalSearchScrollWidget(self.parent_widget)
        self.cloud_search_scroll_area = StreamingSearchScrollWidget(self.parent_widget)

        v_layout.addLayout(search_h_layout)
        v_layout.addWidget(self.local_search_scroll_area, 1)
        v_layout.addWidget(self.cloud_search_scroll_area, 1)

    def _on_search_text_changed(self, text):
        self.local_search_scroll_area.search(text)
        self.cloud_search_scroll_area.schedule_search(text)


class LocalSearchScrollWidget(Qtw.QScrollArea):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_selection = None
        self.setMinimumHeight(324)
        self.setHorizontalScrollBarPolicy(Qtc.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qtc.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.inner_layout = Qtw.QHBoxLayout()
        self.inner_widget = Qtw.QWidget()
        self.inner_widget.setLayout(self.inner_layout)
        self.setWidget(self.inner_widget)
        self.setWidgetResizable(True)

    def search(self, query):
        while self.inner_layout.count():
            item = self.inner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not query.strip():
            return

        library = self.main_window.library.library
        if not library:
            return

        choices = [
            f"{track.get('title') or ''} {track.get('artist') or ''} {track.get('album') or ''}"
            for track in library
        ]
        results = rapidfuzz.process.extract(query, choices, scorer=rapidfuzz.fuzz.WRatio, limit=7, score_cutoff=60)

        def make_play_callback(t):
            def callback():
                self.main_window.music_player.play(t['track'], t['typed'])
                self.main_window.top_bar_widget.set_now_playing(
                    t.get('title', ''), t.get('artist', ''))
            return callback

        for _, score, idx in results:
            track = library[idx]
            art = self.main_window.library.get_art(track['track'], track['typed'])
            tile = LocalSearchTile(
                self,
                track.get('title') or '',
                track.get('album') or '',
                track.get('artist') or '',
                art,
                show_add=False,
                on_play=make_play_callback(track),
            )
            self.inner_layout.addWidget(tile)
        self.inner_layout.addStretch()

    def change_selection(self, new_selection):
        if self.current_selection:
            self.current_selection.deselect_tile()
        self.current_selection = new_selection
        if self.current_selection:
            self.current_selection.select_tile()

    def open_album_detail_view(self):
        pass


class LocalSearchTile(Qtw.QWidget):
    def __init__(self, parent, title, album, artist, art, show_add=True, on_add=None, on_play=None):
        super().__init__()
        v_layout = Qtw.QVBoxLayout()
        self.setLayout(v_layout)
        self.is_selected = False
        self.parent_widget = parent
        self.title = title
        self.album = album
        self.artist = artist

        self.art_area = ArtArea(show_add=show_add)
        if on_add:
            self.art_area.add_button.clicked.connect(on_add)
        if on_play:
            self.art_area.play_button.clicked.connect(on_play)
        pixmap = Qtg.QPixmap()
        pixmap.loadFromData(art)
        self.art_area.setPixmap(pixmap)

        title_text = ElidedLabel(title)
        title_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        artist_text = ElidedLabel(artist)
        artist_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        album_text = ElidedLabel(album)
        album_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)

        v_layout.addWidget(self.art_area)
        v_layout.addWidget(title_text)
        v_layout.addWidget(artist_text)
        v_layout.addWidget(album_text)

    def set_parent_widget(self, parent):
        self.parent_widget = parent

    def deselect_tile(self):
        self.is_selected = False
        self.art_area.setStyleSheet("border: 0px")

    def select_tile(self):
        self.is_selected = True
        self.art_area.setStyleSheet("border: 2px solid blue")

    def mousePressEvent(self, event):
        self.parent_widget.change_selection(self)

    def mouseDoubleClickEvent(self, event):
        self.parent_widget.open_album_detail_view()


class StreamingSearchScrollWidget(Qtw.QScrollArea):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.pending_query = ""
        self.art_cache = {}
        self.current_selection = None
        self.setMinimumHeight(300)
        self.setHorizontalScrollBarPolicy(Qtc.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qtc.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_layout = Qtw.QGridLayout()
        self.inner_widget = Qtw.QWidget()
        self.inner_widget.setLayout(self.grid_layout)
        self.setWidget(self.inner_widget)
        self.setWidgetResizable(True)

        self.debounce_timer = Qtc.QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(1000)
        self.debounce_timer.timeout.connect(self._trigger_search)

    def schedule_search(self, query):
        self.pending_query = query
        self.debounce_timer.start()

    def _trigger_search(self):
        query = self.pending_query
        if not query.strip():
            self._clear_grid()
            return
        thread = threading.Thread(target=self._fetch_and_display, args=(query,), daemon=True)
        thread.start()

    def _fetch_and_display(self, query):
        response = self.main_window.music_player.search_spotify(query)
        if response is None:
            return

        tracks = self._parse_tracks(response)

        tiles_data = []
        for item in tracks:
            art_url = item.get("art_url")
            art = None
            if art_url:
                if art_url not in self.art_cache:
                    try:
                        self.art_cache[art_url] = requests.get(art_url).content
                    except Exception as e:
                        print(f"art fetch failed: {e}")
                        self.art_cache[art_url] = None
                art = self.art_cache[art_url]
            if art is None:
                art = self.main_window.library.get_placeholder_art()
            tiles_data.append({**item, "art": art})

        Qtc.QTimer.singleShot(0, self, lambda: self._update_display(tiles_data))

    def _parse_tracks(self, response):
        # Spotify Web API /v1/search response:
        # { "tracks": { "items": [ { "uri", "name",
        #     "artists": [{"name"}], "album": {"name", "images": [{"url"}]} } ] } }
        tracks = []
        for item in response.get("tracks", {}).get("items", []):
            images = item.get("album", {}).get("images", [])
            artist_names = ", ".join(a["name"] for a in item.get("artists", []))
            tracks.append({
                "uri":          item.get("uri", ""),
                "title":        item.get("name", ""),
                "artist":       artist_names,
                "album":        item.get("album", {}).get("name", ""),
                "art_url":      images[0].get("url") if images else None,
                "duration_ms":  item.get("duration_ms", 0),
                "track_number": item.get("track_number", 0),
                "release_date": item.get("album", {}).get("release_date", ""),
            })
        return tracks

    def _update_display(self, tiles_data):
        self._clear_grid()

        def make_play_callback(track_data):
            track_id = track_data["uri"].split(":")[-1]
            def callback():
                self.main_window.music_player.play(track_id, TrackType.SPOTIFY)
                self.main_window.top_bar_widget.set_now_playing(
                    track_data.get("title", ""), track_data.get("artist", ""))
            return callback

        def make_add_callback(track_data, art_bytes):
            def callback():
                self.main_window.library.add_spotify_track(track_data, art_bytes)
                search_view = self.main_window.search_view_widget
                search_view.local_search_scroll_area.search(search_view.search_bar.text())
            return callback

        for col, data in enumerate(tiles_data):
            tile = LocalSearchTile(
                self, data["title"], data["album"], data["artist"], data["art"],
                on_add=make_add_callback(data, data["art"]),
                on_play=make_play_callback(data),
            )
            self.grid_layout.addWidget(tile, 0, col)

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def change_selection(self, new_selection):
        if self.current_selection:
            self.current_selection.deselect_tile()
        self.current_selection = new_selection
        if self.current_selection:
            self.current_selection.select_tile()

    def open_album_detail_view(self):
        pass
