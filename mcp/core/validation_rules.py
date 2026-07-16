"""ValidationRules contract 與 executable/test implementation mapping。"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import textwrap
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from .field_spec import DType, FieldSpec


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


class RowRuleImplementation(BaseModel):
    """Agent 依已確認 row rule 語意撰寫的 pure Python function body。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^row\.[A-Za-z0-9_.-]+$")
    body: str = Field(min_length=1)


class RuleFixture(BaseModel):
    """一組具名、非空的 concrete test rows。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    rows: list[dict[str, Any]] = Field(min_length=1)


class RuleTestCases(BaseModel):
    """一條 col/row rule 的 passing 與 failing fixtures。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^(col|row)\.[A-Za-z0-9_.-]+$")
    pass_cases: list[RuleFixture] = Field(min_length=1)
    fail_cases: list[RuleFixture] = Field(min_length=1)


class ValidationRules(BaseModel):
    """
    正式 validation contract。

    implementation_bodies 與 test_cases 是 artifact rendering context，刻意從 JSON/hash
    serialization 排除，避免 executable code 與 concrete rows 汙染正式規則契約。
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = "1.0"
    dataset: DatasetRef
    input_schema: list[InputColumn] = Field(min_length=1)
    col_rules: list[ValidationRule]
    row_rules: list[ValidationRule]
    implementation_bodies: dict[str, str] = Field(
        default_factory=dict, exclude=True, repr=False
    )
    test_cases: list[RuleTestCases] = Field(default_factory=list, exclude=True, repr=False)

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

        expected_ids = set(ids)
        if self.implementation_bodies:
            _ensure_exact_ids(
                "rule implementations",
                expected_ids,
                list(self.implementation_bodies),
            )
        if self.test_cases:
            _ensure_exact_ids(
                "rule test cases",
                expected_ids,
                [case.id for case in self.test_cases],
            )
        return self

    @staticmethod
    def _ensure_known_columns(rule: ValidationRule, known: set[str]) -> None:
        unknown = [column for column in rule.columns if column not in known]
        if unknown:
            raise ValueError(f"rule {rule.id} 引用了不存在的欄位：{unknown}")


def _ensure_exact_ids(label: str, expected: set[str], submitted: list[str]) -> None:
    if len(submitted) != len(set(submitted)):
        raise ValueError(f"{label} 不可包含重複 id")
    actual = set(submitted)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label} 不完整；missing={missing}, extra={extra}")


def _column_key(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_.-") or "column"
    if safe != name:
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        safe = f"{safe}.{digest}"
    return safe


def _rebuild_rules(rules: ValidationRules, **rendering_context: object) -> ValidationRules:
    data = rules.model_dump(mode="python")
    data["implementation_bodies"] = rules.implementation_bodies
    data["test_cases"] = rules.test_cases
    data.update(rendering_context)
    return ValidationRules.model_validate(data)


def _build_col_rule_bodies(field_spec: FieldSpec) -> dict[str, str]:
    bodies: dict[str, str] = {}
    for field in field_spec.fields:
        key = _column_key(field.name)
        column = repr(field.name)
        prefix = f"col.{key}"

        if field.nullable is False:
            bodies[f"{prefix}.not_null"] = f"return df[{column}].notna()"

        if field.invalid_value_tokens:
            bodies[f"{prefix}.not_invalid_token"] = (
                f"return ~df[{column}].isin({field.invalid_value_tokens!r})"
            )

        if field.dtype == DType.string:
            if field.unique:
                bodies[f"{prefix}.unique"] = "\n".join(
                    [
                        f"series = df[{column}]",
                        "return series.isna() | ~series.duplicated(keep=False)",
                    ]
                )
            if field.allow_empty_string is False:
                bodies[f"{prefix}.not_empty"] = "\n".join(
                    [
                        f"series = df[{column}]",
                        'text = series.astype("string")',
                        'return series.isna() | ~text.str.fullmatch(r"\\s*", na=False)',
                    ]
                )
            if field.enum_values:
                bodies[f"{prefix}.allowed_values"] = "\n".join(
                    [
                        f"series = df[{column}]",
                        f"return series.isna() | series.isin({field.enum_values!r})",
                    ]
                )
            if field.pattern:
                bodies[f"{prefix}.pattern"] = "\n".join(
                    [
                        f"series = df[{column}]",
                        'text = series.astype("string")',
                        f"return series.isna() | text.str.fullmatch({field.pattern!r}, na=False)",
                    ]
                )

        if field.dtype in {DType.int_, DType.float_} and (
            field.min_value is not None or field.max_value is not None
        ):
            comparisons: list[str] = []
            if field.min_value is not None:
                comparisons.append(f"numeric.ge({field.min_value!r})")
            if field.max_value is not None:
                comparisons.append(f"numeric.le({field.max_value!r})")
            bodies[f"{prefix}.range"] = "\n".join(
                [
                    f"series = df[{column}]",
                    'numeric = pd.to_numeric(series, errors="coerce")',
                    f"within = {' & '.join(comparisons)}",
                    "return series.isna() | within.fillna(False)",
                ]
            )

        if field.dtype == DType.datetime_ and (
            field.datetime_after is not None or field.datetime_before is not None
        ):
            comparisons = []
            if field.datetime_after is not None:
                comparisons.append(
                    f"parsed.ge(pd.to_datetime({field.datetime_after!r}, utc=True))"
                )
            if field.datetime_before is not None:
                comparisons.append(
                    f"parsed.le(pd.to_datetime({field.datetime_before!r}, utc=True))"
                )
            bodies[f"{prefix}.datetime_range"] = "\n".join(
                [
                    f"series = df[{column}]",
                    'parsed = pd.to_datetime(series, errors="coerce", utc=True)',
                    f"within = {' & '.join(comparisons)}",
                    "return series.isna() | within.fillna(False)",
                ]
            )
        if field.dtype == DType.datetime_ and field.expected_datetime_format:
            bodies[f"{prefix}.datetime_format"] = "\n".join(
                [
                    f"series = df[{column}]",
                    (
                        'parsed = pd.to_datetime(series, errors="coerce", '
                        f"format={field.expected_datetime_format!r})"
                    ),
                    "return series.isna() | parsed.notna()",
                ]
            )
    return bodies


_FORBIDDEN_AST = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Lambda,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
_FORBIDDEN_NAMES = {
    "__builtins__",
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}
_FORBIDDEN_ATTRIBUTES = {
    "eval",
    "pipe",
    "query",
    "read_clipboard",
    "read_csv",
    "read_excel",
    "read_feather",
    "read_fwf",
    "read_html",
    "read_json",
    "read_orc",
    "read_parquet",
    "read_pickle",
    "read_sas",
    "read_spss",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_stata",
    "read_table",
    "read_xml",
    "to_clipboard",
    "to_csv",
    "to_excel",
    "to_feather",
    "to_gbq",
    "to_hdf",
    "to_html",
    "to_json",
    "to_latex",
    "to_markdown",
    "to_orc",
    "to_parquet",
    "to_pickle",
    "to_sql",
    "to_stata",
    "to_xml",
}


def validate_row_rule_body(rule_id: str, body: str) -> str:
    """以 AST denylist 驗證 body，通過後回傳去除首尾空白的內容。"""
    source = "def _generated_rule(df):\n" + textwrap.indent(body.strip(), "    ")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"row rule {rule_id} 的 Python body 語法錯誤：{exc}") from exc

    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    if not any(isinstance(node, ast.Return) for node in ast.walk(function)):
        raise ValueError(f"row rule {rule_id} 必須 return boolean Series")

    for node in ast.walk(function):
        if node is function:
            continue
        if isinstance(node, _FORBIDDEN_AST) or isinstance(node, ast.FunctionDef):
            raise ValueError(
                f"row rule {rule_id} 包含不允許的 Python 語法：{type(node).__name__}"
            )
        if isinstance(node, ast.Name) and (
            node.id.startswith("__") or node.id in _FORBIDDEN_NAMES
        ):
            raise ValueError(f"row rule {rule_id} 使用了不允許的名稱：{node.id}")
        if isinstance(node, ast.Attribute) and (
            node.attr.startswith("__") or node.attr in _FORBIDDEN_ATTRIBUTES
        ):
            raise ValueError(f"row rule {rule_id} 使用了不允許的屬性：{node.attr}")
    return body.strip()


def _parse_row_impl_code(raw_json: str) -> list[RowRuleImplementation]:
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"row_impl_code_json 不是合法的 JSON：{exc}") from exc
    try:
        return TypeAdapter(list[RowRuleImplementation]).validate_python(raw)
    except Exception as exc:
        raise ValueError(f"row implementation code 格式錯誤：{exc}") from exc


def validated_row_rule_bodies(
    expected_ids: set[str],
    implementations: list[RowRuleImplementation],
) -> dict[str, str]:
    submitted_ids = [item.id for item in implementations]
    _ensure_exact_ids("row rule implementations", expected_ids, submitted_ids)
    return {
        item.id: validate_row_rule_body(item.id, item.body) for item in implementations
    }


def build_impl_code(
    rules: ValidationRules,
    field_spec: FieldSpec,
    row_impl_code_json: str,
) -> ValidationRules:
    """解析、驗證並整合 col/row implementations，回傳可 render code 的 rules copy。"""
    implementations = _parse_row_impl_code(row_impl_code_json)
    col_bodies = _build_col_rule_bodies(field_spec)
    expected_col_ids = {rule.id for rule in rules.col_rules}
    _ensure_exact_ids("col rule implementations", expected_col_ids, list(col_bodies))

    expected_row_ids = {rule.id for rule in rules.row_rules}
    row_bodies = validated_row_rule_bodies(expected_row_ids, implementations)
    return _rebuild_rules(
        rules,
        implementation_bodies={**col_bodies, **row_bodies},
    )


def _parse_row_test_code(raw_json: str) -> list[RuleTestCases]:
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"row_test_code_json 不是合法的 JSON：{exc}") from exc
    try:
        return TypeAdapter(list[RuleTestCases]).validate_python(raw)
    except Exception as exc:
        raise ValueError(f"row test code 格式錯誤：{exc}") from exc


def build_test_code(
    rules: ValidationRules,
    row_test_code_json: str,
) -> ValidationRules:
    """解析並驗證所有 col/row fixtures，回傳可 render pytest 的 rules copy。"""
    test_cases = _parse_row_test_code(row_test_code_json)
    expected_ids = {rule.id for rule in [*rules.col_rules, *rules.row_rules]}
    _ensure_exact_ids("rule test cases", expected_ids, [case.id for case in test_cases])
    return _rebuild_rules(rules, test_cases=test_cases)


def canonical_validation_rules(rules: ValidationRules) -> str:
    return json.dumps(
        rules.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
