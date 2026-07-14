"""
MCP Server 核心邏輯模組

此模組包含 Data Validation Agent 的核心功能:
- datahub_client: 呼叫 DataHub GraphQL API 取得 dataset schema
- mock_data: 依 field_spec 產生覆蓋驗證規則的全反向 mock data
- field_spec_csv: 將正式版 field_spec 展開為 CSV
- validation_suite: 依 field_spec 組裝 Great Expectations Expectation Suite
- models: field_spec 的 Pydantic 模型定義
"""

from .datahub_client import DataHubError, fetch_table_schema
from .field_spec_csv import generate_field_spec_csv
from .mock_data import build_violation_cases, generate_mock_csv
from .models import parse_field_spec, FieldSpec, FieldSpecField, DType
from .validation_suite import build_expectation_suite
from .workflow import WorkflowError, WorkflowState, WorkflowStore, workflow_store

__all__ = [
    "DataHubError",
    "fetch_table_schema",
    "generate_field_spec_csv",
    "build_violation_cases",
    "generate_mock_csv",
    "parse_field_spec",
    "FieldSpec",
    "FieldSpecField",
    "DType",
    "build_expectation_suite",
    "WorkflowError",
    "WorkflowState",
    "WorkflowStore",
    "workflow_store",
]
