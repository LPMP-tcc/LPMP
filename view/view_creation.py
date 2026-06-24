import re as _re

import PySide6.QtCore as Qtc
import PySide6.QtWidgets as Qtw

from model.filters import Condition, Section, View

_ALBUM_FIELDS = [
    ('artist',      'Artist'),
    ('album_title', 'Album Title'),
    ('date',        'Date'),
    ('genres',      'Genre'),
]

_OPS       = ['contains', 'equals', 'regex', 'range', 'fuzzy']
_OP_LABELS = ['Contains', 'Equals',  'Regex', 'Range', 'Fuzzy']

_RANGE_FIELD = 'date'

class _FieldCombo(Qtw.QComboBox):
    def __init__(self):
        super().__init__()
        for key, label in _ALBUM_FIELDS:
            self.addItem(label, key)

    def current_field(self):
        return self.currentData()

    def set_field(self, key):
        idx = self.findData(key)
        if idx >= 0:
            self.setCurrentIndex(idx)


def _parse_num(text):
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return text


class _ValueStack(Qtw.QStackedWidget):
    def __init__(self):
        super().__init__()
        self._build_pages()

    def _build_pages(self):
        # 0 — contains  (case-insensitive)
        p = Qtw.QWidget()
        r = Qtw.QHBoxLayout(p)
        r.setContentsMargins(0, 0, 0, 0)
        self._c_value = Qtw.QLineEdit()
        r.addWidget(self._c_value)
        self.addWidget(p)

        # 1 — equals
        p = Qtw.QWidget()
        r = Qtw.QHBoxLayout(p)
        r.setContentsMargins(0, 0, 0, 0)
        self._e_value = Qtw.QLineEdit()
        r.addWidget(self._e_value)
        self.addWidget(p)

        # 2 — regex
        p = Qtw.QWidget()
        r = Qtw.QHBoxLayout(p)
        r.setContentsMargins(0, 0, 0, 0)
        self._rx_pattern     = Qtw.QLineEdit()
        self._rx_ignore_case = Qtw.QCheckBox('ignore case')
        r.addWidget(self._rx_pattern)
        r.addWidget(self._rx_ignore_case)
        self.addWidget(p)

        # 3 — range  (Date only)
        p = Qtw.QWidget()
        r = Qtw.QHBoxLayout(p)
        r.setContentsMargins(0, 0, 0, 0)
        self._rng_min = Qtw.QLineEdit()
        self._rng_min.setPlaceholderText('YYYY-MM-DD')
        self._rng_max = Qtw.QLineEdit()
        self._rng_max.setPlaceholderText('YYYY-MM-DD')
        r.addWidget(self._rng_min)
        r.addWidget(Qtw.QLabel('–'))
        r.addWidget(self._rng_max)
        self.addWidget(p)

        # 4 — fuzzy
        p = Qtw.QWidget()
        r = Qtw.QHBoxLayout(p)
        r.setContentsMargins(0, 0, 0, 0)
        self._fz_query     = Qtw.QLineEdit()
        self._fz_threshold = Qtw.QSpinBox()
        self._fz_threshold.setRange(0, 100)
        self._fz_threshold.setValue(80)
        r.addWidget(self._fz_query)
        r.addWidget(Qtw.QLabel('score ≥'))
        r.addWidget(self._fz_threshold)
        self.addWidget(p)

    def current_params(self):
        idx = self.currentIndex()
        if idx == 0:
            return {'value': self._c_value.text()}
        if idx == 1:
            return {'value': self._e_value.text()}
        if idx == 2:
            flags = _re.IGNORECASE if self._rx_ignore_case.isChecked() else 0
            return {'pattern': self._rx_pattern.text(), 'flags': flags}
        if idx == 3:
            return {'min': self._rng_min.text().strip() or None,
                    'max': self._rng_max.text().strip() or None}
        if idx == 4:
            return {'query': self._fz_query.text(),
                    'threshold': self._fz_threshold.value()}
        return {}

    def populate(self, op_idx, d):
        self.setCurrentIndex(op_idx)
        if op_idx == 0:
            self._c_value.setText(str(d.get('value', '')))
        elif op_idx == 1:
            self._e_value.setText(str(d.get('value', '')))
        elif op_idx == 2:
            self._rx_pattern.setText(d.get('pattern', ''))
            self._rx_ignore_case.setChecked(bool(d.get('flags', 0) & _re.IGNORECASE))
        elif op_idx == 3:
            self._rng_min.setText(str(d.get('min', '') or ''))
            self._rng_max.setText(str(d.get('max', '') or ''))
        elif op_idx == 4:
            self._fz_query.setText(d.get('query', ''))
            self._fz_threshold.setValue(d.get('threshold', 80))


class ConditionRow(Qtw.QWidget):
    def __init__(self, on_remove):
        super().__init__()
        layout = Qtw.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self._not_chk = Qtw.QCheckBox('NOT')
        self._field   = _FieldCombo()
        self._op      = Qtw.QComboBox()
        self._op.addItems(_OP_LABELS)
        self._values  = _ValueStack()

        rm = Qtw.QPushButton('−')
        rm.setFixedSize(20, 20)
        rm.clicked.connect(lambda: on_remove(self))

        self._op.currentIndexChanged.connect(self._on_op_changed)

        layout.addWidget(self._not_chk)
        layout.addWidget(self._field)
        layout.addWidget(self._op)
        layout.addWidget(self._values, stretch=1)
        layout.addWidget(rm)

    def _on_op_changed(self, idx):
        self._values.setCurrentIndex(idx)
        is_range = _OPS[idx] == 'range'
        if is_range:
            self._field.set_field(_RANGE_FIELD)
        self._field.setEnabled(not is_range)

    def to_condition(self):
        op_idx = self._op.currentIndex()
        return Condition(
            field   = self._field.current_field(),
            op      = _OPS[op_idx],
            negated = self._not_chk.isChecked(),
            **self._values.current_params(),
        )

    def populate_from_dict(self, d):
        op     = d.get('op', 'contains')
        op_idx = _OPS.index(op) if op in _OPS else 0
        # Set op first so _on_op_changed can lock the field if needed.
        self._op.setCurrentIndex(op_idx)
        # Override locked field with the saved value (for non-range ops).
        if op != 'range':
            self._field.set_field(d.get('field', ''))
        self._values.populate(op_idx, d)
        self._not_chk.setChecked(d.get('negated', False))


class SortKeyRow(Qtw.QWidget):
    def __init__(self, on_remove):
        super().__init__()
        layout = Qtw.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self._field = _FieldCombo()
        self._order = Qtw.QComboBox()
        self._order.addItems(['Ascending', 'Descending'])

        rm = Qtw.QPushButton('−')
        rm.setFixedSize(20, 20)
        rm.clicked.connect(lambda: on_remove(self))

        layout.addWidget(self._field, stretch=1)
        layout.addWidget(self._order)
        layout.addWidget(rm)

    def to_sort_key(self):
        return {'field': self._field.current_field(),
                'reverse': self._order.currentIndex() == 1}

    def populate_from_dict(self, d):
        self._field.set_field(d.get('field', ''))
        self._order.setCurrentIndex(1 if d.get('reverse', False) else 0)


class SectionBlock(Qtw.QFrame):
    def __init__(self, on_remove):
        super().__init__()
        self.setFrameStyle(Qtw.QFrame.Shape.Box | Qtw.QFrame.Shadow.Sunken)
        self.setLineWidth(2)
        self.setAutoFillBackground(True)
        self.setSizePolicy(
            Qtw.QSizePolicy.Policy.Preferred,
            Qtw.QSizePolicy.Policy.Maximum,  # never taller than sizeHint()
        )
        self._condition_rows = []
        self._sort_key_rows  = []
        self._build_ui(on_remove)

    def _build_ui(self, on_remove):
        outer = Qtw.QVBoxLayout(self)
        outer.setSpacing(4)

        # header
        hdr = Qtw.QHBoxLayout()
        lbl = Qtw.QLabel('Section')
        lbl.setStyleSheet('font-weight: bold;')
        hdr.addWidget(lbl)
        hdr.addStretch()
        rm = Qtw.QPushButton('−')
        rm.setFixedSize(20, 20)
        rm.clicked.connect(lambda: on_remove(self))
        hdr.addWidget(rm)
        outer.addLayout(hdr)

        # conditions
        cond_hdr = Qtw.QHBoxLayout()
        cond_hdr.addWidget(Qtw.QLabel('Conditions'))
        cond_hdr.addStretch()
        cond_hdr.addWidget(Qtw.QLabel('combine:'))
        self._combinator = Qtw.QComboBox()
        self._combinator.addItems(['AND', 'OR'])
        cond_hdr.addWidget(self._combinator)
        outer.addLayout(cond_hdr)

        self._cond_layout = Qtw.QVBoxLayout()
        self._cond_layout.setSpacing(2)
        outer.addLayout(self._cond_layout)

        add_cond = Qtw.QPushButton('Add condition')
        add_cond.setSizePolicy(Qtw.QSizePolicy.Policy.Maximum, Qtw.QSizePolicy.Policy.Fixed)
        add_cond.clicked.connect(self._add_condition_row)
        outer.addWidget(add_cond, alignment=Qtc.Qt.AlignmentFlag.AlignRight)

        # separator
        sep = Qtw.QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: gray;")
        outer.addWidget(sep)

        # sort
        outer.addWidget(Qtw.QLabel('Sort by'))

        self._sort_layout = Qtw.QVBoxLayout()
        self._sort_layout.setSpacing(2)
        outer.addLayout(self._sort_layout)

        add_sort = Qtw.QPushButton('Add sort key')
        add_sort.setSizePolicy(Qtw.QSizePolicy.Policy.Maximum, Qtw.QSizePolicy.Policy.Fixed)
        add_sort.clicked.connect(self._add_sort_key_row)
        outer.addWidget(add_sort, alignment=Qtc.Qt.AlignmentFlag.AlignRight)

        # separator
        sep2 = Qtw.QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: gray;")
        outer.addWidget(sep2)

        # exclude previous
        self._exclude_prev = Qtw.QCheckBox('Exclude items matched by previous sections')
        self._exclude_prev.setChecked(True)
        outer.addWidget(self._exclude_prev)

    # condition rows

    def _add_condition_row(self):
        row = ConditionRow(on_remove=self._remove_condition_row)
        self._condition_rows.append(row)
        self._cond_layout.addWidget(row)

    def _remove_condition_row(self, row):
        if row in self._condition_rows:
            self._condition_rows.remove(row)
        self._cond_layout.removeWidget(row)
        row.deleteLater()

    # sort key rows

    def _add_sort_key_row(self):
        row = SortKeyRow(on_remove=self._remove_sort_key_row)
        self._sort_key_rows.append(row)
        self._sort_layout.addWidget(row)

    def _remove_sort_key_row(self, row):
        if row in self._sort_key_rows:
            self._sort_key_rows.remove(row)
        self._sort_layout.removeWidget(row)
        row.deleteLater()

    # serialisation

    def to_section(self):
        return Section(
            conditions      = [r.to_condition() for r in self._condition_rows],
            combinator      = self._combinator.currentText(),
            sort_keys       = [r.to_sort_key() for r in self._sort_key_rows],
            exclude_previous= self._exclude_prev.isChecked(),
        )

    def populate_from_dict(self, d):
        self._combinator.setCurrentText(d.get('combinator', 'AND'))
        self._exclude_prev.setChecked(d.get('exclude_previous', True))
        for c in d.get('conditions', []):
            row = ConditionRow(on_remove=self._remove_condition_row)
            row.populate_from_dict(c)
            self._condition_rows.append(row)
            self._cond_layout.addWidget(row)
        for sk in d.get('sort_keys', []):
            row = SortKeyRow(on_remove=self._remove_sort_key_row)
            row.populate_from_dict(sk)
            self._sort_key_rows.append(row)
            self._sort_layout.addWidget(row)


class ViewCreationWidget(Qtw.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent_widget   = parent
        self._section_blocks = []
        self._editing_item   = None
        self._build_ui()

    def _build_ui(self):
        layout = Qtw.QVBoxLayout(self)

        self.name_input = Qtw.QLineEdit()
        self.name_input.setPlaceholderText('View name…')
        layout.addWidget(self.name_input)

        type_row = Qtw.QHBoxLayout()
        type_row.addWidget(Qtw.QLabel('View type:'))
        self._type_grid = Qtw.QRadioButton('Album Grid')
        self._type_list = Qtw.QRadioButton('List')
        self._type_grid.setChecked(True)
        type_row.addWidget(self._type_grid)
        type_row.addWidget(self._type_list)
        type_row.addStretch()
        layout.addLayout(type_row)

        self._scroll_area = Qtw.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet("QScrollArea { background-color: white; }")
        self._scroll_container = Qtw.QWidget()
        self._scroll_container.setObjectName("sectionsContainer")
        self._scroll_container.setStyleSheet("QWidget#sectionsContainer { background-color: white; }")
        self._scroll_layout    = Qtw.QVBoxLayout(self._scroll_container)
        self._scroll_layout.setAlignment(Qtc.Qt.AlignmentFlag.AlignTop)
        self._scroll_layout.setSpacing(8)
        self._scroll_area.setWidget(self._scroll_container)
        layout.addWidget(self._scroll_area, stretch=1)

        add_btn = Qtw.QPushButton('+ Add section')
        add_btn.setMaximumWidth(120)
        add_btn.clicked.connect(self._add_section_block)
        layout.addWidget(add_btn)

        self._show_unmatched = Qtw.QCheckBox('Show items not matched by any section')
        self._show_unmatched.setChecked(True)
        layout.addWidget(self._show_unmatched)

        btns = Qtw.QHBoxLayout()
        btns.addStretch()
        ok_btn     = Qtw.QPushButton('OK')
        cancel_btn = Qtw.QPushButton('Cancel')
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self._on_cancel)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        self._add_section_block()

    # called by main_window

    def reset(self, add_example=True):
        self._editing_item = None
        self.name_input.clear()
        self._type_grid.setChecked(True)
        self._show_unmatched.setChecked(True)
        for block in self._section_blocks:
            self._scroll_layout.removeWidget(block)
            block.deleteLater()
        self._section_blocks.clear()
        if add_example:
            self._add_section_block()

    def populate(self, name, pipeline_dict, editing_item=None):
        self._editing_item = editing_item
        self.reset(add_example=False)
        self._editing_item = editing_item   # reset() clears it; restore after
        self.name_input.setText(name)
        is_list = pipeline_dict.get('view_type', 'grid') == 'list'
        self._type_list.setChecked(is_list)
        self._type_grid.setChecked(not is_list)
        self._show_unmatched.setChecked(pipeline_dict.get('show_unmatched', True))
        for section_dict in pipeline_dict.get('sections', []):
            self._add_section_block_from_dict(section_dict)
        if not self._section_blocks:
            self._add_section_block()

    # internal

    def _add_section_block(self):
        block = SectionBlock(on_remove=self._remove_section_block)
        self._section_blocks.append(block)
        self._scroll_layout.addWidget(block)

    def _add_section_block_from_dict(self, section_dict):
        block = SectionBlock(on_remove=self._remove_section_block)
        block.populate_from_dict(section_dict)
        self._section_blocks.append(block)
        self._scroll_layout.addWidget(block)

    def _remove_section_block(self, block):
        if block in self._section_blocks:
            self._section_blocks.remove(block)
        self._scroll_layout.removeWidget(block)
        block.deleteLater()

    def _on_ok(self):
        name = self.name_input.text().strip()
        if not name:
            self.name_input.setFocus()
            return
        sections  = [b.to_section() for b in self._section_blocks]
        view_type = 'list' if self._type_list.isChecked() else 'grid'
        view_dict = View(
            sections,
            show_unmatched=self._show_unmatched.isChecked(),
            view_type=view_type,
        ).to_dict()
        if self._editing_item is not None:
            item = self._editing_item
            self._editing_item = None
            self.parent_widget._apply_view_edit(item, name, view_dict)
        else:
            self.parent_widget._create_new_view(name, view_dict)

    def _on_cancel(self):
        self.parent_widget._on_view_creation_cancelled()
