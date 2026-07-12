from __future__ import annotations

import csv
import io
import re
import unittest

from core.mock_data import generate_mock_csv
from core.models import FieldSpec


COMMON = {
    "nullable": False,
    "invalid_value_tokens": ["NULL", "null", "NA", "None", "none"],
    "confidence": "high",
    "source": "discussed_with_user",
}


def make_spec(field: dict) -> FieldSpec:
    return FieldSpec(
        table_name="orders",
        version=1,
        change_note="test",
        fields=[{**COMMON, **field}],
    )


def values_from(csv_text: str, column: str) -> list[str]:
    return [row[column] for row in csv.DictReader(io.StringIO(csv_text))]


class GenerateMockCsvTest(unittest.TestCase):
    def test_integer_values_preserve_type_and_range(self) -> None:
        spec = make_spec(
            {"name": "id", "dtype": "int", "min_value": 1, "max_value": 20}
        )
        values = values_from(generate_mock_csv(spec, 20), "id")
        self.assertTrue(all(value.isdigit() for value in values))
        self.assertTrue(all(1 <= int(value) <= 20 for value in values))

    def test_pattern_and_unique_are_both_honored(self) -> None:
        spec = make_spec(
            {
                "name": "code",
                "dtype": "string",
                "unique": True,
                "allow_empty_string": False,
                "enum_values": None,
                "pattern": r"[A-Z]{3}[0-9]{3}",
            }
        )
        values = values_from(generate_mock_csv(spec, 50), "code")
        self.assertEqual(50, len(set(values)))
        self.assertTrue(all(re.fullmatch(r"[A-Z]{3}[0-9]{3}", value) for value in values))

    def test_enum_is_not_modified_to_force_uniqueness(self) -> None:
        spec = make_spec(
            {
                "name": "status",
                "dtype": "string",
                "unique": True,
                "allow_empty_string": False,
                "enum_values": ["new", "done"],
                "pattern": None,
            }
        )
        with self.assertRaisesRegex(ValueError, "unique enum 只有 2 個可用值"):
            generate_mock_csv(spec, 3)

    def test_unique_is_rejected_for_non_string_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "不應出現型別專屬屬性.*unique"):
            make_spec({"name": "active", "dtype": "boolean", "unique": True})

    def test_datetime_values_follow_requested_format(self) -> None:
        spec = make_spec(
            {
                "name": "created_at",
                "dtype": "datetime",
                "datetime_after": "2024-01-01T00:00:00Z",
                "datetime_before": "2024-01-10T00:00:00Z",
                "expected_datetime_format": "%Y-%m-%dT%H:%M:%SZ",
            }
        )
        values = values_from(generate_mock_csv(spec, 20), "created_at")
        self.assertTrue(all(re.fullmatch(r"2024-01-0[1-9]T\d{2}:\d{2}:\d{2}Z", value) for value in values))

    def test_default_row_count_is_100_and_has_no_upper_limit(self) -> None:
        spec = make_spec({"name": "active", "dtype": "boolean"})
        self.assertEqual(100, len(values_from(generate_mock_csv(spec), "active")))
        self.assertEqual(10_001, len(values_from(generate_mock_csv(spec, 10_001), "active")))
        with self.assertRaisesRegex(ValueError, "row_count 必須是正整數"):
            generate_mock_csv(spec, 0)


if __name__ == "__main__":
    unittest.main()
