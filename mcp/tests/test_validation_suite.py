from __future__ import annotations

import pytest

from conftest import (
    boolean_field,
    datetime_field,
    float_field,
    int_field,
    spec_document,
    string_field,
)
from core.models import FieldSpec
from core.validation_suite import build_expectation_suite


def configurations(suite: dict, expectation_type: str, column: str | None = None) -> list[dict]:
    matches = [
        expectation
        for expectation in suite["expectations"]
        if expectation["expectation_type"] == expectation_type
    ]
    if column is not None:
        matches = [match for match in matches if match["kwargs"].get("column") == column]
    return matches


def one_configuration(suite: dict, expectation_type: str, column: str) -> dict:
    matches = configurations(suite, expectation_type, column)
    assert len(matches) == 1
    return matches[0]


def test_suite_name_and_column_set() -> None:
    spec = FieldSpec(**spec_document(string_field("code"), boolean_field("active")))
    suite = build_expectation_suite("orders", spec)
    assert suite["expectation_suite_name"] == "orders_validation_suite"
    table_config = configurations(suite, "expect_table_columns_to_match_set")
    assert len(table_config) == 1
    assert table_config[0]["kwargs"] == {
        "column_set": ["code", "active"],
        "exact_match": False,
    }


def test_non_nullable_adds_not_null_but_nullable_does_not() -> None:
    spec = FieldSpec(
        **spec_document(string_field("required"), string_field("optional", nullable=True))
    )
    suite = build_expectation_suite("orders", spec)
    assert len(configurations(suite, "expect_column_values_to_not_be_null", "required")) == 1
    assert configurations(suite, "expect_column_values_to_not_be_null", "optional") == []


@pytest.mark.parametrize("unique", [True, False])
def test_string_uniqueness_is_conditional(unique: bool) -> None:
    suite = build_expectation_suite(
        "orders", FieldSpec(**spec_document(string_field(unique=unique)))
    )
    assert bool(configurations(suite, "expect_column_values_to_be_unique", "code")) is unique


def test_string_rules_map_to_expected_configurations() -> None:
    spec = FieldSpec(
        **spec_document(
            string_field(
                enum_values=["AAA", "BBB"],
                pattern=r"[A-Z]{3}",
                allow_empty_string=False,
            )
        )
    )
    suite = build_expectation_suite("orders", spec)
    assert one_configuration(suite, "expect_column_values_to_not_match_regex", "code")[
        "kwargs"
    ]["regex"] == r"^\s*$"
    assert one_configuration(suite, "expect_column_values_to_be_in_set", "code")["kwargs"][
        "value_set"
    ] == ["AAA", "BBB"]
    assert one_configuration(suite, "expect_column_values_to_match_regex", "code")["kwargs"][
        "regex"
    ] == r"[A-Z]{3}"


@pytest.mark.parametrize(
    ("field", "column", "minimum", "maximum"),
    [
        (int_field(min_value=1, max_value=None), "quantity", 1.0, None),
        (float_field(min_value=None, max_value=9.5), "amount", None, 9.5),
    ],
)
def test_numeric_bounds_map_to_between(
    field: dict, column: str, minimum: float | None, maximum: float | None
) -> None:
    suite = build_expectation_suite("orders", FieldSpec(**spec_document(field)))
    kwargs = one_configuration(suite, "expect_column_values_to_be_between", column)["kwargs"]
    assert kwargs["min_value"] == minimum
    assert kwargs["max_value"] == maximum


def test_numeric_without_bounds_has_no_between_expectation() -> None:
    suite = build_expectation_suite("orders", FieldSpec(**spec_document(int_field())))
    assert configurations(suite, "expect_column_values_to_be_between", "quantity") == []


def test_datetime_rules_map_to_between_and_format() -> None:
    spec = FieldSpec(
        **spec_document(
            datetime_field(
                datetime_after="2024-01-01T00:00:00Z",
                datetime_before="2024-01-02T00:00:00Z",
                expected_datetime_format="%Y-%m-%dT%H:%M:%SZ",
            )
        )
    )
    suite = build_expectation_suite("orders", spec)
    between = one_configuration(suite, "expect_column_values_to_be_between", "created_at")
    assert between["kwargs"] == {
        "column": "created_at",
        "min_value": "2024-01-01T00:00:00Z",
        "max_value": "2024-01-02T00:00:00Z",
        "parse_strings_as_datetimes": True,
    }
    format_config = one_configuration(
        suite, "expect_column_values_to_match_strftime_format", "created_at"
    )
    assert format_config["kwargs"]["strftime_format"] == "%Y-%m-%dT%H:%M:%SZ"


def test_datetime_without_bounds_or_format_adds_neither_expectation() -> None:
    suite = build_expectation_suite("orders", FieldSpec(**spec_document(datetime_field())))
    assert configurations(suite, "expect_column_values_to_be_between", "created_at") == []
    assert configurations(
        suite, "expect_column_values_to_match_strftime_format", "created_at"
    ) == []


@pytest.mark.parametrize("tokens", [["NULL", "NA"], []])
def test_invalid_token_expectation_is_conditional(tokens: list[str]) -> None:
    spec = FieldSpec(**spec_document(boolean_field(invalid_value_tokens=tokens)))
    suite = build_expectation_suite("orders", spec)
    matches = configurations(suite, "expect_column_values_to_not_be_in_set", "active")
    assert bool(matches) is bool(tokens)
    if tokens:
        assert matches[0]["kwargs"]["value_set"] == tokens


def test_empty_enum_and_allow_empty_true_add_no_string_expectations() -> None:
    spec = FieldSpec(
        **spec_document(string_field(enum_values=[], allow_empty_string=True, pattern=None))
    )
    suite = build_expectation_suite("orders", spec)
    assert configurations(suite, "expect_column_values_to_be_in_set", "code") == []
    assert configurations(suite, "expect_column_values_to_not_match_regex", "code") == []
