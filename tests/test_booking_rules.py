"""
Тесты для booking_rules.py — валидация имён, дат, времени.
Запуск: pytest tests/test_booking_rules.py -v
"""
import pytest
from datetime import date, timedelta

from booking_rules import (
    MASSAGE_TYPES,
    MASSAGE_TYPE_OPTIONS,
    normalize_name,
    validate_name,
    parse_date,
    validate_birth_date,
    validate_booking_date,
    normalize_time,
    validate_time,
)


class TestNormalizeName:
    def test_normalize_removes_extra_spaces(self):
        assert normalize_name("  Иван   Петров  ") == "Иван Петров"

    def test_normalize_handles_tabs_and_newlines(self):
        assert normalize_name("Иван\t\nПетров") == "Иван Петров"

    def test_normalize_empty_string(self):
        assert normalize_name("") == ""

    def test_normalize_none(self):
        assert normalize_name(None) == ""


class TestValidateName:
    def test_valid_name(self):
        assert validate_name("Иван Петров") is True

    def test_valid_name_min_length(self):
        assert validate_name("А Б") is True  # после normalize = "А Б" (3 символа)

    def test_invalid_too_short(self):
        assert validate_name("А") is False

    def test_invalid_too_long(self):
        long_name = "А" * 101
        assert validate_name(long_name) is False

    def test_invalid_none(self):
        assert validate_name(None) is False

    def test_invalid_number(self):
        assert validate_name(123) is False


class TestParseDate:
    def test_valid_date(self):
        result = parse_date("25.12.2024")
        assert result == date(2024, 12, 25)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            parse_date("2024-12-25")

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError):
            parse_date("32.13.2024")


class TestValidateBirthDate:
    def test_valid_birth_date(self):
        is_valid, error = validate_birth_date("15.03.2020")
        assert is_valid is True
        assert error is None

    def test_invalid_format(self):
        is_valid, error = validate_birth_date("2020-03-15")
        assert is_valid is False
        assert error == "invalid_format"

    def test_future_date(self):
        future = (date.today() + timedelta(days=1)).strftime("%d.%m.%Y")
        is_valid, error = validate_birth_date(future)
        assert is_valid is False
        assert error == "future"

    def test_too_old_over_18(self):
        # 19 лет назад (учитываем високосные годы)
        today = date.today()
        old_date = date(today.year - 19, today.month, today.day).strftime("%d.%m.%Y")
        is_valid, error = validate_birth_date(old_date)
        assert is_valid is False
        assert error == "too_old"


class TestValidateBookingDate:
    def test_valid_future_date(self):
        future = (date.today() + timedelta(days=10)).strftime("%d.%m.%Y")
        is_valid, error = validate_booking_date(future)
        assert is_valid is True
        assert error is None

    def test_valid_today(self):
        today = date.today().strftime("%d.%m.%Y")
        is_valid, error = validate_booking_date(today)
        assert is_valid is True
        assert error is None

    def test_past_date_not_allowed_by_default(self):
        past = (date.today() - timedelta(days=1)).strftime("%d.%m.%Y")
        is_valid, error = validate_booking_date(past)
        assert is_valid is False
        assert error == "past"

    def test_past_date_allowed_with_flag(self):
        past = (date.today() - timedelta(days=1)).strftime("%d.%m.%Y")
        is_valid, error = validate_booking_date(past, allow_past=True)
        assert is_valid is True
        assert error is None

    def test_invalid_format(self):
        is_valid, error = validate_booking_date("2024-12-25")
        assert is_valid is False
        assert error == "invalid_format"


class TestNormalizeTime:
    def test_normalize_with_colon(self):
        assert normalize_time("10:30") == "10:30"

    def test_normalize_with_dot(self):
        assert normalize_time("10.30") == "10:30"

    def test_normalize_strips_spaces(self):
        assert normalize_time(" 10:30 ") == "10:30"

    def test_normalize_none(self):
        assert normalize_time(None) == ""


class TestValidateTime:
    def test_valid_time_colon(self):
        is_valid, normalized = validate_time("14:30")
        assert is_valid is True
        assert normalized == "14:30"

    def test_valid_time_dot(self):
        is_valid, normalized = validate_time("14.30")
        assert is_valid is True
        assert normalized == "14:30"

    def test_invalid_hour_too_large(self):
        is_valid, normalized = validate_time("25:00")
        assert is_valid is False
        assert normalized is None

    def test_invalid_minute_too_large(self):
        is_valid, normalized = validate_time("14:60")
        assert is_valid is False
        assert normalized is None

    def test_invalid_format(self):
        is_valid, normalized = validate_time("14-30")
        assert is_valid is False
        assert normalized is None


class TestMassageTypes:
    def test_massage_types_dict_structure(self):
        assert isinstance(MASSAGE_TYPES, dict)
        assert len(MASSAGE_TYPES) == len(MASSAGE_TYPE_OPTIONS)

    def test_all_callback_data_unique(self):
        callback_datas = [opt[0] for opt in MASSAGE_TYPE_OPTIONS]
        assert len(callback_datas) == len(set(callback_datas))

    def test_massage_types_values_match_options(self):
        for callback_data, _, stored_name in MASSAGE_TYPE_OPTIONS:
            assert MASSAGE_TYPES[callback_data] == stored_name