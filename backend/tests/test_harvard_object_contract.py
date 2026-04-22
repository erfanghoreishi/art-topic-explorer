from backend.src.harvard_object_contract import (
    OBJECT_ENDPOINT,
    OBJECT_FIELDS,
    OBJECT_HAS_IMAGE,
    OBJECT_PAGE_SIZE_MAX,
    object_fields_param,
)


def test_contract_constants_are_locked():
    assert OBJECT_ENDPOINT == "/object"
    assert OBJECT_HAS_IMAGE == 1
    assert OBJECT_PAGE_SIZE_MAX == 100
    assert "period" in OBJECT_FIELDS
    assert "century" in OBJECT_FIELDS
    assert "primaryimageurl" in OBJECT_FIELDS


def test_fields_param_matches_tuple_order():
    assert object_fields_param() == ",".join(OBJECT_FIELDS)

