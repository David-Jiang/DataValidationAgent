"""將已確認的 field spec 與動態 row rules 正規化為 validation_rules.json。"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from .models import DType, FieldSpec, FieldSpecField


class DatasetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urn: str = Field(min_length=1)
    table_name: str = Field(min_length=1)


class InputColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    dtype: DType


class RuleExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    sql: str = Field(min_length=1)


class RuleExamples(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    pass_cases: list[RuleExample] = Field(alias="pass", min_length=1)
    fail_cases: list[RuleExample] = Field(alias="fail", min_length=1)


class ValidationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, pattern=r"^(col|row)\.[A-Za-z0-9_.-]+$")
    desc: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)
    examples: RuleExamples

    @field_validator("columns")
    @classmethod
    def columns_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("columns 不可包含重複欄位")
        return value


class ValidationRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = "1.0"
    dataset: DatasetRef
    input_schema: list[InputColumn] = Field(min_length=1)
    col_rules: list[ValidationRule]
    row_rules: list[ValidationRule]

    @model_validator(mode="after")
    def validate_rule_contract(self) -> "ValidationRules":
        column_names = [column.name for column in self.input_schema]
        if len(column_names) != len(set(column_names)):
            raise ValueError("input_schema 不可包含重複欄位")

        all_rules = [*self.col_rules, *self.row_rules]
        ids = [rule.id for rule in all_rules]
        if len(ids) != len(set(ids)):
            raise ValueError("col_rules 與 row_rules 的 id 必須全域唯一")

        known = set(column_names)
        for rule in self.col_rules:
            if not rule.id.startswith("col."):
                raise ValueError(f"col rule id 必須以 col. 開頭：{rule.id}")
            if len(rule.columns) != 1:
                raise ValueError(f"col rule 必須只引用一個欄位：{rule.id}")
            self._ensure_known_columns(rule, known)

        for rule in self.row_rules:
            if not rule.id.startswith("row."):
                raise ValueError(f"row rule id 必須以 row. 開頭：{rule.id}")
            if len(rule.columns) < 2:
                raise ValueError(f"row rule 必須引用至少兩個欄位：{rule.id}")
            self._ensure_known_columns(rule, known)
        return self

    @staticmethod
    def _ensure_known_columns(rule: ValidationRule, known: set[str]) -> None:
        unknown = [column for column in rule.columns if column not in known]
        if unknown:
            raise ValueError(f"rule {rule.id} 引用了不存在的欄位：{unknown}")


def parse_row_rules(raw_json: str) -> list[ValidationRule]:
    """解析 Agent 依使用者討論建立的 row rules。"""
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"row_rules_json 不是合法的 JSON：{exc}") from exc
    try:
        return TypeAdapter(list[ValidationRule]).validate_python(raw)
    except Exception as exc:
        raise ValueError(f"row_rules 格式不符合規範：{exc}") from exc


def _column_key(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_.-") or "column"
    if safe != name:
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        safe = f"{safe}.{digest}"
    return safe


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
    """依既有 field_spec contract 將每個啟用條件拆成獨立 col rule。"""
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


def build_validation_rules(
    dataset_urn: str,
    field_spec: FieldSpec,
    row_rules: list[ValidationRule],
) -> ValidationRules:
    return ValidationRules(
        dataset=DatasetRef(urn=dataset_urn, table_name=field_spec.table_name),
        input_schema=[
            InputColumn(name=field.name, dtype=field.dtype) for field in field_spec.fields
        ],
        col_rules=build_col_rules(field_spec),
        row_rules=row_rules,
    )


def canonical_validation_rules(rules: ValidationRules) -> str:
    return json.dumps(
        rules.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
