import pytest

from theo_mcp_server.validation import normalize_label, normalize_edge_label, validate_and_fix_properties


def test_normalize_label():
    assert normalize_label("scholarlyWork") == "scholarlyWork"
    assert normalize_label("scholarlywork") == "scholarlyWork"
    assert normalize_label("notiongroup") == "notionGroup"


def test_normalize_edge_label_case_insensitive():
    assert normalize_edge_label("refersto") == "refersTo"


def test_validate_properties_required():
    props = validate_and_fix_properties("notion", {"caption": "x"})
    assert props["caption"] == "x"


def test_validate_properties_reject_unknown():
    with pytest.raises(ValueError):
        validate_and_fix_properties("person", {"caption": "x", "nope": 123})


def test_normalize_label_reception_types():
    assert normalize_label("receptionwork") == "receptionWork"
    assert normalize_label("receptionPassage") == "receptionPassage"


def test_reception_passage_coerces_ints():
    props = validate_and_fix_properties(
        "receptionPassage",
        {"caption": "x", "pageStart": "86", "lineEnd": "26"},
    )
    assert props["pageStart"] == 86
    assert props["lineEnd"] == 26


def test_reception_work_parses_boolean_strings():
    assert validate_and_fix_properties(
        "receptionWork", {"caption": "x", "fragmentary": "False"}
    )["fragmentary"] is False
    assert validate_and_fix_properties(
        "receptionWork", {"caption": "x", "fragmentary": "True"}
    )["fragmentary"] is True
    with pytest.raises(ValueError):
        validate_and_fix_properties("receptionWork", {"caption": "x", "fragmentary": "maybe"})


def test_reception_passage_rejects_unknown_enum_value():
    validate_and_fix_properties(
        "receptionPassage", {"caption": "x", "ctsUrnStatus": "approximate"}
    )
    with pytest.raises(ValueError):
        validate_and_fix_properties(
            "receptionPassage", {"caption": "x", "ctsUrnStatus": "probably"}
        )
