"""依照 field_spec 產生覆蓋驗證規則的全反向 mock data。"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import DType, FieldSpec, FieldSpecField

DEFAULT_ROW_COUNT = 100
MAX_ROW_COUNT = 1000


@dataclass(frozen=True)
class ViolationCase:
    """一個可注入 CSV 的欄位規則違規案例。"""

    field_name: str
    rule: str
    value: Any


def _constraint_error(field: FieldSpecField, message: str) -> ValueError:
    return ValueError(f"欄位 '{field.name}' 無法產生反向 mock data：{message}")


def _parse_datetime_bound(field: FieldSpecField, raw: str, property_name: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _constraint_error(field, f"{property_name} 必須是 ISO-8601 datetime：{raw}") from exc
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_iso_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _outside_enum(enum_values: list[str]) -> str:
    value = "__INVALID_ENUM__"
    while value in enum_values:
        value += "_X"
    return value


def _non_matching_string(field: FieldSpecField) -> str | None:
    if not field.pattern:
        return None
    try:
        pattern = re.compile(field.pattern)
    except re.error as exc:
        raise _constraint_error(field, f"pattern 不是合法的 regular expression：{exc}") from exc

    candidates = ["__INVALID_PATTERN__", "!", "0", " ", ""]
    return next((value for value in candidates if pattern.fullmatch(value) is None), None)


def _field_violation_cases(field: FieldSpecField) -> list[ViolationCase]:
    cases: list[ViolationCase] = []

    if field.nullable is False:
        cases.append(ViolationCase(field.name, "nullable", None))

    for token in field.invalid_value_tokens:
        cases.append(ViolationCase(field.name, "invalid_value_token", token))

    if field.dtype == DType.string:
        if field.unique:
            duplicate = ViolationCase(field.name, "unique", "__DUPLICATE__")
            cases.extend([duplicate, duplicate])
        if field.allow_empty_string is False:
            cases.append(ViolationCase(field.name, "allow_empty_string", " "))
        if field.enum_values:
            cases.append(
                ViolationCase(field.name, "enum_values", _outside_enum(field.enum_values))
            )
        non_match = _non_matching_string(field)
        if non_match is not None:
            cases.append(ViolationCase(field.name, "pattern", non_match))

    if field.dtype in {DType.int_, DType.float_}:
        step = 1 if field.dtype == DType.int_ else 1.0
        if field.min_value is not None:
            cases.append(ViolationCase(field.name, "min_value", field.min_value - step))
        if field.max_value is not None:
            cases.append(ViolationCase(field.name, "max_value", field.max_value + step))

    if field.dtype == DType.datetime_:
        if field.datetime_after:
            lower = _parse_datetime_bound(field, field.datetime_after, "datetime_after")
            cases.append(
                ViolationCase(
                    field.name,
                    "datetime_after",
                    _format_iso_datetime(lower - timedelta(seconds=1)),
                )
            )
        if field.datetime_before:
            upper = _parse_datetime_bound(field, field.datetime_before, "datetime_before")
            cases.append(
                ViolationCase(
                    field.name,
                    "datetime_before",
                    _format_iso_datetime(upper + timedelta(seconds=1)),
                )
            )
        if field.expected_datetime_format:
            cases.append(
                ViolationCase(field.name, "expected_datetime_format", "not-a-valid-datetime")
            )

    return cases


def build_violation_cases(field_spec: FieldSpec) -> list[ViolationCase]:
    """依 field 順序建立規則覆蓋清單；超過上限的案例由產生器截斷。"""
    return [case for field in field_spec.fields for case in _field_violation_cases(field)]


def _neutral_value(field: FieldSpecField, row_index: int) -> Any:
    if field.dtype == DType.string:
        if field.enum_values:
            return field.enum_values[row_index % len(field.enum_values)]
        return f"baseline_{field.name}_{row_index}"
    if field.dtype == DType.int_:
        return int(field.min_value if field.min_value is not None else 0)
    if field.dtype == DType.float_:
        return float(field.min_value if field.min_value is not None else 0.0)
    if field.dtype == DType.datetime_:
        if field.datetime_after:
            return field.datetime_after
        if field.datetime_before:
            return field.datetime_before
        return "2000-01-01T00:00:00Z"
    if field.dtype == DType.boolean:
        return True
    raise _constraint_error(field, f"不支援的 dtype：{field.dtype}")


def generate_mock_csv(field_spec: FieldSpec) -> str:
    """
    產生每列至少違反一條 field_spec 規則的 CSV。

    規則案例不超過 100 時循環補至 100 筆；超過時擴充至足以覆蓋所有案例，最多 1000 筆。
    超過 1000 的其餘案例直接截斷，不視為錯誤。
    """
    cases = build_violation_cases(field_spec)
    if not cases:
        raise ValueError("field_spec 沒有可產生反向資料的驗證條件")

    row_count = min(max(DEFAULT_ROW_COUNT, len(cases)), MAX_ROW_COUNT)
    field_names = [field.name for field in field_spec.fields]
    rows: list[dict[str, Any]] = []

    for row_index in range(row_count):
        row = {
            field.name: _neutral_value(field, row_index)
            for field in field_spec.fields
        }
        violation = cases[row_index % len(cases)]
        row[violation.field_name] = violation.value
        rows.append(row)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=field_names, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
