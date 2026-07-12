from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from core.models import FieldSpec


COMMON_FIELD: dict[str, Any] = {
    "nullable": False,
    "invalid_value_tokens": ["NULL", "null", "NA", "None", "none"],
    "confidence": "high",
    "source": "discussed_with_user",
}


def string_field(name: str = "code", **overrides: Any) -> dict[str, Any]:
    return {
        **COMMON_FIELD,
        "name": name,
        "dtype": "string",
        "unique": False,
        "allow_empty_string": False,
        "enum_values": None,
        "pattern": None,
        **overrides,
    }


def int_field(name: str = "quantity", **overrides: Any) -> dict[str, Any]:
    return {
        **COMMON_FIELD,
        "name": name,
        "dtype": "int",
        "min_value": None,
        "max_value": None,
        **overrides,
    }


def float_field(name: str = "amount", **overrides: Any) -> dict[str, Any]:
    return {
        **COMMON_FIELD,
        "name": name,
        "dtype": "float",
        "min_value": None,
        "max_value": None,
        **overrides,
    }


def datetime_field(name: str = "created_at", **overrides: Any) -> dict[str, Any]:
    return {
        **COMMON_FIELD,
        "name": name,
        "dtype": "datetime",
        "datetime_after": None,
        "datetime_before": None,
        "expected_datetime_format": None,
        **overrides,
    }


def boolean_field(name: str = "active", **overrides: Any) -> dict[str, Any]:
    return {
        **COMMON_FIELD,
        "name": name,
        "dtype": "boolean",
        **overrides,
    }


def spec_document(*fields: Mapping[str, Any], **overrides: Any) -> dict[str, Any]:
    return {
        "table_name": "orders",
        "version": 1,
        "change_note": "test",
        "fields": [dict(field) for field in fields] or [string_field()],
        **overrides,
    }


@pytest.fixture
def all_types_spec() -> FieldSpec:
    return FieldSpec(
        **spec_document(
            string_field(
                unique=True,
                enum_values=["AAA", "BBB", "CCC"],
                pattern=r"[A-Z]{3}",
            ),
            int_field(min_value=1, max_value=10),
            float_field(min_value=-1.5, max_value=2.5),
            datetime_field(
                datetime_after="2024-01-01T00:00:00Z",
                datetime_before="2024-01-02T00:00:00Z",
                expected_datetime_format="%Y-%m-%dT%H:%M:%SZ",
            ),
            boolean_field(),
        )
    )
