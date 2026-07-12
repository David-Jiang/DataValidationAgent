from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from conftest import (
    boolean_field,
    datetime_field,
    float_field,
    int_field,
    spec_document,
    string_field,
)
from core import models
from core.models import DType, FieldSpec, parse_field_spec


def test_dtype_values_are_stable() -> None:
    assert {dtype.value for dtype in DType} == {"string", "int", "float", "datetime", "boolean"}


@pytest.mark.parametrize(
    "field",
    [string_field(), int_field(), float_field(), datetime_field(), boolean_field()],
)
def test_every_supported_field_type_parses(field: dict) -> None:
    parsed = FieldSpec(**spec_document(field))
    assert parsed.fields[0].name == field["name"]


@pytest.mark.parametrize("missing", ["unique", "allow_empty_string", "enum_values", "pattern"])
def test_string_requires_all_specific_properties(missing: str) -> None:
    field = string_field()
    del field[missing]
    with pytest.raises(ValidationError, match=f"缺少 string 專屬屬性.*{missing}"):
        FieldSpec(**spec_document(field))


@pytest.mark.parametrize("forbidden", ["min_value", "max_value", "datetime_after"])
def test_string_forbids_other_type_properties(forbidden: str) -> None:
    with pytest.raises(ValidationError, match="不應出現 numeric/datetime"):
        FieldSpec(**spec_document(string_field(**{forbidden: None})))


@pytest.mark.parametrize("dtype_factory", [int_field, float_field])
@pytest.mark.parametrize("missing", ["min_value", "max_value"])
def test_numeric_fields_require_both_bounds(dtype_factory, missing: str) -> None:
    field = dtype_factory()
    del field[missing]
    with pytest.raises(ValidationError, match=f"缺少 numeric 專屬屬性.*{missing}"):
        FieldSpec(**spec_document(field))


@pytest.mark.parametrize("dtype_factory", [int_field, float_field])
@pytest.mark.parametrize("forbidden", ["unique", "allow_empty_string", "datetime_before"])
def test_numeric_fields_forbid_other_type_properties(dtype_factory, forbidden: str) -> None:
    with pytest.raises(ValidationError, match="不應出現 string/datetime"):
        FieldSpec(**spec_document(dtype_factory(**{forbidden: None})))


@pytest.mark.parametrize(("bound", "value"), [("min_value", 1.5), ("max_value", 2.5)])
def test_integer_bounds_must_be_integral(bound: str, value: float) -> None:
    with pytest.raises(ValidationError, match=f"{bound} 必須是 integer"):
        FieldSpec(**spec_document(int_field(**{bound: value})))


@pytest.mark.parametrize("dtype_factory", [int_field, float_field])
def test_numeric_minimum_cannot_exceed_maximum(dtype_factory) -> None:
    with pytest.raises(ValidationError, match="min_value 不可大於 max_value"):
        FieldSpec(**spec_document(dtype_factory(min_value=2, max_value=1)))


@pytest.mark.parametrize(
    "missing", ["datetime_after", "datetime_before", "expected_datetime_format"]
)
def test_datetime_requires_all_specific_properties(missing: str) -> None:
    field = datetime_field()
    del field[missing]
    with pytest.raises(ValidationError, match=f"缺少 datetime 專屬屬性.*{missing}"):
        FieldSpec(**spec_document(field))


@pytest.mark.parametrize("forbidden", ["unique", "min_value", "allow_empty_string"])
def test_datetime_forbids_other_type_properties(forbidden: str) -> None:
    with pytest.raises(ValidationError, match="不應出現 string/numeric"):
        FieldSpec(**spec_document(datetime_field(**{forbidden: None})))


@pytest.mark.parametrize(
    "forbidden", ["unique", "allow_empty_string", "min_value", "datetime_after"]
)
def test_boolean_forbids_all_type_specific_properties(forbidden: str) -> None:
    with pytest.raises(ValidationError, match="不應出現型別專屬屬性"):
        FieldSpec(**spec_document(boolean_field(**{forbidden: None})))


def test_invalid_value_tokens_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="不可包含重複值"):
        FieldSpec(**spec_document(boolean_field(invalid_value_tokens=["NULL", "NULL"])))


def test_field_names_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="重複的欄位名稱.*code"):
        FieldSpec(**spec_document(string_field("code"), string_field("code")))


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": 0},
        {"fields": []},
        {"unknown": True},
    ],
)
def test_top_level_contract_constraints(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        FieldSpec(**spec_document(**overrides))


def test_parse_field_spec_accepts_valid_json() -> None:
    parsed = parse_field_spec(json.dumps(spec_document(int_field(min_value=1, max_value=2))))
    assert parsed.table_name == "orders"
    assert parsed.fields[0].dtype == DType.int_


def test_parse_field_spec_reports_invalid_json() -> None:
    with pytest.raises(ValueError, match="不是合法的 JSON"):
        parse_field_spec("{")


def test_parse_field_spec_formats_validation_locations() -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_field_spec(json.dumps(spec_document(boolean_field(unique=True))))
    message = str(exc_info.value)
    assert "field_spec 格式不符合規範" in message
    assert "fields -> 0" in message
    assert "unique" in message


def test_parse_field_spec_does_not_hide_unexpected_internal_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenFieldSpec:
        def __init__(self, **_data) -> None:
            raise RuntimeError("unexpected")

    monkeypatch.setattr(models, "FieldSpec", BrokenFieldSpec)
    with pytest.raises(RuntimeError, match="unexpected"):
        models.parse_field_spec(json.dumps(spec_document(boolean_field())))
