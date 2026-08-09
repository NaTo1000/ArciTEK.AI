"""Shared, bounded validation helpers for the robotics engineering-plan MVP.

Every value that crosses the trust boundary (HTTP request bodies, in-process
API calls originating from untrusted callers) is routed through these
helpers. The goal is defense in depth: reject anything oversized, malformed,
or of the wrong type before it reaches the domain model.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

# Bounds are intentionally conservative for an MVP handling small/medium
# engineering projects in memory. They are not meant to model every possible
# real-world design, only to keep the service safe and predictable.
MAX_ID_LENGTH = 80
MAX_NAME_LENGTH = 160
MAX_SHORT_STRING = 300
MAX_TEXT_LENGTH = 4_000
MAX_LIST_ITEMS = 200
MAX_DICT_KEYS = 100
MAX_NUMBER_MAGNITUDE = 1_000_000.0

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,79}$")


class ValidationError(ValueError):
    """Raised when caller-supplied data fails strict, bounded validation."""


def validate_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.match(value):
        raise ValidationError(
            f"{field} must be a 1-80 character identifier "
            "(letters, digits, '_', '-', '.')"
        )
    return value


def validate_string(
    value: Any,
    field: str,
    *,
    max_len: int = MAX_SHORT_STRING,
    required: bool = True,
    allow_empty: bool = False,
    default: str = "",
) -> str:
    if value is None:
        if required:
            raise ValidationError(f"{field} is required")
        return default
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise ValidationError(f"{field} must not be empty")
    if len(value) > max_len:
        raise ValidationError(f"{field} must be at most {max_len} characters")
    return value


def validate_number(
    value: Any,
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    required: bool = True,
    default: float | None = None,
) -> float | None:
    if value is None:
        if required:
            raise ValidationError(f"{field} is required")
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be a finite number")
    if abs(number) > MAX_NUMBER_MAGNITUDE:
        raise ValidationError(f"{field} magnitude is out of bounds")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} must be <= {maximum}")
    return number


def validate_list(value: Any, field: str, *, max_items: int = MAX_LIST_ITEMS) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be a list")
    if len(value) > max_items:
        raise ValidationError(f"{field} must contain at most {max_items} items")
    return value


def validate_dict(value: Any, field: str, *, max_keys: int = MAX_DICT_KEYS) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be an object")
    if len(value) > max_keys:
        raise ValidationError(f"{field} must contain at most {max_keys} keys")
    return value


def validate_vector3(value: Any, field: str, *, required: bool = False) -> list[float]:
    if value is None:
        if required:
            raise ValidationError(f"{field} is required")
        return [0.0, 0.0, 0.0]
    items = validate_list(value, field, max_items=3)
    if len(items) != 3:
        raise ValidationError(f"{field} must have exactly 3 components [x, y, z]")
    return [
        validate_number(item, f"{field}[{index}]", minimum=-1e5, maximum=1e5)
        for index, item in enumerate(items)
    ]


def bounded_iter(items: Iterable, field: str, *, max_items: int = MAX_LIST_ITEMS):
    count = 0
    for item in items:
        count += 1
        if count > max_items:
            raise ValidationError(f"{field} must contain at most {max_items} items")
        yield item
