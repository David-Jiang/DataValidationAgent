"""
field_spec 的 Pydantic 模型，作為 col_rules 的輸入與實作來源。
任何不符合此結構的 field_spec 都會在工具入口被拒絕，並回傳明確錯誤訊息。
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DType(str, Enum):
    string = "string"
    int_ = "int"
    float_ = "float"
    datetime_ = "datetime"
    boolean = "boolean"


class FieldSpecField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    dtype: DType
    nullable: bool
    unique: Optional[bool] = None

    allow_empty_string: Optional[bool] = None
    enum_values: Optional[list[str]] = None
    pattern: Optional[str] = None

    min_value: Optional[float] = None
    max_value: Optional[float] = None

    datetime_after: Optional[str] = None
    datetime_before: Optional[str] = None
    expected_datetime_format: Optional[str] = None

    invalid_value_tokens: list[str]

    confidence: Literal["high", "medium", "low"]
    source: Literal["upstream_schema", "discussed_with_user"]

    @field_validator("invalid_value_tokens")
    @classmethod
    def check_unique_invalid_value_tokens(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("invalid_value_tokens 不可包含重複值")
        return v

    @model_validator(mode="after")
    def check_type_specific_fields(self) -> "FieldSpecField":
        fields_set = self.model_fields_set
        string_fields = {"unique", "allow_empty_string", "enum_values", "pattern"}
        numeric_fields = {"min_value", "max_value"}
        datetime_fields = {"datetime_after", "datetime_before", "expected_datetime_format"}

        if self.dtype == DType.string:
            missing = string_fields - fields_set
            if missing:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 string,缺少 string 專屬屬性: {sorted(missing)}"
                )
            forbidden = (numeric_fields | datetime_fields) & fields_set
            if forbidden:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 string,"
                    f"不應出現 numeric/datetime 專屬屬性: {sorted(forbidden)}"
                )
        elif self.dtype in (DType.int_, DType.float_):
            missing = numeric_fields - fields_set
            if missing:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 {self.dtype.value},"
                    f"缺少 numeric 專屬屬性: {sorted(missing)}"
                )
            forbidden = (string_fields | datetime_fields) & fields_set
            if forbidden:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 {self.dtype.value},"
                    f"不應出現 string/datetime 專屬屬性: {sorted(forbidden)}"
                )
            if self.dtype == DType.int_:
                for attr in numeric_fields:
                    value = getattr(self, attr)
                    if value is not None and not float(value).is_integer():
                        raise ValueError(
                            f"欄位 '{self.name}' dtype 為 int,{attr} 必須是 integer 或 null"
                        )
            if (
                self.min_value is not None
                and self.max_value is not None
                and self.min_value > self.max_value
            ):
                raise ValueError(f"欄位 '{self.name}' min_value 不可大於 max_value")
        elif self.dtype == DType.datetime_:
            missing = datetime_fields - fields_set
            if missing:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 datetime,"
                    f"缺少 datetime 專屬屬性: {sorted(missing)}"
                )
            forbidden = (string_fields | numeric_fields) & fields_set
            if forbidden:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 datetime,"
                    f"不應出現 string/numeric 專屬屬性: {sorted(forbidden)}"
                )
        else:
            forbidden = (string_fields | numeric_fields | datetime_fields) & fields_set
            if forbidden:
                raise ValueError(
                    f"欄位 '{self.name}' dtype 為 boolean,"
                    f"不應出現型別專屬屬性: {sorted(forbidden)}"
                )
        return self


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
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
