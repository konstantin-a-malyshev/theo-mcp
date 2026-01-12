import pytest

from theo_mcp_server.validation import normalize_label, normalize_edge_label, validate_properties


def test_normalize_label():
    assert normalize_label("book") == "Book"
    assert normalize_label("Book") == "Book"
    assert normalize_label("notiongroup") == "notionGroup"


def test_normalize_edge_label_case_insensitive():
    assert normalize_edge_label("refersto") == "refersTo"


def test_validate_properties_required():
    props = validate_properties("notion", {"id": 1, "caption": "x"})
    assert props["id"] == 1


def test_validate_properties_reject_unknown():
    with pytest.raises(ValueError):
        validate_properties("person", {"id": 1, "caption": "x", "nope": 123})
