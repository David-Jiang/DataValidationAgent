"""
依照 field_spec 產生 production-like mock data。
策略:優先依 semantic_tag 用對應的 Faker provider 生成更貼近真實樣貌的值;
沒有對應 semantic_tag 處理器時,退回依 dtype 生成通用假值。
"""
from __future__ import annotations

import io
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from faker import Faker

from models import FieldSpec, FieldSpecField, DType

fake = Faker()

# semantic_tag -> 生成函式對照表。函式簽名一致,方便擴充。
_SEMANTIC_GENERATORS = {
    "uuid": lambda f: str(uuid.uuid4()),
    "email": lambda f: fake.email(),
    "phone": lambda f: fake.phone_number(),
    "phone_tw": lambda f: "09" + "".join(random.choices(string.digits, k=8)),
    "currency": lambda f: round(random.uniform(f.min_value or 0, f.max_value or 10000), 2),
    "timestamp": lambda f: _random_datetime(f),
    "free_text": lambda f: fake.sentence(),
    "enum": lambda f: random.choice(f.enum_values) if f.enum_values else fake.word(),
    "name": lambda f: fake.name(),
}


def _random_datetime(f: FieldSpecField) -> str:
    fmt = f.expected_datetime_format or "%Y-%m-%dT%H:%M:%SZ"
    start = (
        datetime.fromisoformat(f.datetime_after.replace("Z", "+00:00"))
        if f.datetime_after
        else datetime(2020, 1, 1, tzinfo=timezone.utc)
    )
    end = (
        datetime.fromisoformat(f.datetime_before.replace("Z", "+00:00"))
        if f.datetime_before
        else datetime.now(timezone.utc)
    )
    if end <= start:
        end = start + timedelta(days=1)
    delta = end - start
    rand_seconds = random.uniform(0, delta.total_seconds())
    dt = start + timedelta(seconds=rand_seconds)
    return dt.strftime(fmt)


def _generate_value(f: FieldSpecField) -> Any:
    # null 機率:nullable 欄位有 5% 機率生成 null,模擬 production 的缺漏值情況
    if f.nullable and random.random() < 0.05:
        return None

    if f.enum_values:
        return random.choice(f.enum_values)

    if f.semantic_tag and f.semantic_tag in _SEMANTIC_GENERATORS:
        return _SEMANTIC_GENERATORS[f.semantic_tag](f)

    # 退回依 dtype 生成通用值
    if f.dtype == DType.string:
        val = fake.word()
        if f.allow_empty_string is False and val == "":
            val = fake.word()
        return val
    if f.dtype == DType.int_:
        lo = int(f.min_value) if f.min_value is not None else 0
        hi = int(f.max_value) if f.max_value is not None else lo + 10000
        return random.randint(lo, hi)
    if f.dtype == DType.float_:
        lo = f.min_value if f.min_value is not None else 0.0
        hi = f.max_value if f.max_value is not None else lo + 10000.0
        return round(random.uniform(lo, hi), 2)
    if f.dtype == DType.datetime_:
        return _random_datetime(f)
    if f.dtype == DType.boolean:
        return random.choice([True, False])
    return None


def generate_mock_csv(field_spec: FieldSpec, row_count: int = 100) -> str:
    """產生 mock data,回傳 CSV 內容字串(不落地寫檔,由呼叫端/使用者決定要不要存)"""
    rows = []
    for _ in range(row_count):
        row = {f.name: _generate_value(f) for f in field_spec.fields}
        rows.append(row)

    df = pd.DataFrame(rows)

    # 確保 unique 欄位真的唯一(簡單做法:重複值用 uuid 後綴打散,POC 階段足夠)
    for f in field_spec.fields:
        if f.unique and df[f.name].duplicated().any():
            df[f.name] = [f"{v}-{uuid.uuid4().hex[:6]}" if df[f.name].duplicated()[i] else v
                           for i, v in enumerate(df[f.name])]

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
