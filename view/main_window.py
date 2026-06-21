import threading, vlc, math, rapidfuzz, requests

import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw

from view.top_bar import TopBar

class MainWindow(Qtw.QWidget):
    main_v_layout = Qtw.QVBoxLayout()
    main_h_layout = Qtw.QHBoxLayout()

    top_bar_widget = None
    main_display_widget = None
    album_grid_view_widget = None
    album_detail_view_widget = None

    music_player = None
    library = None

    def __init__(self, music_player, library):
        super().__init__()
        self.setWindowTitle("LPMP")
        self.resize(1200,800)
        self.setLayout(self.main_v_layout)

        self.music_player = music_player
        self.library = library
        self.library.pair_with_main_window(self)

        self.main_display_widget = Qtw.QStackedWidget()
        self.album_grid_view_widget = AlbumGridViewWidget(self)
        self.album_detail_view_widget = AlbumDetailViewWidget(self)
        self.search_view_widget = SearchViewWidget(self)

        self.main_display_widget.addWidget(self.album_grid_view_widget)
        self.main_display_widget.addWidget(self.album_detail_view_widget)
        self.main_display_widget.addWidget(self.search_view_widget)
        self.main_display_widget.setCurrentIndex(0)

        self.album_grid_view_widget.populate_grid()

        self.top_bar_widget = TopBar(music_player, library, self)

        self.main_v_layout.addWidget(self.top_bar_widget)
        self.main_v_layout.addWidget(self.main_display_widget)
        self.main_v_layout.addLayout(self.main_h_layout)

        ####

        self.spotifyTrackDuration = 0
        self.spotifyCurrentPosition = 0

        return

    def toggle_search_view(self):
        if self.main_display_widget.currentIndex() != 2:
            self.main_display_widget.setCurrentIndex(2)
        else:
            self.main_display_widget.setCurrentIndex(0)

    def change_to_album_detail_view(self, album_tile):
        album_info = self.library.get_album_info(album_tile.album_title, album_tile.artist)
        self.album_detail_view_widget.set_album_info(album_info)
        self.main_display_widget.setCurrentIndex(1)

    def change_to_album_grid_view(self):
        self.main_display_widget.setCurrentIndex(0)

    def notify_changes(self):
        self.album_grid_view_widget.update_view(None)

    def closeEvent(self, event):
        self.top_bar_widget.set_is_shutting_down(True)
        super().closeEvent(event)


class AlbumGridViewWidget(Qtw.QScrollArea):
    grid_layout = Qtw.QGridLayout()
    inner_widget = None
    current_selection = None
    current_view_query = {}
    widget_list = []

    def __init__(self, parent):
        super().__init__()
        self.parent_widget = parent
        self.setStyleSheet("background-color:white")
        self.update_view(None)

    def update_view(self, new_query):
        self.generate_widget_list(new_query)
        self.populate_grid()

    def generate_widget_list(self, new_query):
        if new_query is None:
            new_query = self.current_view_query

        # ignore the query for now, just generate all tiles
        self.set_widget_list(self.generate_album_tiles())

    def generate_album_tiles(self):
        album_set = set()
        for track_info in self.parent_widget.library.library:
            album_set.add((track_info["album"], track_info["artist"]))

        widget_list = []
        for item in album_set:
            (album, artist) = item
            album_info = self.parent_widget.library.get_album_info(album, artist)
            art = album_info["art"]
            widget_list.append(AlbumTile(self, album, artist, art))
        return widget_list

    def set_widget_list(self, new_widget_list):
        self.widget_list = new_widget_list

    def populate_grid(self):
        # clean it first
        for widget in self.widget_list:
            self.grid_layout.removeWidget(widget)

        # TODO: do away with this magic number/consider margins better
        if self.widget_list:
            columns = int(self.width()/218) + 1
            lines = int(len(self.widget_list) / columns) + 1
            count = 0
            for i in range(lines):
                for j in range(columns):
                    self.grid_layout.addWidget(self.widget_list[count],i+1,j+1)
                    if count == len(self.widget_list)-1:
                        break
                    else:
                        count += 1

        self.inner_widget = Qtw.QWidget()
        self.inner_widget.setLayout(self.grid_layout)
        self.setWidget(self.inner_widget)

    def change_selection(self, new_selection):
        if self.current_selection:
            self.current_selection.deselect_tile()

        self.current_selection = new_selection
        if self.current_selection:
            self.current_selection.select_tile()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.populate_grid()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.change_selection(None)

    # populate on show to consider correct dimensions
    def showEvent(self, event):
        super().showEvent(event)
        self.populate_grid()

    def open_album_detail_view(self):
        self.parent_widget.change_to_album_detail_view(self.current_selection)


class AlbumTile(Qtw.QWidget):
    def __init__(self, parent, name, artist, art):
        super().__init__()
        v_layout = Qtw.QVBoxLayout()
        self.setLayout(v_layout)
        self.is_selected = False
        self.parent_widget = parent
        self.album_title = name
        self.artist = artist

        self.art_area = Qtw.QLabel()
        self.art_area.setFixedWidth(200)
        self.art_area.setFixedHeight(200)
        self.art_area.setScaledContents(True)
        pixmap = Qtg.QPixmap()
        pixmap.loadFromData(art)
        self.art_area.setPixmap(pixmap)

        name_text = ElidedLabel(name)
        name_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        artist_text = ElidedLabel(artist)
        artist_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)

        v_layout.addWidget(self.art_area)
        v_layout.addWidget(name_text)
        v_layout.addWidget(artist_text)

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


class AlbumDetailViewWidget(Qtw.QScrollArea):
    def __init__(self, parent):
        super().__init__()
        self.parent_widget = parent
        self.setStyleSheet("background-color:white")

        self.inner_widget = None
        self.outer_h_layout = None
        self.v_layout = None
        self.album_list_v_layout = None

        self.album_info = None
        self.current_selection = None
        self.track_widget_list = []

    def set_album_info(self, album_info):
        self.album_info = album_info

    def populate(self):
        self.inner_widget = Qtw.QWidget()
        self.outer_h_layout = Qtw.QHBoxLayout()
        self.v_layout = Qtw.QVBoxLayout()
        self.album_list_v_layout = Qtw.QVBoxLayout()

        back_button = Qtw.QPushButton("<")
        back_button.setMaximumWidth(20)
        back_button.clicked.connect(self.parent_widget.change_to_album_grid_view)
        self.outer_h_layout.addWidget(back_button, alignment=Qtc.Qt.AlignmentFlag.AlignTop)

        album_detail_h_layout = Qtw.QHBoxLayout()

        art_area = Qtw.QLabel()
        art_area.setMaximumWidth(300)
        art_area.setMaximumHeight(300)
        art_area.setScaledContents(True)
        pixmap = Qtg.QPixmap()
        pixmap.loadFromData(self.album_info["art"])
        art_area.setPixmap(pixmap)
        album_detail_h_layout.addWidget(art_area)

        album_detail_v_layout = Qtw.QVBoxLayout()
        album_title = Qtw.QLabel(self.album_info["album_title"])
        album_title.setAlignment(Qtc.Qt.AlignmentFlag.AlignBottom)
        album_artist = Qtw.QLabel(self.album_info["artist"])
        album_artist.setAlignment(Qtc.Qt.AlignmentFlag.AlignTop)
        album_detail_v_layout.addWidget(album_title)
        album_detail_v_layout.addWidget(album_artist)
        album_detail_h_layout.addLayout(album_detail_v_layout)

        padding_widget = Qtw.QWidget()
        padding_widget.setMinimumHeight(50)

        # clean it first
        for old_track_widget in self.track_widget_list:
            self.album_list_v_layout.removeWidget(old_track_widget)

        self.create_track_widgets_from_list()

        for track_widget in self.track_widget_list:
            self.album_list_v_layout.addWidget(track_widget)

        self.v_layout.addLayout(album_detail_h_layout)
        self.v_layout.addWidget(padding_widget)
        self.v_layout.addLayout(self.album_list_v_layout)
        self.outer_h_layout.addLayout(self.v_layout)
        self.inner_widget.setLayout(self.outer_h_layout)
        self.setWidget(self.inner_widget)

    def create_track_widgets_from_list(self):
        track_widget_list = []
        for track in self.album_info["track_list"]:
            track_widget = AlbumDetailViewTrackItem(self, track)
            track_widget_list.append(track_widget)

        self.track_widget_list = track_widget_list

    def set_track_widget_list(self, new_track_widget_list):
        self.track_widget_list = new_track_widget_list

    def showEvent(self, event):
        super().showEvent(event)
        self.populate()

    def change_selection(self, new_selection):
        if self.current_selection:
            if self.current_selection in self.track_widget_list:
                self.current_selection.deselect_track_item()

        self.current_selection = new_selection
        if self.current_selection:
            self.current_selection.select_track_item()


class AlbumDetailViewTrackItem(Qtw.QWidget):
    def __init__(self, parent, track_info):
        super().__init__()
        h_layout = Qtw.QHBoxLayout()
        self.setLayout(h_layout)

        self.track = track_info["track"]
        self.track_typed = track_info.get("typed", "")
        self.track_artist = track_info.get("artist", "")
        self.track_number = Qtw.QLabel(str(track_info["number"]))
        self.track_number.setMaximumWidth(30)
        self.track_name = Qtw.QLabel(track_info["title"])
        self.track_name.setAlignment(Qtc.Qt.AlignmentFlag.AlignLeft)
        duration_hms = self.get_duration_in_hms(track_info["duration"])
        self.track_duration = Qtw.QLabel(duration_hms)
        self.track_duration.setAlignment(Qtc.Qt.AlignmentFlag.AlignRight)
        self.parent_widget = parent

        h_layout.addWidget(self.track_number)
        h_layout.addWidget(self.track_name)
        h_layout.addWidget(self.track_duration)

        return

    def get_duration_in_hms(self, duration):
        hours = int(duration / 3600)
        remainder_hours = (duration % 3600)
        minutes = int(remainder_hours / 60)
        seconds = int(remainder_hours % 60)

        if hours > 0:
            return str(hours) + ":" + str(minutes).zfill(2) + ":" + str(seconds).zfill(2)
        else:
            return str(minutes).zfill(2) + ":" + str(seconds).zfill(2)

    def select_track_item(self):
        self.setStyleSheet("background-color: rgb(200,200,200);")

    def deselect_track_item(self):
        self.setStyleSheet("background-color:white")

    def mousePressEvent(self, event):
        self.parent_widget.change_selection(self)

    def mouseDoubleClickEvent(self, event):
        main_window = self.parent_widget.parent_widget
        if self.track_typed == "SPOTIFY":
            main_window.music_player.play_spotify(self.track)
        else:
            main_window.music_player.play_vlc(self.track)
        main_window.top_bar_widget.set_now_playing(self.track_name.text(), self.track_artist)

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
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        search_h_layout.addWidget(self.search_bar)

        self.local_search_scroll_area = LocalSearchScrollWidget(self.parent_widget)
        self.cloud_search_scroll_area = StreamingSearchScrollWidget(self.parent_widget)

        v_layout.addLayout(search_h_layout)
        v_layout.addWidget(self.local_search_scroll_area, 1)
        v_layout.addWidget(self.cloud_search_scroll_area, 1)

    def on_search_text_changed(self, text):
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
                mp = self.main_window.music_player
                if t['typed'] == 'SPOTIFY':
                    mp.play_spotify(t['track'])
                else:
                    mp.play_vlc(t['track'])
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

class ArtArea(Qtw.QLabel):
    def __init__(self, show_add=True, parent=None):
        super().__init__(parent)
        self._show_add = show_add
        self.setFixedWidth(200)
        self.setFixedHeight(200)
        self.setScaledContents(True)

        self.add_button = Qtw.QPushButton("+", self)
        self.add_button.setFixedSize(28, 28)
        self.add_button.move(168, 4)
        self.add_button.hide()

        self.play_button = Qtw.QPushButton("▶", self)
        self.play_button.setFixedSize(28, 28)
        self.play_button.move(168, 168)
        self.play_button.hide()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._show_add:
            self.add_button.show()
        self.play_button.show()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.add_button.hide()
        self.play_button.hide()

class ElidedLabel(Qtw.QLabel):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setText(text)
        self.setSizePolicy(Qtw.QSizePolicy.Policy.Ignored, Qtw.QSizePolicy.Policy.Preferred)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        elided = self.fontMetrics().elidedText(self._full_text, Qtc.Qt.TextElideMode.ElideRight, self.width())
        super().setText(elided)

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
                self.main_window.music_player.play_spotify(track_id)
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
