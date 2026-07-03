from datetime import date, datetime
from typing import Optional, Tuple

from config import DATE_FORMAT, MAX_NAME_LENGTH, MIN_NAME_LENGTH, TIME_FORMAT


MASSAGE_TYPE_OPTIONS = (
    ("massage_general", "🌿 Общий массаж", "Общий массаж"),
    ("massage_medical", "🦴 Лечебный массаж", "Лечебный массаж"),
    ("massage_back", "💪 Массаж спины", "Массаж спины"),
    ("massage_limbs", "🦵 Массаж конечностей", "Массаж конечностей"),
    ("massage_relax", "🏥 Расслабляющий массаж", "Расслабляющий массаж"),
)

MASSAGE_TYPES = {
    callback_data: stored_name
    for callback_data, _, stored_name in MASSAGE_TYPE_OPTIONS
}


def normalize_name(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def validate_name(value: str) -> bool:
    normalized = normalize_name(value)
    return MIN_NAME_LENGTH <= len(normalized) <= MAX_NAME_LENGTH


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), DATE_FORMAT).date()


def validate_birth_date(value: str, today: Optional[date] = None) -> Tuple[bool, Optional[str]]:
    if today is None:
        today = date.today()

    try:
        birth_date = parse_date(value)
    except (AttributeError, TypeError, ValueError):
        return False, "invalid_format"

    if birth_date > today:
        return False, "future"

    age_years = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    if age_years > 18:
        return False, "too_old"

    return True, None


def validate_booking_date(
    value: str,
    today: Optional[date] = None,
    allow_past: bool = False,
) -> Tuple[bool, Optional[str]]:
    if today is None:
        today = date.today()

    try:
        session_date = parse_date(value)
    except (AttributeError, TypeError, ValueError):
        return False, "invalid_format"

    if not allow_past and session_date < today:
        return False, "past"

    return True, None


def normalize_time(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().replace(".", ":")


def validate_time(value: str) -> Tuple[bool, Optional[str]]:
    normalized = normalize_time(value)
    try:
        datetime.strptime(normalized, TIME_FORMAT)
    except ValueError:
        return False, None
    return True, normalized
