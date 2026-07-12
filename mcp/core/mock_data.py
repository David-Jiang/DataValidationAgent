"""依照 field_spec 產生可滿足欄位規則的正向 mock data。"""
from __future__ import annotations

import io
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pandas as pd
import rstr
from faker import Faker

from .models import DType, FieldSpec, FieldSpecField

fake = Faker()

_MAX_ATTEMPTS_PER_VALUE = 200
_DEFAULT_NUMERIC_SPAN = 10_000
_DEFAULT_DATETIME_SPAN = timedelta(days=3650)


def _constraint_error(field: FieldSpecField, message: str) -> ValueError:
    return ValueError(f"欄位 '{field.name}' 無法產生符合 field_spec 的 mock data: {message}")


def _is_invalid_token(field: FieldSpecField, value: Any) -> bool:
    return str(value) in set(field.invalid_value_tokens)


def _generate_with_retry(
    field: FieldSpecField,
    row_count: int,
    factory: Callable[[], Any],
    validator: Callable[[Any], bool],
) -> list[Any]:
    values: list[Any] = []
    seen: set[Any] = set()

    for _ in range(row_count):
        for _attempt in range(_MAX_ATTEMPTS_PER_VALUE):
            value = factory()
            if not validator(value):
                continue
            if field.unique and value in seen:
                continue
            values.append(value)
            seen.add(value)
            break
        else:
            uniqueness = "且保持 unique" if field.unique else ""
            raise _constraint_error(
                field,
                f"在 {_MAX_ATTEMPTS_PER_VALUE} 次嘗試內無法產生合法值{uniqueness}；"
                "請降低 row_count 或放寬 enum、pattern、range 等規則",
            )

    return values


def _generate_string_values(field: FieldSpecField, row_count: int) -> list[str]:
    try:
        compiled_pattern = re.compile(field.pattern) if field.pattern else None
    except re.error as exc:
        raise _constraint_error(field, f"pattern 不是合法的 regular expression: {exc}") from exc

    def is_allowed(value: str) -> bool:
        if field.allow_empty_string is False and value == "":
            return False
        if _is_invalid_token(field, value):
            return False
        return compiled_pattern.fullmatch(value) is not None if compiled_pattern else True

    if field.enum_values is not None:
        candidates = [value for value in field.enum_values if is_allowed(value)]
        if not candidates:
            raise _constraint_error(field, "enum_values 沒有同時符合 pattern、空字串與 invalid token 規則的值")
        if field.unique:
            if len(candidates) < row_count:
                raise _constraint_error(
                    field,
                    f"unique enum 只有 {len(candidates)} 個可用值，無法產生 {row_count} 筆",
                )
            return random.sample(candidates, row_count)
        return random.choices(candidates, k=row_count)

    if compiled_pattern:
        factory = lambda: rstr.xeger(field.pattern or "")
    elif field.unique:
        counter = iter(range(row_count * _MAX_ATTEMPTS_PER_VALUE))
        factory = lambda: f"{fake.word()}_{next(counter)}"
    else:
        factory = fake.word

    return _generate_with_retry(field, row_count, factory, is_allowed)


def _integer_bounds(field: FieldSpecField, row_count: int) -> tuple[int, int]:
    span = max(_DEFAULT_NUMERIC_SPAN, row_count * 10)
    if field.min_value is None and field.max_value is None:
        return 0, span
    if field.min_value is None:
        hi = int(field.max_value)  # type: ignore[arg-type]
        return hi - span, hi
    if field.max_value is None:
        lo = int(field.min_value)
        return lo, lo + span
    return int(field.min_value), int(field.max_value)


def _generate_int_values(field: FieldSpecField, row_count: int) -> list[int]:
    lo, hi = _integer_bounds(field, row_count)
    forbidden = {
        int(token)
        for token in field.invalid_value_tokens
        if token.lstrip("-").isdigit()
        and str(int(token)) == token
        and lo <= int(token) <= hi
    }
    if hi - lo + 1 - len(forbidden) < 1:
        raise _constraint_error(field, "numeric range 內沒有避開 invalid_value_tokens 的可用 integer")
    return _generate_with_retry(
        field,
        row_count,
        lambda: random.randint(lo, hi),
        lambda value: value not in forbidden,
    )


def _float_bounds(field: FieldSpecField) -> tuple[float, float]:
    if field.min_value is None and field.max_value is None:
        return 0.0, float(_DEFAULT_NUMERIC_SPAN)
    if field.min_value is None:
        hi = float(field.max_value)  # type: ignore[arg-type]
        return hi - _DEFAULT_NUMERIC_SPAN, hi
    if field.max_value is None:
        lo = float(field.min_value)
        return lo, lo + _DEFAULT_NUMERIC_SPAN
    return float(field.min_value), float(field.max_value)


def _generate_float_values(field: FieldSpecField, row_count: int) -> list[float]:
    lo, hi = _float_bounds(field)
    return _generate_with_retry(
        field,
        row_count,
        lambda: random.uniform(lo, hi),
        lambda value: not _is_invalid_token(field, value),
    )


def _parse_datetime_bound(field: FieldSpecField, raw: str, property_name: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _constraint_error(field, f"{property_name} 必須是 ISO-8601 datetime: {raw}") from exc
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _datetime_bounds(field: FieldSpecField) -> tuple[datetime, datetime]:
    start = (
        _parse_datetime_bound(field, field.datetime_after, "datetime_after")
        if field.datetime_after
        else None
    )
    end = (
        _parse_datetime_bound(field, field.datetime_before, "datetime_before")
        if field.datetime_before
        else None
    )

    if start is None and end is None:
        end = datetime.now(timezone.utc)
        start = end - _DEFAULT_DATETIME_SPAN
    elif start is None:
        start = end - _DEFAULT_DATETIME_SPAN  # type: ignore[operator]
    elif end is None:
        end = max(datetime.now(timezone.utc), start + _DEFAULT_DATETIME_SPAN)

    assert start is not None and end is not None
    if start > end:
        raise _constraint_error(field, "datetime_after 不可晚於 datetime_before")
    return start, end


def _generate_datetime_values(field: FieldSpecField, row_count: int) -> list[str]:
    start, end = _datetime_bounds(field)
    fmt = field.expected_datetime_format or "%Y-%m-%dT%H:%M:%SZ"
    total_seconds = (end - start).total_seconds()

    def factory() -> str:
        dt = start + timedelta(seconds=random.uniform(0, total_seconds)) if total_seconds else start
        return dt.strftime(fmt)

    return _generate_with_retry(
        field,
        row_count,
        factory,
        lambda value: not _is_invalid_token(field, value),
    )


def _generate_boolean_values(field: FieldSpecField, row_count: int) -> list[bool]:
    candidates = [value for value in (True, False) if not _is_invalid_token(field, value)]
    if not candidates:
        raise _constraint_error(field, "True 與 False 都被 invalid_value_tokens 排除")
    return random.choices(candidates, k=row_count)


def _generate_column(field: FieldSpecField, row_count: int) -> list[Any]:
    if field.dtype == DType.string:
        return _generate_string_values(field, row_count)
    if field.dtype == DType.int_:
        return _generate_int_values(field, row_count)
    if field.dtype == DType.float_:
        return _generate_float_values(field, row_count)
    if field.dtype == DType.datetime_:
        return _generate_datetime_values(field, row_count)
    if field.dtype == DType.boolean:
        return _generate_boolean_values(field, row_count)
    raise _constraint_error(field, f"不支援的 dtype: {field.dtype}")


def generate_mock_csv(field_spec: FieldSpec, row_count: int = 100) -> str:
    """產生只包含合法值的 CSV；無法同時滿足規則時以 ValueError 明確拒絕。"""
    if row_count < 1:
        raise ValueError(f"row_count 必須是正整數，目前為 {row_count}")

    columns = {
        field.name: _generate_column(field, row_count)
        for field in field_spec.fields
    }
    dataframe = pd.DataFrame(columns)
    buffer = io.StringIO()
    dataframe.to_csv(buffer, index=False)
    return buffer.getvalue()
