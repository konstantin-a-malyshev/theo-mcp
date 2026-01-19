import pytest

from theo_mcp_server.validation import normalize_label, normalize_edge_label, validate_and_fix_properties


def test_normalize_label():
    assert normalize_label("book") == "book"
    assert normalize_label("Book") == "book"
    assert normalize_label("notiongroup") == "notionGroup"


def test_normalize_edge_label_case_insensitive():
    assert normalize_edge_label("refersto") == "refersTo"


def test_validate_properties_required():
    props = validate_and_fix_properties("notion", {"caption": "x"})
    assert props["caption"] == "x"


def test_validate_properties_reject_unknown():
    with pytest.raises(ValueError):
        validate_and_fix_properties("person", {"caption": "x", "nope": 123})
