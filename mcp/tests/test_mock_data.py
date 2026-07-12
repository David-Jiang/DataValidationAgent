from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

import pytest

from conftest import (
    boolean_field,
    datetime_field,
    float_field,
    int_field,
    spec_document,
    string_field,
)
from core import mock_data
from core.mock_data import generate_mock_csv
from core.models import DType, FieldSpec


def make_spec(field: dict) -> FieldSpec:
    return FieldSpec(**spec_document(field))


def rows_from(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_text)))


def values_from(csv_text: str, column: str) -> list[str]:
    return [row[column] for row in rows_from(csv_text)]


def test_default_row_count_and_requested_count() -> None:
    spec = make_spec(boolean_field())
    assert len(rows_from(generate_mock_csv(spec))) == 100
    assert len(rows_from(generate_mock_csv(spec, 10_001))) == 10_001


@pytest.mark.parametrize("row_count", [0, -1])
def test_row_count_must_be_positive(row_count: int) -> None:
    with pytest.raises(ValueError, match="row_count 必須是正整數"):
        generate_mock_csv(make_spec(boolean_field()), row_count)


def test_csv_preserves_field_order_and_row_count(all_types_spec: FieldSpec) -> None:
    rows = rows_from(generate_mock_csv(all_types_spec, 3))
    assert len(rows) == 3
    assert list(rows[0]) == ["code", "quantity", "amount", "created_at", "active"]


def test_nullable_fields_still_generate_insertable_non_null_values() -> None:
    spec = make_spec(string_field(nullable=True))
    assert all(value != "" for value in values_from(generate_mock_csv(spec, 20), "code"))


def test_string_pattern_unique_and_invalid_tokens_are_honored() -> None:
    spec = make_spec(
        string_field(
            unique=True,
            pattern=r"[A-Z]{3}[0-9]{3}",
            invalid_value_tokens=["AAA000"],
        )
    )
    values = values_from(generate_mock_csv(spec, 50), "code")
    assert len(set(values)) == 50
    assert "AAA000" not in values
    assert all(re.fullmatch(r"[A-Z]{3}[0-9]{3}", value) for value in values)


def test_unique_string_without_pattern_stays_unique() -> None:
    values = values_from(generate_mock_csv(make_spec(string_field(unique=True)), 50), "code")
    assert len(set(values)) == 50


def test_enum_values_are_used_without_modification() -> None:
    allowed = {"new", "done"}
    spec = make_spec(string_field(enum_values=sorted(allowed)))
    assert set(values_from(generate_mock_csv(spec, 50), "code")) <= allowed


def test_enum_is_filtered_by_pattern_empty_and_invalid_rules() -> None:
    spec = make_spec(
        string_field(
            enum_values=["", "bad", "AAA", "BBB"],
            pattern=r"[A-Z]{3}",
            invalid_value_tokens=["BBB"],
        )
    )
    assert set(values_from(generate_mock_csv(spec, 10), "code")) == {"AAA"}


def test_enum_with_no_legal_candidate_fails() -> None:
    spec = make_spec(string_field(enum_values=["bad"], pattern=r"[A-Z]{3}"))
    with pytest.raises(ValueError, match="enum_values 沒有"):
        generate_mock_csv(spec, 1)


def test_unique_enum_capacity_is_checked() -> None:
    spec = make_spec(string_field(unique=True, enum_values=["new", "done"]))
    with pytest.raises(ValueError, match="unique enum 只有 2 個可用值"):
        generate_mock_csv(spec, 3)


def test_invalid_regular_expression_fails_clearly() -> None:
    spec = make_spec(string_field(pattern="["))
    with pytest.raises(ValueError, match="pattern 不是合法"):
        generate_mock_csv(spec, 1)


def test_retry_exhaustion_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    field = make_spec(string_field()).fields[0]
    monkeypatch.setattr(mock_data, "_MAX_ATTEMPTS_PER_VALUE", 2)
    with pytest.raises(ValueError, match="在 2 次嘗試內"):
        mock_data._generate_with_retry(field, 1, lambda: "bad", lambda _: False)


def test_retry_skips_duplicate_when_string_must_be_unique() -> None:
    field = make_spec(string_field(unique=True)).fields[0]
    candidates = iter(["first", "first", "second"])
    assert mock_data._generate_with_retry(field, 2, lambda: next(candidates), lambda _: True) == [
        "first",
        "second",
    ]


@pytest.mark.parametrize(
    ("field", "minimum", "maximum"),
    [
        (int_field(min_value=1, max_value=5), 1, 5),
        (int_field(min_value=5, max_value=None), 5, 10005),
        (int_field(min_value=None, max_value=-5), -10005, -5),
        (int_field(), 0, 10000),
    ],
)
def test_integer_bounds(field: dict, minimum: int, maximum: int) -> None:
    values = [int(value) for value in values_from(generate_mock_csv(make_spec(field), 100), field["name"])]
    assert all(minimum <= value <= maximum for value in values)


def test_integer_invalid_token_is_never_generated() -> None:
    spec = make_spec(int_field(min_value=1, max_value=2, invalid_value_tokens=["1"]))
    assert set(values_from(generate_mock_csv(spec, 20), "quantity")) == {"2"}


def test_integer_range_fully_excluded_fails() -> None:
    spec = make_spec(int_field(min_value=1, max_value=1, invalid_value_tokens=["1"]))
    with pytest.raises(ValueError, match="沒有避開 invalid_value_tokens"):
        generate_mock_csv(spec, 1)


@pytest.mark.parametrize(
    ("field", "minimum", "maximum"),
    [
        (float_field(min_value=-1.5, max_value=2.5), -1.5, 2.5),
        (float_field(min_value=5, max_value=None), 5, 10005),
        (float_field(min_value=None, max_value=-5), -10005, -5),
        (float_field(), 0, 10000),
    ],
)
def test_float_bounds(field: dict, minimum: float, maximum: float) -> None:
    values = [float(value) for value in values_from(generate_mock_csv(make_spec(field), 100), field["name"])]
    assert all(minimum <= value <= maximum for value in values)


def test_float_invalid_token_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    values = iter([1.0, 2.0])
    monkeypatch.setattr(mock_data.random, "uniform", lambda _lo, _hi: next(values))
    spec = make_spec(float_field(min_value=1, max_value=2, invalid_value_tokens=["1.0"]))
    assert values_from(generate_mock_csv(spec, 1), "amount") == ["2.0"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024-01-01T00:00:00Z", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ("2024-01-01T08:00:00+08:00", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ("2024-01-01T00:00:00", datetime(2024, 1, 1, tzinfo=timezone.utc)),
    ],
)
def test_datetime_bound_parsing(raw: str, expected: datetime) -> None:
    field = make_spec(datetime_field()).fields[0]
    assert mock_data._parse_datetime_bound(field, raw, "bound") == expected


def test_invalid_datetime_bound_fails() -> None:
    spec = make_spec(datetime_field(datetime_after="not-a-date"))
    with pytest.raises(ValueError, match="必須是 ISO-8601"):
        generate_mock_csv(spec, 1)


def test_reversed_datetime_bounds_fail() -> None:
    spec = make_spec(
        datetime_field(
            datetime_after="2024-01-02T00:00:00Z",
            datetime_before="2024-01-01T00:00:00Z",
        )
    )
    with pytest.raises(ValueError, match="datetime_after 不可晚於"):
        generate_mock_csv(spec, 1)


@pytest.mark.parametrize(
    "field",
    [
        datetime_field(),
        datetime_field(datetime_after="2024-01-01T00:00:00Z"),
        datetime_field(datetime_before="2024-01-01T00:00:00Z"),
    ],
)
def test_open_datetime_bounds_generate_values(field: dict) -> None:
    assert len(values_from(generate_mock_csv(make_spec(field), 3), "created_at")) == 3


def test_datetime_format_and_equal_bounds() -> None:
    spec = make_spec(
        datetime_field(
            datetime_after="2024-01-01T00:00:00Z",
            datetime_before="2024-01-01T00:00:00Z",
            expected_datetime_format="%Y/%m/%d",
        )
    )
    assert values_from(generate_mock_csv(spec, 3), "created_at") == ["2024/01/01"] * 3


def test_boolean_respects_invalid_tokens() -> None:
    spec = make_spec(boolean_field(invalid_value_tokens=["True"]))
    assert set(values_from(generate_mock_csv(spec, 20), "active")) == {"False"}


def test_boolean_fails_if_all_values_are_invalid() -> None:
    spec = make_spec(boolean_field(invalid_value_tokens=["True", "False"]))
    with pytest.raises(ValueError, match="True 與 False 都被"):
        generate_mock_csv(spec, 1)


def test_unknown_dtype_dispatch_fails() -> None:
    field = make_spec(boolean_field()).fields[0].model_copy(update={"dtype": "unknown"})
    with pytest.raises(ValueError, match="不支援的 dtype"):
        mock_data._generate_column(field, 1)
