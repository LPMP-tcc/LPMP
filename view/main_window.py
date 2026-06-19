import threading, vlc, math, rapidfuzz

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

        name_text = Qtw.QLabel(name)
        name_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        artist_text = Qtw.QLabel(artist)
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
        self.parent_widget.parent_widget.music_player.play_vlc(self.track)
        print("hello " + self.track_name.text())

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
        search_h_layout.addWidget(self.search_bar)

        self.local_search_scroll_area = LocalSearchScrollWidget(self.parent_widget)
        self.cloud_search_scroll_area = StreamingSearchScrollWidget()

        v_layout.addLayout(search_h_layout)
        v_layout.addWidget(self.local_search_scroll_area)
        v_layout.addWidget(self.cloud_search_scroll_area)
        v_layout.addStretch()

class LocalSearchScrollWidget(Qtw.QScrollArea):
    def __init__(self, main_window):
        super().__init__()
        self.setFixedHeight(324)

        query = "rdiohd"
        choices = [f"{item['title']} {item['album_artist']} {item['album']}" for item in main_window.library.library]
        results = rapidfuzz.process.extract(query, choices, scorer=rapidfuzz.fuzz.WRatio, limit=5)
        print(results)

        grid_layout = Qtw.QGridLayout()

        grid_layout.addWidget(LocalSearchTile(self, "dummy", "dummy", "dummy", main_window.library.get_placeholder_art()), 1, 1)
        grid_layout.addWidget(AlbumTile(self, "dummy2", "dummy2", main_window.library.get_placeholder_art()), 1, 2)
        grid_layout.addWidget(AlbumTile(self, "dummy3", "dummy3", main_window.library.get_placeholder_art()), 1, 3)
        grid_layout.addWidget(AlbumTile(self, "dummy4", "dummy4", main_window.library.get_placeholder_art()), 1, 4)
        grid_layout.addWidget(AlbumTile(self, "dummy5", "dummy5", main_window.library.get_placeholder_art()), 1, 5)
        grid_layout.addWidget(AlbumTile(self, "dummy6", "dummy6", main_window.library.get_placeholder_art()), 1, 6)
        grid_layout.addWidget(AlbumTile(self, "dummy7", "dummy7", main_window.library.get_placeholder_art()), 1, 7)

        self.inner_widget = Qtw.QWidget()
        self.inner_widget.setLayout(grid_layout)
        self.setWidget(self.inner_widget)

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
            columns = int(self.width() / 218) + 1
            lines = int(len(self.widget_list) / columns) + 1
            count = 0
            for i in range(lines):
                for j in range(columns):
                    self.grid_layout.addWidget(self.widget_list[count], i + 1, j + 1)
                    if count == len(self.widget_list) - 1:
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

class LocalSearchTile(Qtw.QWidget):
    def __init__(self, parent, title, album, artist, art):
        super().__init__()
        v_layout = Qtw.QVBoxLayout()
        self.setLayout(v_layout)
        self.is_selected = False
        self.parent_widget = parent
        self.title = title
        self.album = album
        self.artist = artist

        self.art_area = Qtw.QLabel()
        self.art_area.setFixedWidth(200)
        self.art_area.setFixedHeight(200)
        self.art_area.setScaledContents(True)
        pixmap = Qtg.QPixmap()
        pixmap.loadFromData(art)
        self.art_area.setPixmap(pixmap)

        title_text = Qtw.QLabel(title)
        title_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        artist_text = Qtw.QLabel(artist)
        artist_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        album_text = Qtw.QLabel(album)
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
    def __init__(self):
        super().__init__()
        self.setFixedHeight(300)
        h_layout = Qtw.QHBoxLayout()
        self.setLayout(h_layout)
