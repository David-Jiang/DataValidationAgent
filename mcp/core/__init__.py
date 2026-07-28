"""
MCP Server 核心邏輯模組

此模組包含 DataHub schema、field spec、validation rules、Pandas-native artifact generators
與 workflow state machine。
"""

from .artifacts import (
    render_data_validation_module,
    render_readme,
    render_test_module,
    render_validation_rules_json,
)
from .datahub import DataHubError, fetch_table_schema
from .field_spec import parse_field_spec, FieldSpec, FieldSpecField, DType
from .rules import (
    build_col_rules,
    build_validation_rules,
    parse_row_rules,
)
from .validation_rules import (
    InputColumn,
    RuleExample,
    RuleExamples,
    RuleTestCases,
    ValidationRule,
    ValidationRules,
    build_impl_code,
    build_test_code,
)
from .workflow import WorkflowError, WorkflowState, WorkflowStore, workflow_store

__all__ = [
    "DataHubError",
    "fetch_table_schema",
    "parse_field_spec",
    "FieldSpec",
    "FieldSpecField",
    "DType",
    "InputColumn",
    "RuleExample",
    "RuleExamples",
    "ValidationRule",
    "ValidationRules",
    "build_col_rules",
    "build_validation_rules",
    "parse_row_rules",
    "RuleTestCases",
    "build_impl_code",
    "build_test_code",
    "render_validation_rules_json",
    "render_readme",
    "render_data_validation_module",
    "render_test_module",
    "WorkflowError",
    "WorkflowState",
    "WorkflowStore",
    "workflow_store",
]
