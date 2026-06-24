import PySide6.QtCore as Qtc
import PySide6.QtWidgets as Qtw

_ROLE_TRACK = Qtc.Qt.ItemDataRole.UserRole

_COL_POS    = 0
_COL_TITLE  = 1
_COL_DUR    = 2
_COL_ALBUM  = 3
_COL_ARTIST = 4
_COL_DATE   = 5
_COL_GENRE  = 6


class _ReorderTable(Qtw.QTableWidget):
    order_changed = Qtc.Signal()

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(Qtw.QAbstractItemView.DragDropMode.InternalMove)
        self.setDragDropOverwriteMode(False)
        self.setDefaultDropAction(Qtc.Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        # custom dropEvent needed so rows don't vanish into the ether when dragged
        if event.source() is not self:
            super().dropEvent(event)
            return

        src_rows = sorted(set(idx.row() for idx in self.selectedIndexes()))
        if not src_rows:
            event.ignore()
            return
        src = src_rows[0]

        pos = event.position().toPoint()
        idx = self.indexAt(pos)
        if idx.isValid():
            target = idx.row()
            if pos.y() > self.visualRect(idx).center().y():
                target += 1
        else:
            target = self.rowCount()

        if target == src or target == src + 1:
            event.ignore()
            return

        # QTableWidgetItem(orig) deep-copies all data roles including UserRole.
        row_data = []
        for col in range(self.columnCount()):
            orig = self.item(src, col)
            row_data.append(Qtw.QTableWidgetItem(orig) if orig else Qtw.QTableWidgetItem())

        # removeRow updates the selection model, clearing src from the selection.
        # With an empty selection, startDrag's clearOrRemove() will find nothing
        # to remove after drag->exec() returns — leaving our inserted row intact.
        self.removeRow(src)
        if target > src:
            target -= 1

        self.insertRow(target)
        for col, item in enumerate(row_data):
            self.setItem(target, col, item)

        self.clearSelection()   # for clearOrRemove
        event.accept()
        self.order_changed.emit()
        # Defer selectRow until after clearOrRemove has run (zero-delay timer fires
        # after drag->exec() returns and the drag machinery has fully unwound).
        _t = target
        Qtc.QTimer.singleShot(0, lambda: self.selectRow(_t))


class PlaylistViewWidget(Qtw.QWidget):
    def __init__(self, parent, playlist_id):
        super().__init__()
        self.parent_widget = parent
        self.playlist_id   = playlist_id
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = Qtw.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = _ReorderTable()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(["#", "Title", "Duration", "Album", "Artist", "Date", "Genre"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(Qtw.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(Qtw.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setSectionsClickable(False)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(_COL_POS,    Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_TITLE,  Qtw.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_DUR,    Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_ALBUM,  Qtw.QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(_COL_ARTIST, Qtw.QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(_COL_DATE,   Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_GENRE,  Qtw.QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(_COL_ALBUM,  200)
        self._table.setColumnWidth(_COL_ARTIST, 200)
        self._table.setColumnWidth(_COL_GENRE,  150)

        self._table.cellDoubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qtc.Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.installEventFilter(self)
        self._table.order_changed.connect(self._on_order_changed)

        layout.addWidget(self._table)

    def showEvent(self, event):
        super().showEvent(event)
        self.reload()

    def reload(self):
        tracks = self.parent_widget.library.get_playlist_tracks(self.playlist_id)
        self._table.setRowCount(len(tracks))
        for row, track in enumerate(tracks):
            self._fill_row(row, row + 1, track)

    def _fill_row(self, row, pos, track):
        pos_item = Qtw.QTableWidgetItem(str(pos))
        pos_item.setTextAlignment(Qtc.Qt.AlignmentFlag.AlignRight | Qtc.Qt.AlignmentFlag.AlignVCenter)

        title_item = Qtw.QTableWidgetItem(str(track.get('title') or ''))
        title_item.setData(_ROLE_TRACK, track)

        dur_item = Qtw.QTableWidgetItem(_fmt_dur(track.get('duration', 0)))
        dur_item.setTextAlignment(Qtc.Qt.AlignmentFlag.AlignRight | Qtc.Qt.AlignmentFlag.AlignVCenter)

        date_item = Qtw.QTableWidgetItem(str(track.get('date') or '')[:4])
        date_item.setTextAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)

        self._table.setItem(row, _COL_POS,    pos_item)
        self._table.setItem(row, _COL_TITLE,  title_item)
        self._table.setItem(row, _COL_DUR,    dur_item)
        self._table.setItem(row, _COL_ALBUM,  Qtw.QTableWidgetItem(str(track.get('album')  or '')))
        self._table.setItem(row, _COL_ARTIST, Qtw.QTableWidgetItem(str(track.get('artist') or '')))
        self._table.setItem(row, _COL_DATE,   date_item)
        self._table.setItem(row, _COL_GENRE,  Qtw.QTableWidgetItem(str(track.get('genres') or '')))

    def _on_order_changed(self):
        paths = []
        for row in range(self._table.rowCount()):
            self._table.item(row, _COL_POS).setText(str(row + 1))
            title_item = self._table.item(row, _COL_TITLE)
            if title_item:
                track = title_item.data(_ROLE_TRACK)
                if track:
                    paths.append(track['track'])
        self.parent_widget.library.update_playlist_order(self.playlist_id, paths)

    def _on_double_click(self, row, _col):
        title_item = self._table.item(row, _COL_TITLE)
        if title_item is None:
            return
        track = title_item.data(_ROLE_TRACK)
        if track is None:
            return
        queue = [
            self._table.item(r, _COL_TITLE).data(_ROLE_TRACK)
            for r in range(self._table.rowCount())
            if self._table.item(r, _COL_TITLE) is not None
        ]
        queue_index = next((i for i, t in enumerate(queue) if t.get('track') == track.get('track')), 0)
        self.parent_widget.music_player.play(track, queue=queue, queue_index=queue_index)

    def eventFilter(self, obj, event):
        if obj is self._table and event.type() == Qtc.QEvent.Type.KeyPress:
            if event.key() in (Qtc.Qt.Key.Key_Delete, Qtc.Qt.Key.Key_Backspace):
                self._remove_selected()
                return True
        return super().eventFilter(obj, event)

    def _show_context_menu(self, pos):
        if not self._table.selectedIndexes():
            return
        menu = Qtw.QMenu(self)
        remove_action = menu.addAction("Remove from playlist")
        if menu.exec(self._table.viewport().mapToGlobal(pos)) is remove_action:
            self._remove_selected()

    def _remove_selected(self):
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._table.removeRow(row)
        # Re-number and persist
        paths = []
        for row in range(self._table.rowCount()):
            self._table.item(row, _COL_POS).setText(str(row + 1))
            title_item = self._table.item(row, _COL_TITLE)
            if title_item:
                track = title_item.data(_ROLE_TRACK)
                if track:
                    paths.append(track['track'])
        self.parent_widget.library.update_playlist_order(self.playlist_id, paths)


def _fmt_dur(seconds):
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
