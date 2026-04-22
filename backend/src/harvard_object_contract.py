"""Locked API contract for the MVP: only Harvard `/object` is used."""

from __future__ import annotations

from typing import Final


OBJECT_ENDPOINT: Final[str] = "/object"
OBJECT_HAS_IMAGE: Final[int] = 1
OBJECT_PAGE_SIZE_MAX: Final[int] = 100

# Locked field contract for day-one MVP.
# These fields are intentionally sufficient for both browse and detail UI.
OBJECT_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "objectid",
    "title",
    "classification",
    "period",
    "century",
    "dated",
    "culture",
    "medium",
    "people",
    "primaryimageurl",
    "url",
    "imagepermissionlevel",
    "lastupdate",
)


def object_fields_param() -> str:
    """Return comma-separated fields value for Harvard API query."""
    return ",".join(OBJECT_FIELDS)

