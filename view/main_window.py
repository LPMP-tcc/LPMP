import PySide6.QtWidgets as Qtw

from view.top_bar import TopBar
from view.album_grid_view import AlbumGridViewWidget
from view.album_detail_view import AlbumDetailViewWidget
from view.search_view import SearchViewWidget


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
        self.music_player.shutdown()
        super().closeEvent(event)
