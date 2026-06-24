import threading, rapidfuzz, requests, types

import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw

from model.track_type import TrackType
from view.custom_widgets import ElidedLabel, ArtArea


def _disc_icon_pixmap():
    style = Qtw.QApplication.style()
    icon = Qtg.QIcon.fromTheme(
        "media-optical",
        style.standardIcon(Qtw.QStyle.StandardPixmap.SP_DriveCDIcon),
    )
    return icon.pixmap(16, 16)


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

        scorer = rapidfuzz.fuzz.WRatio

        # Score individual tracks
        track_results = []
        for track in library:
            score = max(
                scorer(query, track.get('title')  or ''),
                scorer(query, track.get('artist') or ''),
                scorer(query, track.get('album')  or ''),
            )
            if score >= 60:
                track_results.append({'score': score, 'kind': 'track', 'track': track})

        # Score unique (album, album_artist) pairs by album name
        seen_albums = {}
        for track in library:
            album_name   = track.get('album')  or ''
            artist_name  = track.get('album_artist') or track.get('artist') or ''
            key = (album_name, artist_name)
            album_score = scorer(query, album_name)
            if album_score >= 60:
                if key not in seen_albums or album_score > seen_albums[key]['score']:
                    seen_albums[key] = {
                        'score': album_score, 'kind': 'album',
                        'album': album_name, 'artist': artist_name, 'track': track,
                    }
        album_results = list(seen_albums.values())

        # Exact-name album matches are pinned first
        query_lower = query.strip().lower()
        exact_albums = [r for r in album_results if r['album'].lower() == query_lower]
        other         = sorted(
            [r for r in album_results if r['album'].lower() != query_lower] + track_results,
            key=lambda x: x['score'], reverse=True,
        )
        combined = (sorted(exact_albums, key=lambda x: x['score'], reverse=True) + other)[:7]

        for item in combined:
            if item['kind'] == 'album':
                track = item['track']
                art = self.main_window.library.get_art(track['track'], track['typed'])
                tile = LocalSearchTile(
                    self, item['album'], '', item['artist'], art,
                    show_add=False,
                    on_play=self._make_album_open(item['album'], item['artist']),
                    is_album=True,
                    on_double_click=self._make_album_open(item['album'], item['artist']),
                )
            else:
                track = item['track']
                art = self.main_window.library.get_art(track['track'], track['typed'])
                album_artist = track.get('album_artist') or track.get('artist') or ''
                tile = LocalSearchTile(
                    self,
                    track.get('title')  or '',
                    track.get('album')  or '',
                    track.get('artist') or '',
                    art,
                    show_add=False,
                    on_play=self._make_play(track),
                    on_double_click=self._make_album_open(track.get('album') or '', album_artist),
                )
            self.inner_layout.addWidget(tile)
        self.inner_layout.addStretch()

    def _make_play(self, track):
        return lambda: self.main_window.music_player.play(track)

    def _make_album_open(self, album_title, artist):
        return lambda: self.main_window.change_to_album_detail_view(
            types.SimpleNamespace(album_title=album_title, artist=artist)
        )

    def change_selection(self, new_selection):
        if self.current_selection:
            self.current_selection.deselect_tile()
        self.current_selection = new_selection
        if self.current_selection:
            self.current_selection.select_tile()


class LocalSearchTile(Qtw.QWidget):
    def __init__(self, parent, title, album, artist, art,
                 show_add=True, on_add=None, on_play=None, is_album=False, on_double_click=None,
                 show_play=True):
        super().__init__()
        v_layout = Qtw.QVBoxLayout()
        self.setLayout(v_layout)
        self.is_selected = False
        self.parent_widget = parent
        self.title = title
        self.album = album
        self.artist = artist
        self._on_double_click = on_double_click

        self.art_area = ArtArea(show_add=show_add, show_play=show_play)
        if on_add:
            self.art_area.add_button.clicked.connect(on_add)
        if on_play:
            self.art_area.play_button.clicked.connect(on_play)
        pixmap = Qtg.QPixmap()
        pixmap.loadFromData(art)
        self.art_area.setPixmap(pixmap)
        v_layout.addWidget(self.art_area)

        if is_album:
            title_row = Qtw.QHBoxLayout()
            title_row.setSpacing(4)
            title_row.setContentsMargins(0, 0, 0, 0)
            disc_label = Qtw.QLabel()
            disc_label.setPixmap(_disc_icon_pixmap())
            disc_label.setFixedSize(16, 16)
            disc_label.setScaledContents(True)
            title_label = ElidedLabel(title)
            title_label.setAlignment(
                Qtc.Qt.AlignmentFlag.AlignVCenter | Qtc.Qt.AlignmentFlag.AlignHCenter
            )
            right_spacer = Qtw.QLabel()
            right_spacer.setFixedWidth(16)   # mirrors disc width so title stays centered
            title_row.addWidget(disc_label, 0, Qtc.Qt.AlignmentFlag.AlignVCenter)
            title_row.addWidget(title_label, 1)
            title_row.addWidget(right_spacer)
            v_layout.addLayout(title_row)
        else:
            title_text = ElidedLabel(title)
            title_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
            v_layout.addWidget(title_text)

        artist_text = ElidedLabel(artist)
        artist_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(artist_text)

        if not is_album:
            album_text = ElidedLabel(album)
            album_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
            v_layout.addWidget(album_text)

    def deselect_tile(self):
        self.is_selected = False
        self.art_area.setStyleSheet("border: 0px")

    def select_tile(self):
        self.is_selected = True
        self.art_area.setStyleSheet("border: 2px solid blue")

    def mousePressEvent(self, event):
        self.parent_widget.change_selection(self)

    def mouseDoubleClickEvent(self, event):
        if self._on_double_click:
            self._on_double_click()


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
        track_response = self.main_window.music_player.search_spotify(query)
        album_response = self.main_window.music_player.search_spotify_albums(query)

        tracks = [{'kind': 'track', **t} for t in self._parse_tracks(track_response or {})]
        albums = [{'kind': 'album', **a} for a in self._parse_albums(album_response or {})]

        tiles_data = []
        for item in tracks + albums:
            art_url = item.get("art_url")
            art = None
            if art_url:
                if art_url not in self.art_cache:
                    try:
                        self.art_cache[art_url] = requests.get(art_url).content
                    except Exception:
                        self.art_cache[art_url] = None
                art = self.art_cache[art_url]
            if art is None:
                art = self.main_window.library.get_placeholder_art()
            tiles_data.append({**item, "art": art})

        Qtc.QTimer.singleShot(0, self, lambda: self._update_display(tiles_data))

    def _parse_tracks(self, response):
        tracks = []
        for item in response.get("tracks", {}).get("items", []):
            album_obj    = item.get("album", {})
            images       = album_obj.get("images", [])
            artist_names = ", ".join(a["name"] for a in item.get("artists", []))
            album_artist = ", ".join(a["name"] for a in album_obj.get("artists", []))
            tracks.append({
                "uri":          item.get("uri", ""),
                "title":        item.get("name", ""),
                "artist":       artist_names,
                "album_artist": album_artist,
                "album":        album_obj.get("name", ""),
                "art_url":      images[0].get("url") if images else None,
                "duration_ms":  item.get("duration_ms", 0),
                "track_number": item.get("track_number", 0),
                "disc_number":  item.get("disc_number"),
                "release_date": album_obj.get("release_date", ""),
            })
        return tracks

    def _parse_albums(self, response):
        albums = []
        for item in response.get("albums", {}).get("items", []):
            images = item.get("images", [])
            artist_names = ", ".join(a["name"] for a in item.get("artists", []))
            albums.append({
                "album_id":     item.get("id", ""),
                "title":        item.get("name", ""),
                "artist":       artist_names,
                "art_url":      images[0].get("url") if images else None,
                "release_date": item.get("release_date", ""),
            })
        return albums

    def _update_display(self, tiles_data):
        self._clear_grid()

        def make_add_track_callback(track_data, art_bytes):
            def add():
                self.main_window.library.add_spotify_track(track_data, art_bytes)
                search_view = self.main_window.search_view_widget
                search_view.local_search_scroll_area.search(search_view.search_bar.text())
            return add

        def make_play_callback(track_data):
            return lambda: self.main_window.music_player.play({
                "track":  track_data["uri"].split(":")[-1],
                "typed":  TrackType.SPOTIFY,
                "title":  track_data.get("title", ""),
                "artist": track_data.get("artist", ""),
            })

        def make_add_album_callback(album_data, art_bytes):
            def add():
                album_id     = album_data["album_id"]
                album_name   = album_data["title"]
                album_artist = album_data["artist"]
                release_date = album_data.get("release_date", "")
                response = self.main_window.music_player.get_spotify_album_tracks(album_id)
                if not response:
                    return
                for item in response.get("items", []):
                    track_data = {
                        "uri":          item.get("uri", ""),
                        "title":        item.get("name", ""),
                        "artist":       ", ".join(a["name"] for a in item.get("artists", [])),
                        "album_artist": album_artist,
                        "album":        album_name,
                        "track_number": item.get("track_number", 0),
                        "disc_number":  item.get("disc_number"),
                        "duration_ms":  item.get("duration_ms", 0),
                        "release_date": release_date,
                    }
                    self.main_window.library.add_spotify_track(track_data, art_bytes)
                search_view = self.main_window.search_view_widget
                search_view.local_search_scroll_area.search(search_view.search_bar.text())
            return add

        for col, data in enumerate(tiles_data):
            if data.get('kind') == 'album':
                tile = LocalSearchTile(
                    self, data["title"], '', data["artist"], data["art"],
                    show_add=True,
                    on_add=make_add_album_callback(data, data["art"]),
                    on_play=None,
                    is_album=True,
                    on_double_click=self._make_album_navigate(data["title"], data["artist"]),
                    show_play=False,
                )
            else:
                album_artist = data.get("album_artist") or data.get("artist", "")
                tile = LocalSearchTile(
                    self, data["title"], data.get("album", ""), data["artist"], data["art"],
                    on_add=make_add_track_callback(data, data["art"]),
                    on_play=make_play_callback(data),
                    on_double_click=self._make_album_navigate(data.get("album", ""), album_artist),
                )
            self.grid_layout.addWidget(tile, 0, col)

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _make_album_navigate(self, album_title, album_artist):
        def navigate():
            found = any(
                t.get('album') == album_title and
                (t.get('album_artist') or t.get('artist')) == album_artist
                for t in self.main_window.library.library
            )
            if not found:
                return
            self.main_window.change_to_album_detail_view(
                types.SimpleNamespace(album_title=album_title, artist=album_artist)
            )
        return navigate

    def change_selection(self, new_selection):
        if self.current_selection:
            self.current_selection.deselect_tile()
        self.current_selection = new_selection
        if self.current_selection:
            self.current_selection.select_tile()
