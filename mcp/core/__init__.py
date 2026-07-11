"""
MCP Server 核心邏輯模組

此模組包含 Data Validation Agent 的核心功能:
- datahub_client: 呼叫 DataHub GraphQL API 取得 dataset schema
- mock_data: 依 field_spec 產生 production-like mock data
- validation_suite: 依 field_spec 組裝 Great Expectations Expectation Suite
- models: field_spec 的 Pydantic 模型定義
"""

from .datahub_client import DataHubError, fetch_table_schema
from .mock_data import generate_mock_csv
from .models import parse_field_spec, FieldSpec, FieldSpecField, DType, TableLevelChecks
from .validation_suite import build_expectation_suite

__all__ = [
    "DataHubError",
    "fetch_table_schema",
    "generate_mock_csv",
    "parse_field_spec",
    "FieldSpec",
    "FieldSpecField",
    "DType",
    "TableLevelChecks",
    "build_expectation_suite",
]