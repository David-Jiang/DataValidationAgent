"""使用記憶體內 workflow state machine 的 Data Validation Agent MCP Server。"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from core import (
    DataHubError,
    WorkflowError,
    WorkflowState,
    build_expectation_suite,
    fetch_table_schema,
    generate_mock_csv,
    parse_field_spec,
    workflow_store,
)

_SCHEMA_PATH = Path(__file__).parent / "core" / "schemas" / "field_spec.schema.json"
_SERVER_INSTRUCTIONS = """
這是 Data Validation Agent MCP Server。每個 workflow 都必須從 start_validation(dataset_urn)
開始，並將回傳的 workflow_id 傳給所有後續 tool。請依照以下順序執行：
get_table_schema -> get_field_spec -> submit_field_spec -> confirm_field_spec ->
gen_validation_suite -> 選用的 gen_mock_data -> complete_validation。
Server 會拒絕不符合目前 workflow state 的操作。只有在人類完整檢視 field_spec，並明確回覆
「確認」等肯定語句後，才能呼叫 confirm_field_spec。Artifact 會以字串回傳，Agent Host 必須
將其寫入 artifacts/{workflow_id}/；MCP Server 不保存 artifact 檔案。
""".strip()

mcp = FastMCP(
    "data-validation-agent",
    host="0.0.0.0",
    port=8000,
    instructions=_SERVER_INSTRUCTIONS,
)


def _json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _state(workflow_id: str) -> WorkflowState:
    return WorkflowState(workflow_store.snapshot(workflow_id)["state"])


@mcp.tool()
def start_validation(dataset_urn: str) -> str:
    """為一個 DataHub dataset 建立 workflow，並回傳 workflow_id。"""
    try:
        return _json(workflow_store.start(dataset_urn))
    except WorkflowError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def get_validation_state(workflow_id: str) -> str:
    """回傳 workflow 目前的 state、hash、history 與 artifact 狀態。"""
    try:
        snapshot = workflow_store.snapshot(workflow_id)
        if snapshot["state"] in {
            WorkflowState.confirmed.value,
            WorkflowState.generating_artifacts.value,
        }:
            snapshot["expected_artifact_paths"] = workflow_store.expected_artifact_paths(
                workflow_id
            )
        return _json(snapshot)
    except WorkflowError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def get_table_schema(workflow_id: str) -> str:
    """
    取得由 start_validation 登記之 dataset 的上游 DataHub schema。
    只有 workflow 處於 awaiting_schema 時才能使用此 tool。
    """
    try:
        dataset_urn = workflow_store.dataset_urn(workflow_id)
        schema = fetch_table_schema(dataset_urn)
        workflow_store.schema_loaded(workflow_id, schema)
        return _json(schema)
    except WorkflowError as exc:
        return f"ERROR: {exc}"
    except DataHubError as exc:
        workflow_store.block(workflow_id, str(exc), WorkflowState.awaiting_schema)
        return f"ERROR: {exc}"
    except Exception as exc:
        workflow_store.block(
            workflow_id,
            f"取得資料表 schema 時發生例外：{exc}",
            WorkflowState.awaiting_schema,
        )
        return f"ERROR: 取得資料表 schema 時發生例外：{exc}"


@mcp.tool()
def get_field_spec(workflow_id: str) -> str:
    """
    回傳具權威性的 field_spec JSON Schema，並進入 drafting_spec。
    若在 spec 已提交或確認後呼叫，原有 confirmation 與 artifacts 都會失效。
    """
    try:
        contract = _SCHEMA_PATH.read_text(encoding="utf-8")
        workflow_store.contract_loaded(workflow_id, contract)
        return contract
    except WorkflowError as exc:
        return f"ERROR: {exc}"
    except FileNotFoundError:
        message = (
            "找不到 field_spec schema 檔案，請確認 Server 部署內容包含 "
            "core/schemas/field_spec.schema.json"
        )
        try:
            workflow_store.block(workflow_id, message, _state(workflow_id))
        except WorkflowError:
            pass
        return f"ERROR: {message}"
    except Exception as exc:
        message = f"讀取 field_spec schema 時發生例外：{exc}"
        try:
            workflow_store.block(workflow_id, message, _state(workflow_id))
        except WorkflowError:
            pass
        return f"ERROR: {message}"


@mcp.tool()
def submit_field_spec(workflow_id: str, field_spec_json: str) -> str:
    """
    驗證並保存 canonical field_spec，接著進入 awaiting_confirmation。
    提交的 spec 必須符合 get_field_spec 最近一次回傳的 schema。
    """
    try:
        spec = parse_field_spec(field_spec_json)
        return _json(workflow_store.submit_spec(workflow_id, spec))
    except (WorkflowError, ValueError) as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        return f"ERROR: 提交 field_spec 時發生例外：{exc}"


@mcp.tool()
def confirm_field_spec(workflow_id: str) -> str:
    """
    確認目前實際提交的 field_spec。
    Agent 必須先向人類顯示完整 spec 與 workflow_id，並收到「確認」等明確肯定回覆，才能呼叫。
    """
    try:
        return _json(workflow_store.confirm(workflow_id))
    except WorkflowError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def gen_validation_suite(workflow_id: str) -> str:
    """
    使用 Server 內已確認的 field_spec 產生必要的 Great Expectations suite。
    Agent Host 必須將回傳的 JSON 寫入
    artifacts/{workflow_id}/<table_name>_validation_suite.json.
    """
    try:
        resume_state = _state(workflow_id)
        spec = workflow_store.field_spec(workflow_id)
        suite = build_expectation_suite(spec.table_name, spec)
        workflow_store.artifact_generated(workflow_id, "validation_suite")
        return _json(suite)
    except WorkflowError as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        message = f"產生 validation suite 時發生例外：{exc}"
        workflow_store.block(workflow_id, message, resume_state)
        return f"ERROR: {message}"


@mcp.tool()
def gen_mock_data(workflow_id: str, row_count: int = 100) -> str:
    """
    使用 Server 內已確認的 field_spec 產生選用的 CSV mock data。
    Agent Host 必須將回傳的 CSV 寫入
    artifacts/{workflow_id}/<table_name>_mock.csv.
    """
    try:
        resume_state = _state(workflow_id)
        spec = workflow_store.field_spec(workflow_id)
        csv_text = generate_mock_csv(spec, row_count=row_count)
        workflow_store.artifact_generated(workflow_id, "mock_data")
        return csv_text
    except WorkflowError as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        message = f"產生 mock data 時發生例外：{exc}"
        workflow_store.block(workflow_id, message, resume_state)
        return f"ERROR: {message}"


@mcp.tool()
def complete_validation(
    workflow_id: str, suite_path: str, mock_path: str = ""
) -> str:
    """
    Agent Host 寫入並驗證產生的 artifacts 後，將交付標記為完成。
    路徑必須符合 artifacts/{workflow_id}/<table_name>_validation_suite.json；若有產生 mock
    data，還必須符合 artifacts/{workflow_id}/<table_name>_mock.csv。
    """
    try:
        return _json(workflow_store.complete(workflow_id, suite_path, mock_path))
    except WorkflowError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def resume_validation(workflow_id: str) -> str:
    """在人類修正輸入或環境後，恢復處於 blocked 的 workflow。"""
    try:
        return _json(workflow_store.resume(workflow_id))
    except WorkflowError as exc:
        return f"ERROR: {exc}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
