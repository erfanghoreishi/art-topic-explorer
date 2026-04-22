from backend.src.normalizer import normalize_object_record


def test_normalize_prefers_period_then_century():
    record = {
        "id": 10,
        "title": "Work",
        "classification": "Paintings",
        "period": "Edo period",
        "century": "19th century",
        "people": [{"displayname": "A"}, {"name": "A"}, {"name": "B"}],
        "primaryimageurl": "https://img",
        "imagepermissionlevel": 0,
    }
    out = normalize_object_record(record)
    assert out is not None
    assert out["era"] == "Edo period"
    assert out["eraSource"] == "period"
    assert out["people"] == ["A", "B"]


def test_normalize_falls_back_to_century_then_unknown():
    from_century = normalize_object_record(
        {
            "objectid": "11",
            "period": "  ",
            "century": "20th century",
            "primaryimageurl": "https://img",
            "imagepermissionlevel": 1,
        }
    )
    assert from_century is not None
    assert from_century["era"] == "20th century"
    assert from_century["eraSource"] == "century"

    unknown = normalize_object_record(
        {
            "id": 12,
            "period": None,
            "century": "",
            "primaryimageurl": "https://img",
            "imagepermissionlevel": 0,
        }
    )
    assert unknown is not None
    assert unknown["era"] == "Unknown Era"
    assert unknown["eraSource"] == "unknown"


def test_normalize_skips_unusable_image_records():
    no_image = normalize_object_record({"id": 1, "imagepermissionlevel": 0})
    blocked = normalize_object_record(
        {"id": 2, "primaryimageurl": "https://img", "imagepermissionlevel": 2}
    )
    assert no_image is None
    assert blocked is None

