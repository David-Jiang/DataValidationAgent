"""建立 col_rules、解析 row_rules，並封裝完整 ValidationRules。"""
from __future__ import annotations

import json
import re
import unicodedata

from pydantic import TypeAdapter

from .field_spec import DType, FieldSpec, FieldSpecField
from .validation_rules import (
    DatasetRef,
    InputColumn,
    RuleExamples,
    ValidationRule,
    ValidationRules,
    _column_key,
)


_ROW_RULE_ID = re.compile(r"^row\.[A-Za-z0-9_]+(?:[.-][A-Za-z0-9_]+)*$")
_RESTRICTED_TEXT_CATEGORIES = {"Cc", "Cf", "Cs", "Zl", "Zp"}
_MAX_ROW_RULES = 200
_MAX_RAW_JSON_LENGTH = 256_000
_MAX_ID_LENGTH = 128
_MAX_DESCRIPTION_LENGTH = 1_000
_MAX_COLUMN_NAME_LENGTH = 256
_MAX_EXAMPLE_NAME_LENGTH = 200
_MAX_EXAMPLE_SQL_LENGTH = 4_000


def _identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _examples(
    pass_cases: list[tuple[str, str]], fail_cases: list[tuple[str, str]]
) -> RuleExamples:
    return RuleExamples.model_validate(
        {
            "pass": [{"name": name, "sql": sql} for name, sql in pass_cases],
            "fail": [{"name": name, "sql": sql} for name, sql in fail_cases],
        }
    )


def _rule(
    field: FieldSpecField,
    suffix: str,
    desc: str,
    pass_cases: list[tuple[str, str]],
    fail_cases: list[tuple[str, str]],
) -> ValidationRule:
    return ValidationRule(
        id=f"col.{_column_key(field.name)}.{suffix}",
        desc=desc,
        columns=[field.name],
        examples=_examples(pass_cases, fail_cases),
    )


def build_col_rules(field_spec: FieldSpec) -> list[ValidationRule]:
    """將已驗證的 FieldSpec 確定性地拆成獨立 column rules。"""
    rules: list[ValidationRule] = []
    for field in field_spec.fields:
        column = _identifier(field.name)

        if field.nullable is False:
            rules.append(
                _rule(
                    field,
                    "not_null",
                    f"{field.name} 不可為 null",
                    [("欄位有值", f"{column} IS NOT NULL")],
                    [("欄位為 null", f"{column} IS NULL")],
                )
            )

        if field.invalid_value_tokens:
            values = ", ".join(_literal(value) for value in field.invalid_value_tokens)
            rules.append(
                _rule(
                    field,
                    "not_invalid_token",
                    f"{field.name} 不可使用無效值 token：{field.invalid_value_tokens}",
                    [("不是無效值 token", f"{column} NOT IN ({values})")],
                    [("是無效值 token", f"{column} IN ({values})")],
                )
            )

        if field.dtype == DType.string:
            if field.unique:
                rules.append(
                    _rule(
                        field,
                        "unique",
                        f"{field.name} 的非 null 值不可重複",
                        [("值未重複", f"COUNT(*) OVER (PARTITION BY {column}) = 1")],
                        [("值重複", f"COUNT(*) OVER (PARTITION BY {column}) > 1")],
                    )
                )
            if field.allow_empty_string is False:
                rules.append(
                    _rule(
                        field,
                        "not_empty",
                        f"{field.name} 不可為空字串或全空白",
                        [("字串有內容", f"TRIM({column}) <> ''")],
                        [("字串為空", f"TRIM({column}) = ''")],
                    )
                )
            if field.enum_values:
                values = ", ".join(_literal(value) for value in field.enum_values)
                rules.append(
                    _rule(
                        field,
                        "allowed_values",
                        f"{field.name} 只能是：{field.enum_values}",
                        [("值在允許清單", f"{column} IN ({values})")],
                        [("值不在允許清單", f"{column} NOT IN ({values})")],
                    )
                )
            if field.pattern:
                pattern = _literal(field.pattern)
                rules.append(
                    _rule(
                        field,
                        "pattern",
                        f"{field.name} 必須符合正規表示式：{field.pattern}",
                        [("格式符合", f"REGEXP_LIKE({column}, {pattern})")],
                        [("格式不符合", f"NOT REGEXP_LIKE({column}, {pattern})")],
                    )
                )

        if field.dtype in {DType.int_, DType.float_} and (
            field.min_value is not None or field.max_value is not None
        ):
            conditions: list[str] = []
            failing: list[tuple[str, str]] = []
            if field.min_value is not None:
                conditions.append(f"{column} >= {_literal(field.min_value)}")
                failing.append(("小於下界", f"{column} < {_literal(field.min_value)}"))
            if field.max_value is not None:
                conditions.append(f"{column} <= {_literal(field.max_value)}")
                failing.append(("大於上界", f"{column} > {_literal(field.max_value)}"))
            rules.append(
                _rule(
                    field,
                    "range",
                    f"{field.name} 必須符合範圍：" + " AND ".join(conditions),
                    [("位於允許範圍", " AND ".join(conditions))],
                    failing,
                )
            )

        if field.dtype == DType.datetime_ and (
            field.datetime_after is not None or field.datetime_before is not None
        ):
            conditions = []
            failing = []
            if field.datetime_after is not None:
                conditions.append(f"{column} >= {_literal(field.datetime_after)}")
                failing.append(("早於下界", f"{column} < {_literal(field.datetime_after)}"))
            if field.datetime_before is not None:
                conditions.append(f"{column} <= {_literal(field.datetime_before)}")
                failing.append(("晚於上界", f"{column} > {_literal(field.datetime_before)}"))
            rules.append(
                _rule(
                    field,
                    "datetime_range",
                    f"{field.name} 必須符合時間範圍：" + " AND ".join(conditions),
                    [("位於允許時間範圍", " AND ".join(conditions))],
                    failing,
                )
            )
        if field.dtype == DType.datetime_ and field.expected_datetime_format:
            format_literal = _literal(field.expected_datetime_format)
            expression = f"TRY(DATE_PARSE({column}, {format_literal})) IS NOT NULL"
            rules.append(
                _rule(
                    field,
                    "datetime_format",
                    f"{field.name} 必須符合 datetime 格式：{field.expected_datetime_format}",
                    [("格式正確", expression)],
                    [("格式錯誤", f"NOT ({expression})")],
                )
            )
    return rules


def _validate_text(value: str, location: str, max_length: int) -> None:
    if not value.strip():
        raise ValueError(f"{location} 不可為空或只有空白")
    if len(value) > max_length:
        raise ValueError(f"{location} 長度不可超過 {max_length}")
    restricted = [
        f"U+{ord(char):04X}"
        for char in value
        if unicodedata.category(char) in _RESTRICTED_TEXT_CATEGORIES
    ]
    if restricted:
        chars = ", ".join(sorted(set(restricted)))
        raise ValueError(f"{location} 包含不允許的控制或不可見字元：{chars}")


def _validate_row_rule(rule: ValidationRule, index: int) -> None:
    prefix = f"row_rules[{index}]"
    if len(rule.id) > _MAX_ID_LENGTH or not _ROW_RULE_ID.fullmatch(rule.id):
        raise ValueError(
            f"{prefix}.id 格式錯誤；必須以 row. 開頭，且各段只能使用英數字或底線，"
            "段落可用單一 . 或 - 分隔"
        )
    if len(rule.columns) < 2:
        raise ValueError(f"{prefix}.columns 必須至少包含兩個欄位")

    _validate_text(rule.desc, f"{prefix}.desc", _MAX_DESCRIPTION_LENGTH)
    for column_index, column in enumerate(rule.columns):
        _validate_text(
            column,
            f"{prefix}.columns[{column_index}]",
            _MAX_COLUMN_NAME_LENGTH,
        )
    for case_type, cases in (
        ("pass", rule.examples.pass_cases),
        ("fail", rule.examples.fail_cases),
    ):
        for case_index, case in enumerate(cases):
            _validate_text(
                case.name,
                f"{prefix}.examples.{case_type}[{case_index}].name",
                _MAX_EXAMPLE_NAME_LENGTH,
            )
            _validate_text(
                case.sql,
                f"{prefix}.examples.{case_type}[{case_index}].sql",
                _MAX_EXAMPLE_SQL_LENGTH,
            )


def parse_row_rules(raw_json: str) -> list[ValidationRule]:
    """解析 row rule JSON，並將所有格式與文字限制錯誤統一為 ValueError。"""
    if not isinstance(raw_json, str):
        raise ValueError("row_rules_json 必須是字串")
    if len(raw_json) > _MAX_RAW_JSON_LENGTH:
        raise ValueError(f"row_rules_json 長度不可超過 {_MAX_RAW_JSON_LENGTH}")
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"row_rules_json 不是合法的 JSON：{exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("row_rules_json 最外層必須是 array")
    if len(raw) > _MAX_ROW_RULES:
        raise ValueError(f"row_rules 最多 {_MAX_ROW_RULES} 條")

    try:
        rules = TypeAdapter(list[ValidationRule]).validate_python(raw)
    except Exception as exc:
        raise ValueError(f"row_rules 格式不符合規範：{exc}") from exc

    ids = [rule.id for rule in rules]
    if len(ids) != len(set(ids)):
        duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
        raise ValueError(f"row_rules 不可包含重複 id：{duplicates}")
    for index, rule in enumerate(rules):
        _validate_row_rule(rule, index)
    return rules


def build_validation_rules(
    dataset_urn: str,
    field_spec: FieldSpec,
    col_rules: list[ValidationRule],
    row_rules: list[ValidationRule],
) -> ValidationRules:
    """將有效的 col_rules 與 row_rules 封裝成正式 ValidationRules。"""
    return ValidationRules(
        dataset=DatasetRef(urn=dataset_urn, table_name=field_spec.table_name),
        input_schema=[
            InputColumn(name=field.name, dtype=field.dtype) for field in field_spec.fields
        ],
        col_rules=col_rules,
        row_rules=row_rules,
    )
