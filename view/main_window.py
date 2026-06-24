import PySide6.QtCore as Qtc
import PySide6.QtWidgets as Qtw

from model.filters import filter_from_dict
from view.album_grid_view import AlbumGridViewWidget, CustomGridView
from view.album_detail_view import AlbumDetailViewWidget
from view.search_view import SearchViewWidget
from view.top_bar import TopBar
from view.playlist_view import PlaylistViewWidget
from view.track_list_view import TrackListViewWidget, CustomTrackListView
from view.view_creation import ViewCreationWidget

# UserRole slots on QListWidgetItems
_ROLE_WIDGET  = Qtc.Qt.ItemDataRole.UserRole       # the widget in the stacked layout
_ROLE_VIEW_ID = Qtc.Qt.ItemDataRole.UserRole + 1   # DB row id


class MainWindow(Qtw.QWidget):
    main_v_layout = Qtw.QVBoxLayout()
    main_h_layout = Qtw.QHBoxLayout()

    top_bar_widget = None
    main_display_widget = None
    album_grid_view_widget = None
    album_detail_view_widget = None
    search_view_widget = None
    view_creation_widget = None
    _previous_widget = None  # restored on Cancel from view creation

    fixed_list = None
    views_list = None
    playlists_list = None
    _remove_view_btn     = None
    _edit_view_btn       = None
    _edit_playlist_btn   = None
    _remove_playlist_btn = None
    _pending_playlist_item = None   # item currently being named inline

    music_player = None
    library = None

    def __init__(self, music_player, library):
        super().__init__()
        self.setWindowTitle("LPMP")
        self.resize(1200, 800)
        self.setLayout(self.main_v_layout)

        self.music_player = music_player
        self.library = library
        self.library.pair_with_main_window(self)

        self.main_display_widget = Qtw.QStackedWidget()
        self.album_grid_view_widget = AlbumGridViewWidget(self)
        self.track_list_view_widget = TrackListViewWidget(self)
        self.album_detail_view_widget = AlbumDetailViewWidget(self)
        self.search_view_widget = SearchViewWidget(self)
        self.view_creation_widget = ViewCreationWidget(self)

        self.main_display_widget.addWidget(self.album_detail_view_widget)
        self.main_display_widget.addWidget(self.view_creation_widget)

        sidebar_widget = self._build_sidebar()

        self._add_to_sidebar_list(self.fixed_list, "Search", self.search_view_widget)
        self._add_to_sidebar_list(self.fixed_list, "Albums", self.album_grid_view_widget)
        self._add_to_sidebar_list(self.fixed_list, "Tracks", self.track_list_view_widget)

        self.fixed_list.setCurrentRow(1)  # Start on Albums view
        self.main_display_widget.setCurrentWidget(self.album_grid_view_widget)
        self.album_grid_view_widget.populate_grid()

        self.fixed_list.currentRowChanged.connect(
            lambda row: self._on_sidebar_list_selection(self.fixed_list, row)
        )
        self.views_list.currentRowChanged.connect(
            lambda row: self._on_sidebar_list_selection(self.views_list, row)
        )
        self.views_list.currentRowChanged.connect(
            lambda row: self._set_view_buttons_enabled(row >= 0)
        )
        self.playlists_list.currentRowChanged.connect(
            lambda row: self._on_sidebar_list_selection(self.playlists_list, row)
        )
        self.playlists_list.currentRowChanged.connect(
            lambda row: self._set_playlist_buttons_enabled(row >= 0)
        )
        self.playlists_list.itemChanged.connect(self._on_playlist_name_changed)

        self._load_saved_views()
        self._load_saved_playlists()

        self.top_bar_widget = TopBar(music_player, library, self)

        self.main_h_layout.addWidget(sidebar_widget)
        self.main_h_layout.addWidget(self.main_display_widget)

        self.main_v_layout.addWidget(self.top_bar_widget)
        self.main_v_layout.addLayout(self.main_h_layout)

    def _build_sidebar(self):
        sidebar_widget = Qtw.QWidget()
        sidebar_widget.setFixedWidth(160)
        layout = Qtw.QVBoxLayout(sidebar_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.fixed_list = Qtw.QListWidget()
        self.fixed_list.setSizePolicy(
            Qtw.QSizePolicy.Policy.Preferred,
            Qtw.QSizePolicy.Policy.Maximum,
        )

        views_header, self._edit_view_btn, self._remove_view_btn = self._sidebar_list_header(
            "Views",
            on_add=self._navigate_to_view_creation,
            on_edit=self._on_edit_view,
            on_remove=self._on_remove_view,
            add_tooltip="Add View",
            edit_tooltip="Edit View",
            remove_tooltip="Remove View",
        )
        self.views_list = Qtw.QListWidget()

        playlists_header, self._edit_playlist_btn, self._remove_playlist_btn = self._sidebar_list_header(
            "Playlists",
            on_add=self._on_add_playlist,
            on_edit=self._on_edit_playlist,
            on_remove=self._on_remove_playlist,
            add_tooltip="Add Playlist",
            edit_tooltip="Edit Playlist Name",
            remove_tooltip="Remove Playlist",
        )
        self.playlists_list = Qtw.QListWidget()
        self.playlists_list.setEditTriggers(Qtw.QAbstractItemView.EditTrigger.NoEditTriggers)

        layout.addWidget(self.fixed_list)
        layout.addWidget(views_header)
        layout.addWidget(self.views_list, stretch=1)
        layout.addWidget(playlists_header)
        layout.addWidget(self.playlists_list, stretch=1)

        return sidebar_widget

    @staticmethod
    def _sidebar_list_header(title, on_add=None, on_edit=None, on_remove=None,
                             add_tooltip=None, edit_tooltip=None, remove_tooltip=None):
        # Row with a section label and optional +/✎/− buttons on the right

        container = Qtw.QWidget()
        row = Qtw.QHBoxLayout(container)
        row.setContentsMargins(4, 4, 4, 4)
        row.addWidget(Qtw.QLabel(title))
        row.addStretch()
        edit_btn = remove_btn = None
        if on_add:
            btn = Qtw.QPushButton("+")
            btn.setFixedSize(20, 20)
            btn.clicked.connect(on_add)
            if add_tooltip:
                btn.setToolTip(add_tooltip)
            row.addWidget(btn)
        if on_edit:
            edit_btn = Qtw.QPushButton("✎")  # ✎
            edit_btn.setFixedSize(20, 20)
            edit_btn.setEnabled(False)
            edit_btn.clicked.connect(on_edit)
            if edit_tooltip:
                edit_btn.setToolTip(edit_tooltip)
            row.addWidget(edit_btn)
        if on_remove:
            remove_btn = Qtw.QPushButton("−")  # −
            remove_btn.setFixedSize(20, 20)
            remove_btn.setEnabled(False)
            remove_btn.clicked.connect(on_remove)
            if remove_tooltip:
                remove_btn.setToolTip(remove_tooltip)
            row.addWidget(remove_btn)
        return container, edit_btn, remove_btn

    def _set_view_buttons_enabled(self, enabled):
        if self._edit_view_btn:
            self._edit_view_btn.setEnabled(enabled)
        if self._remove_view_btn:
            self._remove_view_btn.setEnabled(enabled)

    def _add_to_sidebar_list(self, list_widget, label, widget, view_id=None):
        self.main_display_widget.addWidget(widget)
        item = Qtw.QListWidgetItem(label)
        item.setData(_ROLE_WIDGET, widget)
        if view_id is not None:
            item.setData(_ROLE_VIEW_ID, view_id)
        list_widget.addItem(item)

    def add_sidebar_view_entry(self, label, widget, view_id=None):
        self._add_to_sidebar_list(self.views_list, label, widget, view_id)

    def add_sidebar_playlist_entry(self, label, widget, playlist_id=None):
        self._add_to_sidebar_list(self.playlists_list, label, widget, view_id=playlist_id)
        # Make the item renameable via editItem()
        item = self.playlists_list.item(self.playlists_list.count() - 1)
        item.setFlags(item.flags() | Qtc.Qt.ItemFlag.ItemIsEditable)

    def _on_sidebar_list_selection(self, source_list, row):
        if row < 0:
            return
        for lst in (self.fixed_list, self.views_list, self.playlists_list):
            if lst is not source_list:
                lst.blockSignals(True)
                lst.setCurrentRow(-1)
                lst.blockSignals(False)
        item = source_list.item(row)
        if item:
            self.main_display_widget.setCurrentWidget(item.data(_ROLE_WIDGET))

    def _navigate_to_view(self, widget):
        # Switch to a view from the list and change selections accordingly
        for lst in (self.fixed_list, self.views_list, self.playlists_list):
            for row in range(lst.count()):
                if lst.item(row).data(_ROLE_WIDGET) is widget:
                    lst.setCurrentRow(row)
                    self.main_display_widget.setCurrentWidget(widget)
                    return

    def _navigate_to_view_creation(self):
        self._previous_widget = self.main_display_widget.currentWidget()
        self.view_creation_widget.reset()   # clears _editing_item; adds one example block
        self.main_display_widget.setCurrentWidget(self.view_creation_widget)

    def toggle_search_view(self):
        if self.main_display_widget.currentWidget() is not self.search_view_widget:
            self._navigate_to_view(self.search_view_widget)
        else:
            self._navigate_to_view(self.album_grid_view_widget)

    def change_to_album_detail_view(self, album_tile):
        album_info = self.library.get_album_info(album_tile.album_title, album_tile.artist)
        self.album_detail_view_widget.set_album_info(album_info)
        self.main_display_widget.setCurrentWidget(self.album_detail_view_widget)

    def change_to_album_grid_view(self):
        self._navigate_to_view(self.album_grid_view_widget)

    def _make_view_widget(self, pipeline):
        if getattr(pipeline, 'view_type', 'grid') == 'list':
            return CustomTrackListView(self, pipeline)
        return CustomGridView(self, pipeline)

    def _create_new_view(self, name, pipeline_dict):
        view_id  = self.library.save_view(name, pipeline_dict)
        pipeline = filter_from_dict(pipeline_dict)
        widget   = self._make_view_widget(pipeline)
        self.add_sidebar_view_entry(name, widget, view_id)
        self._navigate_to_view(widget)

    def _apply_view_edit(self, item, name, pipeline_dict):
        old_widget = item.data(_ROLE_WIDGET)
        view_id    = item.data(_ROLE_VIEW_ID)
        pipeline   = filter_from_dict(pipeline_dict)
        new_widget = self._make_view_widget(pipeline)

        self.main_display_widget.addWidget(new_widget)
        item.setText(name)
        item.setData(_ROLE_WIDGET, new_widget)
        self._navigate_to_view(new_widget)

        self.main_display_widget.removeWidget(old_widget)
        old_widget.deleteLater()

        if view_id is not None:
            self.library.update_view(view_id, name, pipeline_dict)

    def _on_edit_view(self):
        row = self.views_list.currentRow()
        if row < 0:
            return
        item = self.views_list.item(row)
        if not item:
            return

        self._previous_widget = self.main_display_widget.currentWidget()

        pipeline_dict = item.data(_ROLE_WIDGET)._pipeline.to_dict()
        self.view_creation_widget.populate(item.text(), pipeline_dict, editing_item=item)
        self.main_display_widget.setCurrentWidget(self.view_creation_widget)

    def _on_view_creation_cancelled(self):
        prev = self._previous_widget or self.album_grid_view_widget
        if self.main_display_widget.indexOf(prev) >= 0:
            self.main_display_widget.setCurrentWidget(prev)
        else:
            self.main_display_widget.setCurrentWidget(self.album_grid_view_widget)

    def _on_remove_view(self):
        row = self.views_list.currentRow()
        if row < 0:
            return
        item = self.views_list.item(row)
        if not item:
            return

        widget  = item.data(_ROLE_WIDGET)
        view_id = item.data(_ROLE_VIEW_ID)

        # Block all list signals during removal to prevent cascading navigation.
        for lst in (self.fixed_list, self.views_list, self.playlists_list):
            lst.blockSignals(True)

        self.views_list.takeItem(row)
        self.views_list.setCurrentRow(-1)

        if self.main_display_widget.currentWidget() is widget:
            self.fixed_list.setCurrentRow(1)
            self.main_display_widget.setCurrentWidget(self.album_grid_view_widget)

        for lst in (self.fixed_list, self.views_list, self.playlists_list):
            lst.blockSignals(False)

        self.main_display_widget.removeWidget(widget)
        widget.deleteLater()
        self._set_view_buttons_enabled(False)

        if view_id is not None:
            self.library.delete_view(view_id)

    def _set_playlist_buttons_enabled(self, enabled):
        if self._edit_playlist_btn:
            self._edit_playlist_btn.setEnabled(enabled)
        if self._remove_playlist_btn:
            self._remove_playlist_btn.setEnabled(enabled)

    def _on_add_playlist(self):
        playlist_id = self.library.create_playlist("New Playlist")
        widget = PlaylistViewWidget(self, playlist_id)
        # Block itemChanged so setText doesn't trigger rename logic
        self.playlists_list.blockSignals(True)
        self.add_sidebar_playlist_entry("New Playlist", widget, playlist_id)
        self.playlists_list.blockSignals(False)

        item = self.playlists_list.item(self.playlists_list.count() - 1)
        self._pending_playlist_item = item
        self._navigate_to_view(widget)
        self.playlists_list.editItem(item)

    def _on_edit_playlist(self):
        row = self.playlists_list.currentRow()
        if row < 0:
            return
        item = self.playlists_list.item(row)
        if item:
            self._pending_playlist_item = item
            self.playlists_list.editItem(item)

    def _on_remove_playlist(self):
        row = self.playlists_list.currentRow()
        if row < 0:
            return
        item = self.playlists_list.item(row)
        if not item:
            return

        widget      = item.data(_ROLE_WIDGET)
        playlist_id = item.data(_ROLE_VIEW_ID)

        for lst in (self.fixed_list, self.views_list, self.playlists_list):
            lst.blockSignals(True)

        self.playlists_list.takeItem(row)
        self.playlists_list.setCurrentRow(-1)

        if self.main_display_widget.currentWidget() is widget:
            self.fixed_list.setCurrentRow(1)
            self.main_display_widget.setCurrentWidget(self.album_grid_view_widget)

        for lst in (self.fixed_list, self.views_list, self.playlists_list):
            lst.blockSignals(False)

        self.main_display_widget.removeWidget(widget)
        widget.deleteLater()
        self._set_playlist_buttons_enabled(False)

        if playlist_id is not None:
            self.library.delete_playlist(playlist_id)

    def _on_playlist_name_changed(self, item):
        # Only act on the item currently being edited
        if item is not self._pending_playlist_item:
            return
        self._pending_playlist_item = None

        name = item.text().strip()
        if not name:
            self.playlists_list.blockSignals(True)
            item.setText("New Playlist")
            self.playlists_list.blockSignals(False)
            name = "New Playlist"

        playlist_id = item.data(_ROLE_VIEW_ID)
        if playlist_id is not None:
            self.library.rename_playlist(playlist_id, name)

    def _load_saved_views(self):
        for view_data in self.library.load_all_views():
            try:
                pipeline = filter_from_dict(view_data["pipeline"])
            except (ValueError, KeyError):
                continue
            widget = self._make_view_widget(pipeline)
            self.add_sidebar_view_entry(view_data["name"], widget, view_data["id"])

    def _load_saved_playlists(self):
        for pl in self.library.load_all_playlists():
            widget = PlaylistViewWidget(self, pl['id'])
            self.add_sidebar_playlist_entry(pl['name'], widget, pl['id'])

    def notify_playlist_changed(self, playlist_id):
        # Reload a playlist view immediately if it's currently visible
        current = self.main_display_widget.currentWidget()
        for row in range(self.playlists_list.count()):
            widget = self.playlists_list.item(row).data(_ROLE_WIDGET)
            if getattr(widget, 'playlist_id', None) == playlist_id and widget is current:
                widget.reload()

    def notify_changes(self):
        current = self.main_display_widget.currentWidget()
        for lst in (self.fixed_list, self.views_list):
            for row in range(lst.count()):
                widget = lst.item(row).data(_ROLE_WIDGET)
                if not hasattr(widget, 'mark_dirty'):
                    continue
                if widget is current:
                    widget.update_view(None)   # visible now — update immediately
                else:
                    widget.mark_dirty()        # hidden — update on next show

    def closeEvent(self, event):
        self.top_bar_widget.set_is_shutting_down(True)
        self.music_player.shutdown()
        super().closeEvent(event)
