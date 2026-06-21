import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw

from view.widgets import ElidedLabel


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
        self._generate_widget_list(new_query)
        self.populate_grid()

    def _generate_widget_list(self, new_query):
        if new_query is None:
            new_query = self.current_view_query

        # ignore the query for now, just generate all tiles
        self._set_widget_list(self._generate_album_tiles())

    def _generate_album_tiles(self):
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

    def _set_widget_list(self, new_widget_list):
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
