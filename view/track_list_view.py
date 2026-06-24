import PySide6.QtCore as Qtc
import PySide6.QtWidgets as Qtw

from model.filters import SortFilter
from view.metadata_edit_dialog import MetadataEditDialog

# Column indices
_COL_NUM      = 0
_COL_TITLE    = 1
_COL_DURATION = 2
_COL_ALBUM    = 3
_COL_ARTIST   = 4
_COL_DATE     = 5
_COL_GENRE    = 6

# UserRole on the title cell stores the track dict for the row.
_ROLE_TRACK = Qtc.Qt.ItemDataRole.UserRole


class _NumericItem(Qtw.QTableWidgetItem):
    """QTableWidgetItem that sorts by a numeric UserRole value."""
    def __lt__(self, other):
        a = self.data(Qtc.Qt.ItemDataRole.UserRole)
        b = other.data(Qtc.Qt.ItemDataRole.UserRole)
        try:
            return float(a or 0) < float(b or 0)
        except (TypeError, ValueError):
            return super().__lt__(other)


class TrackListViewWidget(Qtw.QWidget):
    _COLUMNS     = ["#", "Title", "Duration", "Album", "Artist", "Date", "Genre"]
    _sort_enabled = True   # set to False in subclasses to lock header sorting

    def __init__(self, parent):
        super().__init__()
        self.parent_widget = parent
        self._dirty = False
        self._initial_sort_done = False
        self._build_ui()
        self.update_view(None)

    def _build_ui(self):
        layout = Qtw.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = Qtw.QTableWidget()
        self._table.setColumnCount(len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(Qtw.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(Qtw.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(_COL_NUM,      Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_TITLE,    Qtw.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_DURATION, Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_ALBUM,    Qtw.QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(_COL_ARTIST,   Qtw.QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(_COL_DATE,     Qtw.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_GENRE,    Qtw.QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(_COL_ALBUM,  200)
        self._table.setColumnWidth(_COL_ARTIST, 200)
        self._table.setColumnWidth(_COL_GENRE,  150)

        self._table.cellDoubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qtc.Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.installEventFilter(self)

        layout.addWidget(self._table)

    def mark_dirty(self):
        self._dirty = True

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self._dirty = False
            self.update_view(None)

    def update_view(self, _):
        self._populate_table(self._get_tracks())

    def _get_tracks(self):
        return SortFilter('artist', 'date', 'number').apply(
            self.parent_widget.library.library
        )

    def _populate_table(self, tracks):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            num = track.get('number')
            num_item = _NumericItem(str(num) if num is not None else '')
            num_item.setData(Qtc.Qt.ItemDataRole.UserRole, num or 0)
            num_item.setTextAlignment(
                Qtc.Qt.AlignmentFlag.AlignRight | Qtc.Qt.AlignmentFlag.AlignVCenter
            )

            # Title cell carries the track dict so double-click always reads
            # the right track regardless of how the user has sorted the table.
            title_item = Qtw.QTableWidgetItem(str(track.get('title') or ''))
            title_item.setData(_ROLE_TRACK, track)

            dur_item = Qtw.QTableWidgetItem(_fmt_dur(track.get('duration', 0)))
            dur_item.setTextAlignment(
                Qtc.Qt.AlignmentFlag.AlignRight | Qtc.Qt.AlignmentFlag.AlignVCenter
            )

            date_item = Qtw.QTableWidgetItem((str(track.get('date') or ''))[:4])
            date_item.setTextAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)

            self._table.setItem(row, _COL_NUM,      num_item)
            self._table.setItem(row, _COL_TITLE,    title_item)
            self._table.setItem(row, _COL_DURATION, dur_item)
            self._table.setItem(row, _COL_ALBUM,    Qtw.QTableWidgetItem(str(track.get('album') or '')))
            self._table.setItem(row, _COL_ARTIST,   Qtw.QTableWidgetItem(str(track.get('artist') or '')))
            self._table.setItem(row, _COL_DATE,     date_item)
            self._table.setItem(row, _COL_GENRE,    Qtw.QTableWidgetItem(str(track.get('genres') or '')))

        if self._sort_enabled:
            self._table.setSortingEnabled(True)
            if not self._initial_sort_done:
                self._table.sortByColumn(_COL_ALBUM, Qtc.Qt.SortOrder.AscendingOrder)
                self._initial_sort_done = True

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
        item = self._table.item(rows[0], _COL_TITLE)
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
            item = self._table.item(row, _COL_TITLE)
            if item:
                track = item.data(_ROLE_TRACK)
                if track:
                    self.parent_widget.library.add_track_to_playlist(playlist_id, track['track'])
        self.parent_widget.notify_playlist_changed(playlist_id)

    def _remove_selected(self):
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        paths = []
        for row in rows:
            item = self._table.item(row, _COL_TITLE)
            if item:
                track = item.data(_ROLE_TRACK)
                if track:
                    paths.append(track['track'])
        if paths:
            self.parent_widget.library.remove_tracks_batch(paths)

    def _on_double_click(self, row, _col):
        title_item = self._table.item(row, _COL_TITLE)
        if title_item is None:
            return
        track = title_item.data(_ROLE_TRACK)
        if track is None:
            return
        # Build the queue in the table's current display order.
        queue = []
        for r in range(self._table.rowCount()):
            t = self._table.item(r, _COL_TITLE)
            if t is not None:
                queue.append(t.data(_ROLE_TRACK))
        queue_index = next((i for i, t in enumerate(queue) if t.get('track') == track.get('track')), 0)
        self.parent_widget.music_player.play(track, queue=queue, queue_index=queue_index)


class CustomTrackListView(TrackListViewWidget):
    # A track list view driven by an arbitrary combination of filter blocks
    _sort_enabled = False

    def __init__(self, parent, pipeline):
        self._pipeline = pipeline
        super().__init__(parent)
        self._table.horizontalHeader().setSectionsClickable(False)

    def _get_tracks(self):
        tracks = self.parent_widget.library.library
        # expose album_title so View conditions work the same as on album grid views
        normed = [{**t, 'album_title': t.get('album', '')} for t in tracks]
        return self._pipeline.apply(normed)


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
