import pytest


from cairn.core.preview import _parse_bulk_selection


def test_parse_bulk_selection_commas():
    assert _parse_bulk_selection("1,2,3", max_index=5) == [1, 2, 3]
    assert _parse_bulk_selection("1, 2,3", max_index=5) == [1, 2, 3]
    assert _parse_bulk_selection("3,1,2,2", max_index=5) == [1, 2, 3]


def test_parse_bulk_selection_ranges():
    assert _parse_bulk_selection("1-4", max_index=10) == [1, 2, 3, 4]
    assert _parse_bulk_selection("2-2", max_index=10) == [2]
    assert _parse_bulk_selection("1-3,5", max_index=10) == [1, 2, 3, 5]


def test_parse_bulk_selection_all():
    assert _parse_bulk_selection("all", max_index=3) == [1, 2, 3]
    assert _parse_bulk_selection("*", max_index=2) == [1, 2]


def test_parse_bulk_selection_out_of_range():
    with pytest.raises(ValueError):
        _parse_bulk_selection("0", max_index=3)
    with pytest.raises(ValueError):
        _parse_bulk_selection("4", max_index=3)
    with pytest.raises(ValueError):
        _parse_bulk_selection("1,4", max_index=3)


def test_parse_bulk_selection_invalid_syntax():
    with pytest.raises(ValueError):
        _parse_bulk_selection("", max_index=3)
    with pytest.raises(ValueError):
        _parse_bulk_selection("  ", max_index=3)
    with pytest.raises(ValueError):
        _parse_bulk_selection("nope", max_index=3)
    with pytest.raises(ValueError):
        _parse_bulk_selection("1-", max_index=3)
    with pytest.raises(ValueError):
        _parse_bulk_selection("-3", max_index=3)
    with pytest.raises(ValueError):
        _parse_bulk_selection("4-1", max_index=10)
