"""
Data Validation Agent MCP Server

提供四個工具:
- get_table_schema    : 呼叫 DataHub API 取得上游原始 schema
- get_field_spec       : 回傳 field_spec 的正式 JSON Schema 定義
- gen_mock_data         : 依 field_spec 產生 mock data (CSV)
- gen_validation_suite  : 依 field_spec 產生 Great Expectations Validation Suite (JSON)

設計原則:本 Server 完全 stateless,不持有任何討論狀態或版本歷史,
field_spec 草稿的存取由 client 端 (Claude Code) 自行管理。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from datahub_client import DataHubError, fetch_table_schema
from mock_data import generate_mock_csv
from models import parse_field_spec
from validation_suite import build_expectation_suite

mcp = FastMCP(
    "data-validation-agent",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "field_spec.schema.json"


@mcp.tool()
def get_table_schema(dataset_urn: str) -> str:
    """
    呼叫 DataHub API,取得上游 table 的原始 schema(欄位名稱、型別、description)。
    dataset_urn: DataHub dataset 的 URN,例如 'urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)'
    回傳 JSON 字串。失敗時回傳以 ERROR: 開頭的錯誤訊息,說明原因。
    """
    try:
        schema = fetch_table_schema(dataset_urn)
        return json.dumps(schema, ensure_ascii=False, indent=2)
    except DataHubError as e:
        return f"ERROR: {e}"


@mcp.tool()
def get_field_spec() -> str:
    """
    回傳 field_spec 的正式 JSON Schema 定義。
    在開始與使用者討論欄位規則、或產生 field_spec 之前,應先呼叫此工具確認格式規範,
    此 schema 是格式的單一事實來源,優先於任何文件中對結構的描述。
    """
    try:
        return _SCHEMA_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "ERROR: field_spec schema 檔案未找到,請確認 Server 部署是否正確包含 schemas/field_spec.schema.json"


@mcp.tool()
def gen_mock_data(field_spec_json: str, row_count: int = 100) -> str:
    """
    根據確認後的 field_spec(JSON 字串,需符合 get_field_spec 回傳的結構)產生 mock data。
    row_count: 要產生的資料筆數,預設 100。
    回傳 CSV 內容字串(不落地寫檔,由使用者決定要不要存檔)。
    失敗時回傳以 ERROR: 開頭的錯誤訊息,說明 field_spec 哪裡不符合規範。
    """
    try:
        spec = parse_field_spec(field_spec_json)
    except ValueError as e:
        return f"ERROR: {e}"

    try:
        return generate_mock_csv(spec, row_count=row_count)
    except Exception as e:
        return f"ERROR: 產生 mock data 時發生例外: {e}"


@mcp.tool()
def gen_validation_suite(table_name: str, field_spec_json: str) -> str:
    """
    根據確認後的 field_spec(JSON 字串,需符合 get_field_spec 回傳的結構),
    使用 great_expectations 套件產生 Validation Suite。
    回傳 validation_suite.json 內容字串。
    失敗時回傳以 ERROR: 開頭的錯誤訊息,說明 field_spec 哪裡不符合規範。
    """
    try:
        spec = parse_field_spec(field_spec_json)
    except ValueError as e:
        return f"ERROR: {e}"

    try:
        suite_dict = build_expectation_suite(table_name, spec)
        return json.dumps(suite_dict, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"ERROR: 產生 validation suite 時發生例外: {e}"


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
