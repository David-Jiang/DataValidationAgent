"""產生 validation-as-code package 的四個 artifacts。"""
from __future__ import annotations

import json
import re
import textwrap
from typing import Any

from .validation_rules import ValidationRules


def _function_name(rule_id: str) -> str:
    return "_rule_" + re.sub(r"[^A-Za-z0-9_]", "_", rule_id)


def render_validation_rules_json(rules: ValidationRules) -> str:
    return json.dumps(
        rules.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        indent=2,
    )


def _markdown(value: object) -> str:
    text = str(value).replace("|", "\\|").replace("\n", "<br>")
    return text or "—"


def render_readme(rules: ValidationRules) -> str:
    all_rules = [*rules.col_rules, *rules.row_rules]
    pass_count = sum(len(rule.examples.pass_cases) for rule in all_rules)
    fail_count = sum(len(rule.examples.fail_cases) for rule in all_rules)
    lines = [
        f"# 資料驗證契約：{rules.dataset.table_name}",
        "",
        "本目錄提供可直接放入 Airflow ETL repository 的 Pandas-native 資料驗證程式與 pytest。",
        "",
        "## 摘要",
        "",
        "| 項目 | 數量 |",
        "| --- | ---: |",
        f"| 輸入欄位 | {len(rules.input_schema)} |",
        f"| 欄位規則 | {len(rules.col_rules)} |",
        f"| 跨欄位規則 | {len(rules.row_rules)} |",
        f"| 規則總數 | {len(all_rules)} |",
        f"| 通過範例 | {pass_count} |",
        f"| 失敗範例 | {fail_count} |",
        "",
        "## 輸入資料結構",
        "",
        "| 欄位 | 資料型別 |",
        "| --- | --- |",
    ]
    lines.extend(
        f"| {_markdown(column.name)} | {_markdown(column.dtype.value)} |"
        for column in rules.input_schema
    )
    lines.extend(["", "## 欄位規則（Column Rules）", ""])

    rules_by_column = {
        column.name: [rule for rule in rules.col_rules if rule.columns == [column.name]]
        for column in rules.input_schema
    }
    for column in rules.input_schema:
        column_rules = rules_by_column[column.name]
        lines.extend(
            [
                "<details>",
                (
                    f"<summary>{_markdown(column.name)} — {_markdown(column.dtype.value)} — "
                    f"{len(column_rules)} 條規則</summary>"
                ),
                "",
                "| 規則 ID | 驗證條件 | 通過範例 | 失敗範例 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for rule in column_rules:
            passing = "<br>".join(
                f"{_markdown(case.name)}：`{_markdown(case.sql)}`"
                for case in rule.examples.pass_cases
            )
            failing = "<br>".join(
                f"{_markdown(case.name)}：`{_markdown(case.sql)}`"
                for case in rule.examples.fail_cases
            )
            lines.append(
                f"| `{rule.id}` | {_markdown(rule.desc)} | {passing} | {failing} |"
            )
        lines.extend(["", "</details>", ""])

    lines.extend(
        [
            "## 跨欄位規則（Cross-field Row Rules）",
            "",
            "<details>",
            f"<summary>跨欄位規則 — {len(rules.row_rules)} 條規則</summary>",
            "",
            "| 規則 ID | 使用欄位 | 驗證條件 | 通過範例 | 失敗範例 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if rules.row_rules:
        for rule in rules.row_rules:
            passing = "<br>".join(
                f"{_markdown(case.name)}：`{_markdown(case.sql)}`"
                for case in rule.examples.pass_cases
            )
            failing = "<br>".join(
                f"{_markdown(case.name)}：`{_markdown(case.sql)}`"
                for case in rule.examples.fail_cases
            )
            lines.append(
                f"| `{rule.id}` | {_markdown(', '.join(rule.columns))} | "
                f"{_markdown(rule.desc)} | {passing} | {failing} |"
            )
    else:
        lines.append("| — | — | 本次沒有跨欄位規則 | — | — |")

    lines.extend(["", "</details>"])

    lines.extend(
        [
            "",
            "## 使用方式",
            "",
            "```python",
            "from data_validation import validate",
            "",
            "valid_df, invalid_df = validate(input_df)",
            "```",
            "",
            "空 DataFrame 會在執行任何規則前，直接回傳兩個空 DataFrame。非空資料若違反規則或規則執行失敗，",
            "會進入 `invalid_df`，並附加 `__validation_failed_rules__` 與",
            "`__validation_failure_reasons__` 欄位。",
            "",
            "```bash",
            "pytest test_data_validation.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def render_data_validation_module(
    rules: ValidationRules,
) -> str:
    all_rules = [*rules.col_rules, *rules.row_rules]
    if all_rules and not rules.implementation_bodies:
        raise ValueError("ValidationRules 尚未附加 executable rule implementations")
    descriptions = {rule.id: rule.desc for rule in all_rules}
    columns = {rule.id: rule.columns for rule in all_rules}
    functions: list[str] = []
    registry: list[str] = []
    for rule in all_rules:
        function_name = _function_name(rule.id)
        functions.append(
            f"def {function_name}(df: pd.DataFrame) -> pd.Series:\n"
            + textwrap.indent(rules.implementation_bodies[rule.id], "    ")
        )
        registry.append(f"    {rule.id!r}: {function_name},")

    required_columns = [column.name for column in rules.input_schema]
    module = f'''\
"""由 Data Validation Agent 產生的 Pandas-native validation module。"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd


FAILED_RULES_COLUMN = "__validation_failed_rules__"
FAILURE_REASONS_COLUMN = "__validation_failure_reasons__"
REQUIRED_COLUMNS = {required_columns!r}
RULE_DESCRIPTIONS = {descriptions!r}
RULE_COLUMNS = {columns!r}


{chr(10).join(functions)}


RULE_FUNCTIONS: dict[str, Callable[[pd.DataFrame], pd.Series]] = {{
{chr(10).join(registry)}
}}


def _evaluate_rule(rule_id: str, df: pd.DataFrame) -> pd.Series:
    return RULE_FUNCTIONS[rule_id](df)


def _execution_failure(df: object, reason: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    invalid_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    valid_df = invalid_df.iloc[0:0].copy()
    if invalid_df.empty:
        return valid_df, invalid_df
    invalid_df[FAILED_RULES_COLUMN] = [["validation.execution"] for _ in range(len(invalid_df))]
    invalid_df[FAILURE_REASONS_COLUMN] = [[f"執行失敗：{{reason}}"] for _ in range(len(invalid_df))]
    return valid_df, invalid_df


def _normalize_mask(mask: object, df: pd.DataFrame) -> pd.Series:
    if not isinstance(mask, pd.Series):
        raise TypeError("rule 必須回傳 pandas Series")
    if len(mask) != len(df):
        raise ValueError("rule 回傳長度與 DataFrame 不一致")
    if not mask.index.equals(df.index):
        raise ValueError("rule 回傳 index 與 DataFrame 不一致")
    if not pd.api.types.is_bool_dtype(mask.dtype):
        raise TypeError("rule 必須回傳 boolean Series")
    return mask.fillna(False).astype(bool)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not isinstance(df, pd.DataFrame):
        return _execution_failure(df, "input 必須是 pandas DataFrame")

    if df.empty:
        return df.copy(), df.copy()

    failed_rule_ids: list[list[str]] = [[] for _ in range(len(df))]
    failure_reasons: list[list[str]] = [[] for _ in range(len(df))]
    valid_mask = pd.Series(True, index=df.index, dtype=bool)

    missing_schema = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_schema:
        reason = f"執行失敗：缺少 input schema 欄位：{{missing_schema}}"
        valid_mask[:] = False
        for position in range(len(df)):
            failed_rule_ids[position].append("schema.input_schema")
            failure_reasons[position].append(reason)

    for rule_id, rule_function in RULE_FUNCTIONS.items():
        try:
            missing = [column for column in RULE_COLUMNS[rule_id] if column not in df.columns]
            if missing:
                raise KeyError(f"缺少欄位：{{missing}}")
            rule_mask = _normalize_mask(rule_function(df), df)
            reason = f"規則失敗：{{RULE_DESCRIPTIONS[rule_id]}}"
        except Exception as exc:
            rule_mask = pd.Series(False, index=df.index, dtype=bool)
            reason = f"執行失敗：{{rule_id}}：{{exc}}"

        failed_positions = [
            position for position, passed in enumerate(rule_mask.to_numpy()) if not passed
        ]
        for position in failed_positions:
            failed_rule_ids[position].append(rule_id)
            failure_reasons[position].append(reason)
        valid_mask &= rule_mask

    valid_df = df.loc[valid_mask].copy()
    invalid_df = df.loc[~valid_mask].copy()
    invalid_positions = [
        position for position, passed in enumerate(valid_mask.to_numpy()) if not passed
    ]
    invalid_df[FAILED_RULES_COLUMN] = [failed_rule_ids[position] for position in invalid_positions]
    invalid_df[FAILURE_REASONS_COLUMN] = [failure_reasons[position] for position in invalid_positions]
    return valid_df, invalid_df
'''
    return module


def render_test_module(
    rules: ValidationRules,
) -> str:
    all_rules = [*rules.col_rules, *rules.row_rules]
    if all_rules and not rules.test_cases:
        raise ValueError("ValidationRules 尚未附加 rule test cases")
    passing: list[tuple[str, str, list[dict[str, Any]]]] = []
    failing: list[tuple[str, str, list[dict[str, Any]]]] = []
    for rule_cases in rules.test_cases:
        passing.extend(
            (rule_cases.id, fixture.name, fixture.rows)
            for fixture in rule_cases.pass_cases
        )
        failing.extend(
            (rule_cases.id, fixture.name, fixture.rows)
            for fixture in rule_cases.fail_cases
        )

    return f'''\
"""每條 validation rule 的 passing 與 failing pytest。"""
from __future__ import annotations

import pandas as pd
import pytest

from data_validation import RULE_FUNCTIONS, _evaluate_rule, validate


PASS_CASES = {passing!r}
FAIL_CASES = {failing!r}


def test_every_rule_has_pass_and_fail_case() -> None:
    assert {{rule_id for rule_id, _name, _rows in PASS_CASES}} == set(RULE_FUNCTIONS)
    assert {{rule_id for rule_id, _name, _rows in FAIL_CASES}} == set(RULE_FUNCTIONS)


@pytest.mark.parametrize(
    ("rule_id", "case_name", "rows"),
    PASS_CASES,
    ids=[f"{{rule_id}}:{{name}}" for rule_id, name, _rows in PASS_CASES],
)
def test_rule_pass_cases(rule_id: str, case_name: str, rows: list[dict]) -> None:
    del case_name
    result = _evaluate_rule(rule_id, pd.DataFrame(rows))
    assert result.fillna(False).all()


@pytest.mark.parametrize(
    ("rule_id", "case_name", "rows"),
    FAIL_CASES,
    ids=[f"{{rule_id}}:{{name}}" for rule_id, name, _rows in FAIL_CASES],
)
def test_rule_fail_cases(rule_id: str, case_name: str, rows: list[dict]) -> None:
    del case_name
    result = _evaluate_rule(rule_id, pd.DataFrame(rows))
    assert (~result.fillna(False)).any()


def test_empty_dataframe_returns_two_empty_dataframes() -> None:
    source = pd.DataFrame()
    valid_df, invalid_df = validate(source)
    assert valid_df.empty
    assert invalid_df.empty
'''
