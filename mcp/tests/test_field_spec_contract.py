from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from conftest import (
    boolean_field,
    datetime_field,
    float_field,
    int_field,
    spec_document,
    string_field,
)
from core.models import FieldSpec


SCHEMA_PATH = Path(__file__).parents[1] / "core" / "schemas" / "field_spec.schema.json"
VALIDATOR = Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "field",
    [string_field(), int_field(), float_field(), datetime_field(), boolean_field()],
)
def test_json_schema_accepts_every_supported_dtype(field: dict) -> None:
    VALIDATOR.validate(spec_document(field))


def test_json_schema_requires_unique_for_string() -> None:
    field = string_field()
    del field["unique"]
    assert not VALIDATOR.is_valid(spec_document(field))


@pytest.mark.parametrize(
    "field",
    [
        int_field(unique=True),
        float_field(unique=True),
        datetime_field(unique=True),
        boolean_field(unique=True),
    ],
)
def test_json_schema_forbids_unique_for_non_string(field: dict) -> None:
    assert not VALIDATOR.is_valid(spec_document(field))


def test_json_schema_rejects_unknown_properties() -> None:
    assert not VALIDATOR.is_valid(spec_document(string_field(unknown_rule=True)))


def test_json_schema_and_pydantic_accept_same_complete_document() -> None:
    raw = spec_document(
        string_field(), int_field(), float_field(), datetime_field(), boolean_field()
    )
    VALIDATOR.validate(raw)
    parsed = FieldSpec(**raw)
    assert [field.dtype.value for field in parsed.fields] == [
        "string",
        "int",
        "float",
        "datetime",
        "boolean",
    ]
