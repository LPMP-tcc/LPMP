import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw

from model.filters import SortFilter
from view.metadata_edit_dialog import AlbumMetadataEditDialog
from view.custom_widgets import ArtArea, ElidedLabel


class AlbumGridViewWidget(Qtw.QScrollArea):
    def __init__(self, parent):
        super().__init__()
        self.parent_widget      = parent
        self.inner_widget       = None
        self.current_selection  = None
        self.current_view_query = {}
        self.widget_list        = []
        self._dirty             = False
        self.setStyleSheet("background-color:white")
        self.update_view(None)

    def update_view(self, new_query):
        self.current_selection = None   # old tile objects are about to be replaced
        self._generate_widget_list(new_query)
        self.populate_grid()

    def _generate_widget_list(self, new_query):
        self._set_widget_list(self._generate_album_tiles())

    def _generate_album_tiles(self):
        summaries = self.parent_widget.library.get_all_album_summaries()
        sorted_summaries = SortFilter('artist', 'date').apply(summaries)
        return [AlbumTile(self, s["album_title"], s["artist"], s["art"])
                for s in sorted_summaries]

    def _set_widget_list(self, new_widget_list):
        self.widget_list = new_widget_list

    def populate_grid(self):
        grid = Qtw.QGridLayout()

        if self.widget_list:
            columns = max(1, self.viewport().width() // 218)
            for col in range(columns):
                grid.setColumnStretch(col, 1)
            for idx, tile in enumerate(self.widget_list):
                grid.addWidget(
                    tile,
                    idx // columns,
                    idx % columns,
                    Qtc.Qt.AlignmentFlag.AlignHCenter | Qtc.Qt.AlignmentFlag.AlignTop,
                )

        self.inner_widget = Qtw.QWidget()
        self.inner_widget.setLayout(grid)
        self.setWidget(self.inner_widget)

    def change_selection(self, new_selection):
        if self.current_selection:
            self.current_selection.deselect_tile()

        self.current_selection = new_selection
        if self.current_selection:
            self.current_selection.select_tile()

    def mark_dirty(self):
        self._dirty = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.populate_grid()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.change_selection(None)

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self._dirty = False
            self.update_view(None)   # full refresh
        else:
            self.populate_grid()     # re-layout only

    def open_album_detail_view(self):
        self.parent_widget.change_to_album_detail_view(self.current_selection)


class CustomGridView(AlbumGridViewWidget):

    def __init__(self, parent, pipeline):
        self._pipeline = pipeline   # must be set before super().__init__ triggers _generate_album_tiles
        super().__init__(parent)

    def _generate_album_tiles(self):
        summaries = self.parent_widget.library.get_all_album_summaries()
        filtered = self._pipeline.apply(summaries)
        return [AlbumTile(self, s["album_title"], s["artist"], s["art"])
                for s in filtered]


class AlbumTile(Qtw.QWidget):
    def __init__(self, parent, name, artist, art):
        super().__init__()
        v_layout = Qtw.QVBoxLayout()
        self.setLayout(v_layout)
        self.is_selected = False
        self.parent_widget = parent
        self.album_title = name
        self.artist = artist

        self.setFocusPolicy(Qtc.Qt.FocusPolicy.ClickFocus)

        self.art_area = ArtArea(show_add=False)
        pixmap = Qtg.QPixmap()
        pixmap.loadFromData(art)
        self.art_area.setPixmap(pixmap)
        self.art_area.play_button.clicked.connect(self._play_album)

        name_text = ElidedLabel(name)
        name_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        artist_text = ElidedLabel(artist)
        artist_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)

        v_layout.addWidget(self.art_area)
        v_layout.addWidget(name_text)
        v_layout.addWidget(artist_text)

    def _play_album(self):
        main = self.parent_widget.parent_widget
        album_info = main.library.get_album_info(self.album_title, self.artist)
        tracks = album_info.get('track_list', [])
        if tracks:
            main.music_player.play(tracks[0], queue=tracks, queue_index=0)

    def set_parent_widget(self, parent):
        self.parent_widget = parent

    def deselect_tile(self):
        self.is_selected = False
        self.art_area.setStyleSheet("border: 0px")

    def select_tile(self):
        self.is_selected = True
        self.art_area.setStyleSheet("border: 2px solid blue")

    def _remove_album(self):
        library = self.parent_widget.parent_widget.library
        library.remove_album(self.album_title, self.artist)

    def _edit_album_metadata(self):
        library = self.parent_widget.parent_widget.library
        info = library.get_album_info(self.album_title, self.artist)
        tracks = info['track_list']
        dialog = AlbumMetadataEditDialog(tracks, self)
        if dialog.exec() == Qtw.QDialog.DialogCode.Accepted:
            updates = dialog.get_values()
            if updates:
                for i, track in enumerate(tracks):
                    library.update_track_metadata(
                        track['track'], updates,
                        notify=(i == len(tracks) - 1),
                    )

    def mousePressEvent(self, event):
        self.parent_widget.change_selection(self)
        self.setFocus()

    def mouseDoubleClickEvent(self, event):
        self.parent_widget.open_album_detail_view()

    def keyPressEvent(self, event):
        if event.key() in (Qtc.Qt.Key.Key_Delete, Qtc.Qt.Key.Key_Backspace):
            self._remove_album()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = Qtw.QMenu(self)
        edit_action   = menu.addAction("Edit album metadata")
        remove_action = menu.addAction("Remove from library")
        chosen = menu.exec(event.globalPos())
        if chosen is edit_action:
            self._edit_album_metadata()
        elif chosen is remove_action:
            self._remove_album()
