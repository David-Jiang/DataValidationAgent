from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from conftest import int_field, spec_document, string_field
from core.artifacts import (
    RowRuleImplementation,
    RuleFixture,
    RuleTestCases,
    render_data_validation_module,
    render_readme,
    render_test_module,
    render_validation_rules_json,
)
from core.models import FieldSpec
from core.validation_rules import ValidationRule, build_validation_rules


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"


def package_contract():
    spec = FieldSpec(
        **spec_document(
            int_field(
                "amount",
                nullable=True,
                invalid_value_tokens=[],
                min_value=0,
                max_value=10,
            ),
            string_field(
                "status",
                nullable=True,
                invalid_value_tokens=[],
                allow_empty_string=True,
            ),
        )
    )
    row_rule = ValidationRule.model_validate(
        {
            "id": "row.amount_required_when_status_paid",
            "desc": "status 為 PAID 時，amount 不可為 null",
            "columns": ["status", "amount"],
            "examples": {
                "pass": [{"name": "已付款且有金額", "sql": "status = 'PAID' AND amount IS NOT NULL"}],
                "fail": [{"name": "已付款但無金額", "sql": "status = 'PAID' AND amount IS NULL"}],
            },
        }
    )
    return spec, build_validation_rules(DATASET_URN, spec, [row_rule])


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("generated_data_validation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_json_and_chinese_readme_are_generated_from_same_rules() -> None:
    _spec, rules = package_contract()
    document = json.loads(render_validation_rules_json(rules))
    readme = render_readme(rules)

    assert document["input_schema"] == [
        {"name": "amount", "dtype": "int"},
        {"name": "status", "dtype": "string"},
    ]
    assert "| 規則總數 | 2 |" in readme
    assert "## 欄位規則（Column Rules）" in readme
    assert "## 跨欄位規則（Cross-field Row Rules）" in readme
    assert "<summary>跨欄位規則 — 1 條規則</summary>" in readme
    assert "status 為 PAID 時，amount 不可為 null" in readme


def test_generated_validate_short_circuits_empty_and_partitions_nonempty_rows(
    tmp_path: Path,
) -> None:
    spec, rules = package_contract()
    source = render_data_validation_module(
        rules,
        spec,
        [
            RowRuleImplementation(
                id="row.amount_required_when_status_paid",
                body=(
                    'condition = df["status"].eq("PAID").fillna(False)\n'
                    'return (~condition | df["amount"].notna()).fillna(False)'
                ),
            )
        ],
    )
    module_path = tmp_path / "data_validation.py"
    module_path.write_text(source, encoding="utf-8")
    module = _load_module(module_path)

    empty_valid, empty_invalid = module.validate(pd.DataFrame())
    assert empty_valid.empty and empty_invalid.empty
    assert list(empty_invalid.columns) == []

    df = pd.DataFrame(
        [
            {"amount": 5, "status": "PAID"},
            {"amount": None, "status": "PAID"},
            {"amount": 20, "status": "OPEN"},
        ]
    )
    valid_df, invalid_df = module.validate(df)
    assert valid_df.index.tolist() == [0]
    assert invalid_df.index.tolist() == [1, 2]
    assert invalid_df.loc[1, module.FAILED_RULES_COLUMN] == [
        "row.amount_required_when_status_paid"
    ]
    assert invalid_df.loc[2, module.FAILED_RULES_COLUMN] == ["col.amount.range"]


def test_generated_validate_turns_execution_failure_into_invalid_reason(
    tmp_path: Path,
) -> None:
    spec, rules = package_contract()
    source = render_data_validation_module(
        rules,
        spec,
        [
            RowRuleImplementation(
                id="row.amount_required_when_status_paid",
                body='return df["missing_column"].notna()',
            )
        ],
    )
    path = tmp_path / "data_validation.py"
    path.write_text(source, encoding="utf-8")
    module = _load_module(path)

    valid_df, invalid_df = module.validate(
        pd.DataFrame([{"amount": 5, "status": "PAID"}])
    )
    assert valid_df.empty
    assert "執行失敗" in invalid_df.iloc[0][module.FAILURE_REASONS_COLUMN][0]


def test_test_module_has_pass_fail_rule_tests_but_no_execution_failure_test() -> None:
    _spec, rules = package_contract()
    cases = [
        RuleTestCases(
            id="col.amount.range",
            pass_cases=[RuleFixture(name="範圍內", rows=[{"amount": 5}])],
            fail_cases=[RuleFixture(name="超出範圍", rows=[{"amount": 20}])],
        ),
        RuleTestCases(
            id="row.amount_required_when_status_paid",
            pass_cases=[
                RuleFixture(name="有金額", rows=[{"status": "PAID", "amount": 5}])
            ],
            fail_cases=[
                RuleFixture(name="缺金額", rows=[{"status": "PAID", "amount": None}])
            ],
        ),
    ]
    source = render_test_module(rules, cases)
    compile(source, "test_data_validation.py", "exec")
    assert "test_rule_pass_cases" in source
    assert "test_rule_fail_cases" in source
    assert "test_empty_dataframe_returns_two_empty_dataframes" in source
    assert "execution_failure" not in source


def test_generated_package_pytest_runs_successfully(tmp_path: Path) -> None:
    spec, rules = package_contract()
    data_validation_source = render_data_validation_module(
        rules,
        spec,
        [
            RowRuleImplementation(
                id="row.amount_required_when_status_paid",
                body=(
                    'condition = df["status"].eq("PAID").fillna(False)\n'
                    'return (~condition | df["amount"].notna()).fillna(False)'
                ),
            )
        ],
    )
    cases = [
        RuleTestCases(
            id="col.amount.range",
            pass_cases=[RuleFixture(name="範圍內", rows=[{"amount": 5}])],
            fail_cases=[RuleFixture(name="超出範圍", rows=[{"amount": 20}])],
        ),
        RuleTestCases(
            id="row.amount_required_when_status_paid",
            pass_cases=[
                RuleFixture(name="有金額", rows=[{"status": "PAID", "amount": 5}])
            ],
            fail_cases=[
                RuleFixture(name="缺金額", rows=[{"status": "PAID", "amount": None}])
            ],
        ),
    ]
    (tmp_path / "data_validation.py").write_text(
        data_validation_source, encoding="utf-8"
    )
    (tmp_path / "test_data_validation.py").write_text(
        render_test_module(rules, cases), encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_data_validation.py"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_row_rule_python_rejects_file_io() -> None:
    spec, rules = package_contract()
    with pytest.raises(ValueError, match="不允許"):
        render_data_validation_module(
            rules,
            spec,
            [
                RowRuleImplementation(
                    id="row.amount_required_when_status_paid",
                    body='pd.read_csv("secret.csv")\nreturn df["amount"].notna()',
                )
            ],
        )


def test_row_rule_python_rejects_dynamic_import() -> None:
    spec, rules = package_contract()
    with pytest.raises(ValueError, match="不允許"):
        render_data_validation_module(
            rules,
            spec,
            [
                RowRuleImplementation(
                    id="row.amount_required_when_status_paid",
                    body='__import__("os").system("whoami")\nreturn df["amount"].notna()',
                )
            ],
        )
