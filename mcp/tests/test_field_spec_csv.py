from __future__ import annotations

import csv
import io
import json

from conftest import int_field, spec_document, string_field
from core.field_spec_csv import FIELD_SPEC_COLUMNS, generate_field_spec_csv
from core.models import FieldSpec


def test_field_spec_csv_expands_every_property_and_field() -> None:
    spec = FieldSpec(
        **spec_document(
            string_field(
                "code",
                unique=True,
                enum_values=["A", "B"],
                pattern=r"[A-Z]",
            ),
            int_field("quantity", min_value=1, max_value=10),
        )
    )
    rows = list(csv.DictReader(io.StringIO(generate_field_spec_csv(spec))))

    assert len(rows) == 2
    assert list(rows[0]) == FIELD_SPEC_COLUMNS
    assert rows[0]["table_name"] == "orders"
    assert rows[0]["name"] == "code"
    assert rows[0]["dtype"] == "string"
    assert rows[0]["unique"] == "True"
    assert json.loads(rows[0]["enum_values"]) == ["A", "B"]
    assert json.loads(rows[0]["invalid_value_tokens"]) == [
        "NULL",
        "null",
        "NA",
        "None",
        "none",
    ]
    assert rows[1]["name"] == "quantity"
    assert rows[1]["min_value"] == "1.0"
    assert rows[1]["max_value"] == "10.0"
    assert rows[1]["unique"] == ""
