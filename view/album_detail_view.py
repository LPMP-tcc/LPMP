import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw

from view.metadata_edit_dialog import AlbumMetadataEditDialog, MetadataEditDialog

_ROLE_TRACK = Qtc.Qt.ItemDataRole.UserRole


class _NumericItem(Qtw.QTableWidgetItem):
    def __lt__(self, other):
        a = self.data(Qtc.Qt.ItemDataRole.UserRole)
        b = other.data(Qtc.Qt.ItemDataRole.UserRole)
        try:
            return float(a or 0) < float(b or 0)
        except (TypeError, ValueError):
            return super().__lt__(other)


class AlbumDetailViewWidget(Qtw.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent_widget = parent
        self.album_info = None
        self._build_ui()

    def _build_ui(self):
        root = Qtw.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # header
        header = Qtw.QHBoxLayout()

        back_btn = Qtw.QPushButton("<")
        back_btn.setMaximumWidth(20)
        back_btn.clicked.connect(self.parent_widget.change_to_album_grid_view)
        header.addWidget(back_btn, alignment=Qtc.Qt.AlignmentFlag.AlignTop)

        self._art_label = Qtw.QLabel()
        self._art_label.setFixedSize(300, 300)
        self._art_label.setScaledContents(True)
        header.addWidget(self._art_label)

        info = Qtw.QVBoxLayout()
        info.addStretch()

        self._title_label = Qtw.QLabel()
        self._title_label.setWordWrap(True)
        font = self._title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        self._title_label.setFont(font)

        self._artist_label = Qtw.QLabel()
        self._genre_label  = Qtw.QLabel()

        edit_album_btn = Qtw.QPushButton("✎")
        edit_album_btn.setFixedSize(20, 20)
        edit_album_btn.setToolTip("Edit album metadata")
        edit_album_btn.clicked.connect(self._edit_album_metadata)

        info.addWidget(self._title_label)
        info.addWidget(self._artist_label)
        info.addWidget(self._genre_label)
        info.addWidget(edit_album_btn, alignment=Qtc.Qt.AlignmentFlag.AlignLeft)
        info.addStretch()
        header.addLayout(info, stretch=1)

        root.addLayout(header)

        # track table
        self._table = Qtw.QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["#", "Title", "Duration", "Genre"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(Qtw.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(Qtw.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, Qtw.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, Qtw.QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(3, 150)

        self._table.cellDoubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qtc.Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.installEventFilter(self)

        root.addWidget(self._table)

    def set_album_info(self, album_info):
        self.album_info = album_info

    def populate(self):
        if self.album_info is None:
            return

        pixmap = Qtg.QPixmap()
        pixmap.loadFromData(self.album_info['art'])
        self._art_label.setPixmap(pixmap)
        self._title_label.setText(self.album_info['album_title'])
        self._artist_label.setText(self.album_info['artist'])

        tracks = self.album_info['track_list']

        genres_set = set()
        for t in tracks:
            for g in (t.get('genres') or '').split(','):
                g = g.strip()
                if g:
                    genres_set.add(g)
        self._genre_label.setText(', '.join(sorted(genres_set)))

        multi_disc = len({t.get('disc') for t in tracks if t.get('disc')}) > 1

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            num  = track.get('number')
            disc = track.get('disc')
            if multi_disc and disc:
                num_str = f"{disc}-{num}" if num is not None else str(disc)
            else:
                num_str = str(num) if num is not None else ''
            sort_val = (int(disc or 1)) * 10000 + (int(num or 0)) if multi_disc else (num or 0)
            num_item = _NumericItem(num_str)
            num_item.setData(Qtc.Qt.ItemDataRole.UserRole, sort_val)
            num_item.setTextAlignment(
                Qtc.Qt.AlignmentFlag.AlignRight | Qtc.Qt.AlignmentFlag.AlignVCenter
            )

            title_item = Qtw.QTableWidgetItem(str(track.get('title') or ''))
            title_item.setData(_ROLE_TRACK, track)

            dur_item = Qtw.QTableWidgetItem(_format_duration(track.get('duration', 0)))
            dur_item.setTextAlignment(
                Qtc.Qt.AlignmentFlag.AlignRight | Qtc.Qt.AlignmentFlag.AlignVCenter
            )

            self._table.setItem(row, 0, num_item)
            self._table.setItem(row, 1, title_item)
            self._table.setItem(row, 2, dur_item)
            self._table.setItem(row, 3, Qtw.QTableWidgetItem(str(track.get('genres') or '')))

        self._table.setSortingEnabled(True)

    def showEvent(self, event):
        super().showEvent(event)
        self.populate()

    def eventFilter(self, obj, event):
        if obj is self._table and event.type() == Qtc.QEvent.Type.KeyPress:
            if event.key() in (Qtc.Qt.Key.Key_Delete, Qtc.Qt.Key.Key_Backspace):
                self._remove_selected()
                return True
        return super().eventFilter(obj, event)

    def _edit_album_metadata(self):
        if not self.album_info:
            return
        tracks = self.album_info['track_list']
        dialog = AlbumMetadataEditDialog(tracks, self)
        if dialog.exec() == Qtw.QDialog.DialogCode.Accepted:
            updates = dialog.get_values()
            if updates:
                library = self.parent_widget.library
                for i, track in enumerate(tracks):
                    library.update_track_metadata(
                        track['track'], updates,
                        notify=(i == len(tracks) - 1), # prevent N UI redraws when editing metadata for N tracks
                    )

    def _show_context_menu(self, pos):
        if not self._table.selectedIndexes():
            return
        menu = Qtw.QMenu(self)
        edit_action   = menu.addAction("Edit metadata")
        remove_action = menu.addAction("Remove from library")

        playlists = self.parent_widget.library.load_all_playlists()
        if playlists:
            sub = menu.addMenu("Add to playlist")
            for pl in playlists:
                action = sub.addAction(pl['name'])
                action.setData(pl['id'])

        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is edit_action:
            self._edit_metadata()
        elif chosen is remove_action:
            self._remove_selected()
        elif chosen.data() is not None:
            self._add_selected_to_playlist(chosen.data())

    def _edit_metadata(self):
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        if not rows:
            return
        item = self._table.item(rows[0], 1)
        if not item:
            return
        track = item.data(_ROLE_TRACK)
        if not track:
            return
        dialog = MetadataEditDialog(track, self)
        if dialog.exec() == Qtw.QDialog.DialogCode.Accepted:
            self.parent_widget.library.update_track_metadata(track['track'], dialog.get_values())

    def _add_selected_to_playlist(self, playlist_id):
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        for row in rows:
            item = self._table.item(row, 1)
            if item:
                track = item.data(_ROLE_TRACK)
                if track:
                    self.parent_widget.library.add_track_to_playlist(playlist_id, track['track'])
        self.parent_widget.notify_playlist_changed(playlist_id)

    def _remove_selected(self):
        # Remove rows in reverse so indices don't shift mid-loop.
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        paths = []
        for row in rows:
            item = self._table.item(row, 1)
            if item:
                track = item.data(_ROLE_TRACK)
                if track:
                    paths.append(track['track'])
            self._table.removeRow(row)
        if paths:
            self.parent_widget.library.remove_tracks_batch(paths)

    def _on_double_click(self, row, _col):
        title_item = self._table.item(row, 1)
        if title_item is None:
            return
        track = title_item.data(_ROLE_TRACK)
        if track is None:
            return
        queue = [
            self._table.item(r, 1).data(_ROLE_TRACK)
            for r in range(self._table.rowCount())
            if self._table.item(r, 1) is not None
        ]
        queue_index = next((i for i, t in enumerate(queue) if t.get('track') == track.get('track')), 0)
        self.parent_widget.music_player.play(track, queue=queue, queue_index=queue_index)


def _format_duration(seconds):
    if not seconds:
        return ''
    try:
        s = int(float(seconds))
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
    except (ValueError, TypeError):
        return str(seconds)
