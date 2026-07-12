from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft7Validator

from core.models import FieldSpec
from core.validation_suite import build_expectation_suite


SCHEMA_PATH = Path(__file__).parents[1] / "core" / "schemas" / "field_spec.schema.json"
COMMON = {
    "nullable": False,
    "invalid_value_tokens": ["NULL", "null", "NA", "None", "none"],
    "confidence": "high",
    "source": "discussed_with_user",
}


def document(field: dict) -> dict:
    return {
        "table_name": "orders",
        "version": 1,
        "change_note": "test",
        "fields": [{**COMMON, **field}],
    }


class FieldSpecContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

    def test_string_requires_unique(self) -> None:
        raw = document(
            {
                "name": "code",
                "dtype": "string",
                "allow_empty_string": False,
                "enum_values": None,
                "pattern": None,
            }
        )
        self.assertFalse(self.validator.is_valid(raw))
        with self.assertRaisesRegex(ValueError, "缺少 string 專屬屬性.*unique"):
            FieldSpec(**raw)

    def test_non_string_forbids_unique(self) -> None:
        raw = document(
            {
                "name": "amount",
                "dtype": "float",
                "unique": True,
                "min_value": 0,
                "max_value": 100,
            }
        )
        self.assertFalse(self.validator.is_valid(raw))
        with self.assertRaisesRegex(ValueError, "不應出現 string/datetime 專屬屬性.*unique"):
            FieldSpec(**raw)

    def test_string_unique_generates_ge_expectation(self) -> None:
        spec = FieldSpec(
            **document(
                {
                    "name": "code",
                    "dtype": "string",
                    "unique": True,
                    "allow_empty_string": False,
                    "enum_values": None,
                    "pattern": None,
                }
            )
        )
        suite = build_expectation_suite("orders", spec)
        expectation_types = {
            expectation["expectation_type"]
            for expectation in suite["expectations"]
        }
        self.assertIn("expect_column_values_to_be_unique", expectation_types)


if __name__ == "__main__":
    unittest.main()
