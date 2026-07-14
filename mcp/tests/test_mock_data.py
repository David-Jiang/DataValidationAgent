from __future__ import annotations

import csv
import inspect
import io

import pytest

from conftest import (
    boolean_field,
    datetime_field,
    float_field,
    int_field,
    spec_document,
    string_field,
)
from core.mock_data import (
    MAX_ROW_COUNT,
    ViolationCase,
    build_violation_cases,
    generate_mock_csv,
)
from core.models import FieldSpec


def make_spec(*fields: dict) -> FieldSpec:
    return FieldSpec(**spec_document(*fields))


def rows_from(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_text)))


def csv_value(case: ViolationCase) -> str:
    return "" if case.value is None else str(case.value)


def test_generator_has_no_user_controlled_row_count() -> None:
    assert list(inspect.signature(generate_mock_csv).parameters) == ["field_spec"]


def test_default_is_100_rows_and_preserves_field_order() -> None:
    spec = make_spec(string_field("code"), int_field("quantity"))
    rows = rows_from(generate_mock_csv(spec))
    assert len(rows) == 100
    assert list(rows[0]) == ["code", "quantity"]


def test_every_row_contains_an_injected_violation() -> None:
    spec = make_spec(
        string_field(unique=True, enum_values=["A", "B"], pattern=r"[A-Z]"),
        int_field(min_value=1, max_value=10),
        float_field(min_value=-1.5, max_value=2.5),
        datetime_field(
            datetime_after="2024-01-01T00:00:00Z",
            datetime_before="2024-01-02T00:00:00Z",
            expected_datetime_format="%Y-%m-%dT%H:%M:%SZ",
        ),
        boolean_field(),
    )
    cases = build_violation_cases(spec)
    negative_values = {
        (case.field_name, csv_value(case))
        for case in cases
    }

    for row in rows_from(generate_mock_csv(spec)):
        assert any((field_name, row[field_name]) in negative_values for field_name in row)


def test_each_rule_case_is_covered_when_under_limit() -> None:
    spec = make_spec(
        string_field(unique=True, enum_values=["A", "B"], pattern=r"[A-Z]"),
        int_field(min_value=1, max_value=10),
        datetime_field(
            datetime_after="2024-01-01T00:00:00Z",
            datetime_before="2024-01-02T00:00:00Z",
            expected_datetime_format="%Y-%m-%dT%H:%M:%SZ",
        ),
    )
    rows = rows_from(generate_mock_csv(spec))
    for case in build_violation_cases(spec):
        assert any(row[case.field_name] == csv_value(case) for row in rows)


def test_unique_rule_gets_at_least_two_duplicate_rows() -> None:
    spec = make_spec(string_field(unique=True, invalid_value_tokens=[]))
    values = [row["code"] for row in rows_from(generate_mock_csv(spec))]
    assert values.count("__DUPLICATE__") >= 2


def test_more_than_100_cases_expand_row_count() -> None:
    tokens = [f"bad_{index}" for index in range(150)]
    spec = make_spec(boolean_field(nullable=True, invalid_value_tokens=tokens))
    rows = rows_from(generate_mock_csv(spec))
    assert len(rows) == 150
    assert {row["active"] for row in rows} == set(tokens)


def test_more_than_1000_cases_are_truncated_without_error() -> None:
    tokens = [f"bad_{index}" for index in range(MAX_ROW_COUNT + 200)]
    spec = make_spec(boolean_field(nullable=True, invalid_value_tokens=tokens))
    rows = rows_from(generate_mock_csv(spec))
    assert len(rows) == MAX_ROW_COUNT
    assert rows[-1]["active"] == "bad_999"


def test_spec_without_negative_condition_is_rejected() -> None:
    spec = make_spec(boolean_field(nullable=True, invalid_value_tokens=[]))
    with pytest.raises(ValueError, match="沒有可產生反向資料"):
        generate_mock_csv(spec)


def test_invalid_pattern_fails_clearly() -> None:
    spec = make_spec(string_field(pattern="["))
    with pytest.raises(ValueError, match="pattern 不是合法"):
        generate_mock_csv(spec)


def test_universal_pattern_is_skipped_but_other_rules_still_generate() -> None:
    spec = make_spec(
        string_field(
            nullable=True,
            allow_empty_string=True,
            invalid_value_tokens=["INVALID"],
            pattern=r".*",
        )
    )
    cases = build_violation_cases(spec)
    assert [case.rule for case in cases] == ["invalid_value_token"]
    assert len(rows_from(generate_mock_csv(spec))) == 100


def test_numeric_and_datetime_boundary_violations_are_outside_limits() -> None:
    spec = make_spec(
        int_field(min_value=1, max_value=10, invalid_value_tokens=[]),
        float_field(min_value=-1.5, max_value=2.5, invalid_value_tokens=[]),
        datetime_field(
            datetime_after="2024-01-01T00:00:00Z",
            datetime_before="2024-01-02T00:00:00Z",
            invalid_value_tokens=[],
        ),
    )
    cases = {(case.field_name, case.rule): case.value for case in build_violation_cases(spec)}
    assert cases[("quantity", "min_value")] == 0
    assert cases[("quantity", "max_value")] == 11
    assert cases[("amount", "min_value")] == -2.5
    assert cases[("amount", "max_value")] == 3.5
    assert cases[("created_at", "datetime_after")] == "2023-12-31T23:59:59Z"
    assert cases[("created_at", "datetime_before")] == "2024-01-02T00:00:01Z"
