"""
依 field_spec 組裝 Great Expectations Expectation Suite。
"""
from __future__ import annotations

from great_expectations.expectations.expectation_configuration import ExpectationConfiguration
from great_expectations.core import ExpectationSuite

from .models import FieldSpec


def build_expectation_suite(table_name: str, field_spec: FieldSpec) -> dict:
    suite = ExpectationSuite()
    suite.expectation_suite_name = f"{table_name}_validation_suite"

    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_table_columns_to_match_set",
            kwargs={"column_set": [f.name for f in field_spec.fields], "exact_match": False},
        )
    )

    for f in field_spec.fields:
        col = f.name

        if f.nullable is False:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_not_be_null",
                    kwargs={"column": col},
                )
            )

        if f.unique:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_be_unique",
                    kwargs={"column": col},
                )
            )

        if f.allow_empty_string is False:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_not_match_regex",
                    kwargs={"column": col, "regex": r"^\s*$"},
                )
            )

        if f.enum_values:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_be_in_set",
                    kwargs={"column": col, "value_set": f.enum_values},
                )
            )

        if f.pattern:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_match_regex",
                    kwargs={"column": col, "regex": f.pattern},
                )
            )

        if f.min_value is not None or f.max_value is not None:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_be_between",
                    kwargs={"column": col, "min_value": f.min_value, "max_value": f.max_value},
                )
            )

        if f.datetime_after or f.datetime_before:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_be_between",
                    kwargs={
                        "column": col,
                        "min_value": f.datetime_after,
                        "max_value": f.datetime_before,
                        "parse_strings_as_datetimes": True,
                    },
                )
            )

        if f.expected_datetime_format:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_match_strftime_format",
                    kwargs={"column": col, "strftime_format": f.expected_datetime_format},
                )
            )

        if f.invalid_value_tokens:
            suite.add_expectation(
                ExpectationConfiguration(
                    expectation_type="expect_column_values_to_not_be_in_set",
                    kwargs={"column": col, "value_set": f.invalid_value_tokens},
                )
            )

    return suite.to_json_dict()
