import re
import rapidfuzz.fuzz


class Condition:
    OPERATORS = ['contains', 'equals', 'regex', 'range', 'fuzzy']

    def __init__(self, field, op, negated=False, **params):
        self.field   = field
        self.op      = op
        self.negated = negated
        self.params  = params
        self._check  = self._compile(op, params)

    @staticmethod
    def _compile(op, p):
        if op == 'contains':
            needle = str(p.get('value', '')).casefold()
            return lambda val: needle in val.casefold()
        if op == 'equals':
            target = str(p.get('value', ''))
            return lambda val: val == target
        if op == 'regex':
            try:
                pattern = re.compile(p.get('pattern', ''), p.get('flags', 0))
            except re.error:
                return lambda val: False
            return lambda val: bool(pattern.search(val))
        if op == 'range':
            lo, hi = p.get('min'), p.get('max')
            def check_range(val):
                try:
                    v = float(val)
                except (ValueError, TypeError):
                    v = val
                if lo is not None and v < lo:
                    return False
                if hi is not None and v > hi:
                    return False
                return True
            return check_range
        if op == 'fuzzy':
            query     = str(p.get('query', ''))
            threshold = p.get('threshold', 80)
            return lambda val: rapidfuzz.fuzz.WRatio(val, query) >= threshold
        return lambda val: True

    def test_conditional(self, item):
        result = self._check(str(item.get(self.field, '') or ''))
        return not result if self.negated else result

    def to_dict(self):
        return {'field': self.field, 'op': self.op, 'negated': self.negated, **self.params}

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        field   = d.pop('field')
        op      = d.pop('op')
        negated = d.pop('negated', False)
        return cls(field, op, negated=negated, **d)


class SortFilter:
    # Sort by one or more named fields

    def __init__(self, *keys, reverse=False, key=None):
        self.keys = list(keys)
        self.reverse = reverse
        self._custom_key = key

    def apply(self, tracks):
        key_fn = self._custom_key if self._custom_key else self._make_key()
        return sorted(tracks, key=key_fn, reverse=self.reverse)

    def _make_key(self):
        fields = self.keys
        def key_fn(track):
            parts = []
            for field in fields:
                val = track.get(field)
                if val is None:
                    parts.append((1, '', 0.0))
                elif isinstance(val, (int, float)):
                    parts.append((0, '', float(val)))
                else:
                    parts.append((0, str(val).casefold(), 0.0))
            return parts
        return key_fn

    def to_dict(self):
        if self._custom_key:
            raise TypeError("SortFilter with a custom key function cannot be serialized")
        return {'type': 'SortFilter', 'keys': self.keys, 'reverse': self.reverse}

    @classmethod
    def from_dict(cls, d):
        return cls(*d['keys'], reverse=d.get('reverse', False))


class Section:
    # Each section applies its own conditional filtering and sorting

    class _ReverseKey:
        __slots__ = ('val',)
        def __init__(self, val): self.val = val
        def __lt__(self, o): return self.val > o.val
        def __le__(self, o): return self.val >= o.val
        def __eq__(self, o): return self.val == o.val
        def __ge__(self, o): return self.val <= o.val
        def __gt__(self, o): return self.val < o.val
        def __ne__(self, o): return self.val != o.val

    @staticmethod
    def _field_sort_key(item, field):
        val = item.get(field)
        if val is None or val == '':
            return (1, '', 0.0)
        if isinstance(val, (int, float)):
            return (0, '', float(val))
        return (0, str(val).casefold(), 0.0)

    @staticmethod
    def item_id(item):
        return (item.get('album_title', ''), item.get('artist', ''))

    def __init__(self, conditions=None, combinator='AND', sort_keys=None, exclude_previous=True):
        self.conditions       = conditions or []
        self.combinator       = combinator
        self.sort_keys        = sort_keys or []    # list of {"field": str, "reverse": bool}
        self.exclude_previous = exclude_previous

    def _make_sort_key(self):
        def key(item):
            parts = []
            for sk in self.sort_keys:
                raw = self._field_sort_key(item, sk['field'])
                if sk.get('reverse', False):
                    parts.append(tuple(self._ReverseKey(v) for v in raw))
                else:
                    parts.append(raw)
            return tuple(parts)
        return key

    def apply(self, items, exclude_ids=None):
        if self.conditions:
            combine = all if self.combinator == 'AND' else any
            filtered = [x for x in items if combine(c.test_conditional(x) for c in self.conditions)]
        else:
            filtered = list(items)

        if exclude_ids is not None:
            filtered = [x for x in filtered if self.item_id(x) not in exclude_ids]

        if self.sort_keys:
            filtered = sorted(filtered, key=self._make_sort_key())

        return filtered

    def to_dict(self):
        return {
            'combinator':       self.combinator,
            'exclude_previous': self.exclude_previous,
            'conditions':       [c.to_dict() for c in self.conditions],
            'sort_keys':        list(self.sort_keys),
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            conditions      = [Condition.from_dict(c) for c in d.get('conditions', [])],
            combinator      = d.get('combinator', 'AND'),
            sort_keys       = d.get('sort_keys', []),
            exclude_previous= d.get('exclude_previous', True),
        )


class View:
    # A sequence of sections

    def __init__(self, sections=None, show_unmatched=True, view_type='grid'):
        self.sections       = sections or []
        self.show_unmatched = show_unmatched
        self.view_type      = view_type   # 'grid' | 'list'

    def apply(self, items):
        seen   = set()
        result = []
        for section in self.sections:
            out = section.apply(
                items,
                exclude_ids=seen if section.exclude_previous else None,
            )
            seen.update(Section.item_id(x) for x in out)
            result.extend(out)

        if self.show_unmatched:
            for item in items:
                if Section.item_id(item) not in seen:
                    result.append(item)

        return result

    def to_dict(self):
        return {
            'type':           'View',
            'view_type':      self.view_type,
            'show_unmatched': self.show_unmatched,
            'sections':       [s.to_dict() for s in self.sections],
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            sections       = [Section.from_dict(s) for s in d.get('sections', [])],
            show_unmatched = d.get('show_unmatched', True),
            view_type      = d.get('view_type', 'grid'),
        )


def filter_from_dict(d):
    filter_type = d.get('type')
    if filter_type == 'SortFilter':
        return SortFilter.from_dict(d)
    if filter_type == 'View':
        return View.from_dict(d)
    raise ValueError(f"Unknown filter type: {filter_type!r}")
