import PySide6.QtCore as Qtc
import PySide6.QtGui as Qtg
import PySide6.QtWidgets as Qtw

_ALBUM_FIELDS = [
    ('artist',       'Artist:'),
    ('album_artist', 'Album Artist:'),
    ('album',        'Album:'),
    ('disc',         'Disc #:'),
    ('date',         'Date:'),
    ('composers',    'Composers:'),
    ('genres',       'Genres:'),
]


class _MixedLineEdit(Qtw.QLineEdit):
    # for when a field has different values across tracks
    def __init__(self, value, is_differing):
        super().__init__()
        if is_differing:
            self.setPlaceholderText("differing values")
            font = self.font()
            font.setItalic(True)
            self.setFont(font)
            palette = self.palette()
            palette.setColor(Qtg.QPalette.ColorRole.PlaceholderText, Qtg.QColor(140, 140, 140))
            self.setPalette(palette)
            self.textChanged.connect(self._on_first_edit)
        else:
            self.setText(value)

    def _on_first_edit(self, text):
        if text:
            font = self.font()
            font.setItalic(False)
            self.setFont(font)
            self.textChanged.disconnect(self._on_first_edit)


class AlbumMetadataEditDialog(Qtw.QDialog):
    def __init__(self, tracks, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Album Metadata")
        self.setMinimumWidth(420)

        form = Qtw.QFormLayout()
        form.setLabelAlignment(Qtc.Qt.AlignmentFlag.AlignRight)

        self._edits = {}
        for field_key, label in _ALBUM_FIELDS:
            values = {t.get(field_key) for t in tracks}
            is_differing = len(values) > 1
            if is_differing:
                common = ''
            else:
                v = next(iter(values))
                common = str(v) if v is not None else ''
            edit = _MixedLineEdit(common, is_differing)
            self._edits[field_key] = (edit, is_differing)
            form.addRow(label, edit)

        buttons = Qtw.QDialogButtonBox(
            Qtw.QDialogButtonBox.StandardButton.Save |
            Qtw.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = Qtw.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_values(self):
        result = {}
        for field_key, (edit, was_differing) in self._edits.items():
            text = edit.text()
            if was_differing and not text:
                continue  # differing field was untouched = don't overwrite
            if field_key == 'disc':
                try:
                    result[field_key] = int(text) if text else None
                except ValueError:
                    result[field_key] = None
            else:
                result[field_key] = text
        return result


class MetadataEditDialog(Qtw.QDialog):
    def __init__(self, track, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Metadata")
        self.setMinimumWidth(420)

        form = Qtw.QFormLayout()
        form.setLabelAlignment(Qtc.Qt.AlignmentFlag.AlignRight)

        self._title        = Qtw.QLineEdit(track.get('title')        or '')
        self._artist       = Qtw.QLineEdit(track.get('artist')       or '')
        self._album_artist = Qtw.QLineEdit(track.get('album_artist') or '')
        self._album        = Qtw.QLineEdit(track.get('album')        or '')
        self._number       = Qtw.QLineEdit(str(track['number']) if track.get('number') is not None else '')
        self._disc         = Qtw.QLineEdit(str(track['disc'])   if track.get('disc')   is not None else '')
        self._date         = Qtw.QLineEdit(track.get('date')         or '')
        self._composers    = Qtw.QLineEdit(track.get('composers')    or '')
        self._genres       = Qtw.QLineEdit(track.get('genres')       or '')

        form.addRow("Title:",        self._title)
        form.addRow("Artist:",       self._artist)
        form.addRow("Album Artist:", self._album_artist)
        form.addRow("Album:",        self._album)
        form.addRow("Track #:",      self._number)
        form.addRow("Disc #:",       self._disc)
        form.addRow("Date:",         self._date)
        form.addRow("Composers:",    self._composers)
        form.addRow("Genres:",       self._genres)

        buttons = Qtw.QDialogButtonBox(
            Qtw.QDialogButtonBox.StandardButton.Save |
            Qtw.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = Qtw.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_values(self):
        def _int_or_none(text):
            t = text.strip()
            try:
                return int(t) if t else None
            except ValueError:
                return None
        return {
            'title':        self._title.text().strip(),
            'artist':       self._artist.text().strip(),
            'album_artist': self._album_artist.text().strip(),
            'album':        self._album.text().strip(),
            'number':       _int_or_none(self._number.text()),
            'disc':         _int_or_none(self._disc.text()),
            'date':         self._date.text().strip(),
            'composers':    self._composers.text().strip(),
            'genres':       self._genres.text().strip(),
        }
