"""
field_spec 的 Pydantic 模型,作為 gen_mock_data / gen_validation_suite 的輸入驗證層。
任何不符合此結構的 field_spec 都會在工具入口被拒絕,並回傳明確錯誤訊息。
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DType(str, Enum):
    string = "string"
    int_ = "int"
    float_ = "float"
    datetime_ = "datetime"
    boolean = "boolean"


class FieldSpecField(BaseModel):
    name: str
    dtype: DType
    semantic_tag: Optional[str] = None
    nullable: bool
    unique: bool

    allow_empty_string: Optional[bool] = None
    enum_values: Optional[list[str]] = None
    pattern: Optional[str] = None

    min_value: Optional[float] = None
    max_value: Optional[float] = None

    datetime_after: Optional[str] = None
    datetime_before: Optional[str] = None
    expected_datetime_format: Optional[str] = None

    invalid_value_tokens: list[str] = Field(default_factory=list)

    confidence: Literal["high", "medium", "low"]
    source: Literal["upstream_schema", "discussed_with_user"]

    @model_validator(mode="after")
    def check_type_specific_fields(self) -> "FieldSpecField":
        if self.dtype != DType.string:
            if self.allow_empty_string is not None or self.pattern is not None:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 {self.dtype.value},"
                    f"不應設定 allow_empty_string 或 pattern(string 專屬屬性),請設為 null"
                )
        if self.dtype != DType.datetime_:
            if any([self.datetime_after, self.datetime_before, self.expected_datetime_format]):
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 {self.dtype.value},"
                    f"不應設定 datetime_after / datetime_before / expected_datetime_format,請設為 null"
                )
        if self.dtype not in (DType.int_, DType.float_):
            if self.min_value is not None or self.max_value is not None:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 {self.dtype.value},"
                    f"不應設定 min_value / max_value(int/float 專屬屬性),請設為 null"
                )
        return self


class TableLevelChecks(BaseModel):
    min_row_count: Optional[int] = None
    max_row_count: Optional[int] = None


class FieldSpec(BaseModel):
    table_name: str
    version: int = Field(ge=1)
    generated_at: Optional[str] = None
    based_on_upstream_schema_fetched_at: Optional[str] = None
    based_on_upstream_dataset_urn: Optional[str] = None
    change_note: Optional[str] = None
    table_level_checks: Optional[TableLevelChecks] = None
    fields: list[FieldSpecField] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def check_unique_field_names(cls, v: list[FieldSpecField]) -> list[FieldSpecField]:
        names = [f.name for f in v]
        if len(names) != len(set(names)):
            dupes = {n for n in names if names.count(n) > 1}
            raise ValueError(f"field_spec 裡有重複的欄位名稱: {dupes}")
        return v


def parse_field_spec(raw_json: str) -> FieldSpec:
    """
    將傳入的 JSON 字串解析並驗證成 FieldSpec。
    失敗時拋出帶有明確訊息的 ValueError,呼叫端應捕捉並回傳給 Claude 修正。
    """
    import json

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"field_spec 不是合法的 JSON: {e}") from e

    try:
        return FieldSpec(**data)
    except Exception as e:  # pydantic.ValidationError
        from pydantic import ValidationError

        if isinstance(e, ValidationError):
            lines = []
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err["loc"])
                lines.append(f"- {loc}: {err['msg']}")
            raise ValueError(
                "field_spec 格式不符合規範,請依下列問題修正後重新呼叫:\n" + "\n".join(lines)
            ) from e
        raise
