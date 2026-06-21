import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw


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

        self._create_track_widgets_from_list()

        for track_widget in self.track_widget_list:
            self.album_list_v_layout.addWidget(track_widget)

        self.v_layout.addLayout(album_detail_h_layout)
        self.v_layout.addWidget(padding_widget)
        self.v_layout.addLayout(self.album_list_v_layout)
        self.outer_h_layout.addLayout(self.v_layout)
        self.inner_widget.setLayout(self.outer_h_layout)
        self.setWidget(self.inner_widget)

    def _create_track_widgets_from_list(self):
        track_widget_list = []
        for track in self.album_info["track_list"]:
            track_widget = AlbumDetailViewTrackItem(self, track)
            track_widget_list.append(track_widget)

        self.track_widget_list = track_widget_list

    def _set_track_widget_list(self, new_track_widget_list):
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
        duration_hms = self._get_duration_in_hms(track_info["duration"])
        self.track_duration = Qtw.QLabel(duration_hms)
        self.track_duration.setAlignment(Qtc.Qt.AlignmentFlag.AlignRight)
        self.parent_widget = parent

        h_layout.addWidget(self.track_number)
        h_layout.addWidget(self.track_name)
        h_layout.addWidget(self.track_duration)

        return

    def _get_duration_in_hms(self, duration):
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
        main_window.music_player.play(self.track, self.track_typed)
        main_window.top_bar_widget.set_now_playing(self.track_name.text(), self.track_artist)
