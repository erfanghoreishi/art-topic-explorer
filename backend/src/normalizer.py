"""Normalization logic for Harvard `/object` records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


JsonDict = Dict[str, Any]


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _derive_era(period: Optional[str], century: Optional[str]) -> Tuple[str, str]:
    clean_period = _clean_text(period)
    clean_century = _clean_text(century)
    if clean_period:
        return clean_period, "period"
    if clean_century:
        return clean_century, "century"
    return "Unknown Era", "unknown"


def _extract_people_names(people: Any) -> List[str]:
    if not isinstance(people, list):
        return []

    names: List[str] = []
    seen = set()
    for person in people:
        if not isinstance(person, dict):
            continue
        name = _clean_text(person.get("displayname")) or _clean_text(person.get("name"))
        if not name:
            continue
        if name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def _resolve_id(record: JsonDict) -> Optional[int]:
    for key in ("id", "objectid"):
        value = record.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def normalize_object_record(record: JsonDict) -> Optional[JsonDict]:
    """
    Normalize a Harvard object record into the MVP internal schema.

    Returns None when record is unusable for image-first browsing.
    """
    obj_id = _resolve_id(record)
    if obj_id is None:
        return None

    image_url = _clean_text(record.get("primaryimageurl"))
    if not image_url:
        return None

    # Respect Harvard image permission restrictions.
    # level 2 = do not display images (exclude record from image-first MVP).
    permission = record.get("imagepermissionlevel")
    if permission == 2:
        return None

    classification = _clean_text(record.get("classification")) or "Unknown Classification"
    period = _clean_text(record.get("period"))
    century = _clean_text(record.get("century"))
    era, era_source = _derive_era(period, century)

    normalized: JsonDict = {
        "id": obj_id,
        "title": _clean_text(record.get("title")) or f"Untitled ({obj_id})",
        "classification": classification,
        "era": era,
        "eraSource": era_source,
        "period": period,
        "century": century,
        "dated": _clean_text(record.get("dated")),
        "culture": _clean_text(record.get("culture")),
        "medium": _clean_text(record.get("medium")),
        "people": _extract_people_names(record.get("people")),
        "imageUrl": image_url,
        "museumUrl": _clean_text(record.get("url")),
        "lastUpdate": _clean_text(record.get("lastupdate")),
    }
    return normalized

