"""將正式版 field_spec 展開為方便人工比對的 CSV。"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from .models import FieldSpec

FIELD_SPEC_COLUMNS = [
    "table_name",
    "name",
    "dtype",
    "nullable",
    "unique",
    "allow_empty_string",
    "enum_values",
    "pattern",
    "min_value",
    "max_value",
    "datetime_after",
    "datetime_before",
    "expected_datetime_format",
    "invalid_value_tokens",
    "confidence",
    "source",
]


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def generate_field_spec_csv(field_spec: FieldSpec) -> str:
    """將全部屬性展開為欄，並讓每個資料欄位各占一列。"""
    rows = []
    for field in field_spec.fields:
        values = field.model_dump(mode="json")
        rows.append(
            {
                column: _csv_value(
                    field_spec.table_name if column == "table_name" else values.get(column)
                )
                for column in FIELD_SPEC_COLUMNS
            }
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELD_SPEC_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
