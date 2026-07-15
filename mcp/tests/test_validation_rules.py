from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from conftest import int_field, spec_document, string_field
from core.models import FieldSpec
from core.validation_rules import (
    ValidationRule,
    build_validation_rules,
    parse_row_rules,
)


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"


def row_rule(**overrides) -> dict:
    return {
        "id": "row.code_required_when_alt_empty",
        "desc": "alt 為空字串時，code 不可為 null",
        "columns": ["alt", "code"],
        "examples": {
            "pass": [{"name": "code 有值", "sql": "alt = '' AND code IS NOT NULL"}],
            "fail": [{"name": "code 缺值", "sql": "alt = '' AND code IS NULL"}],
        },
        **overrides,
    }


def test_build_validation_rules_keeps_minimal_input_schema_and_splits_col_rules() -> None:
    spec = FieldSpec(
        **spec_document(
            string_field(
                "code",
                nullable=False,
                invalid_value_tokens=[],
                unique=True,
                allow_empty_string=False,
            ),
            int_field(
                "amount",
                nullable=True,
                invalid_value_tokens=[],
                min_value=0,
                max_value=10,
            ),
        )
    )
    rules = build_validation_rules(DATASET_URN, spec, [])

    document = rules.model_dump(mode="json", by_alias=True)
    assert document["input_schema"] == [
        {"name": "code", "dtype": "string"},
        {"name": "amount", "dtype": "int"},
    ]
    assert [rule["id"] for rule in document["col_rules"]] == [
        "col.code.not_null",
        "col.code.unique",
        "col.code.not_empty",
        "col.amount.range",
    ]
    assert set(document["col_rules"][0]) == {
        "id",
        "desc",
        "columns",
        "examples",
    }


def test_row_rules_keep_only_minimal_fields_and_sql_examples() -> None:
    parsed = parse_row_rules(json.dumps([row_rule()]))
    assert parsed[0].model_dump(mode="json", by_alias=True) == row_rule()


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "col.not_a_row_rule"},
        {"columns": ["code"]},
        {"columns": ["code", "missing"]},
        {"examples": {"pass": [], "fail": [{"name": "x", "sql": "x"}]}},
    ],
)
def test_validation_contract_rejects_invalid_row_rules(overrides: dict) -> None:
    spec = FieldSpec(
        **spec_document(
            string_field("code", nullable=True, invalid_value_tokens=[], allow_empty_string=True),
            string_field("alt", nullable=True, invalid_value_tokens=[], allow_empty_string=True),
        )
    )
    with pytest.raises(ValidationError):
        submitted = ValidationRule.model_validate(row_rule(**overrides))
        build_validation_rules(DATASET_URN, spec, [submitted])


def test_parse_row_rules_reports_invalid_json() -> None:
    with pytest.raises(ValueError, match="不是合法的 JSON"):
        parse_row_rules("{")
