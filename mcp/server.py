"""使用記憶體內 workflow state machine 的 Data Validation Agent MCP Server。"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from core import (
    DataHubError,
    WorkflowError,
    WorkflowState,
    build_col_rules,
    build_impl_code,
    build_test_code,
    build_validation_rules,
    fetch_table_schema,
    parse_field_spec,
    parse_row_rules,
    render_data_validation_module,
    render_readme,
    render_test_module,
    render_validation_rules_json,
    workflow_store,
)

_SCHEMA_PATH = Path(__file__).parent / "core" / "schemas" / "field_spec.schema.json"
_SERVER_INSTRUCTIONS = """
這是 Data Validation Agent MCP Server。每個 workflow 都必須從 start_validation(dataset_urn)
開始，並將回傳的 workflow_id 傳給所有後續 tool。流程為：get_table_schema ->
get_field_spec -> submit_validation_rules -> 使用者同時確認完整 col_rules 與 row_rules ->
confirm_validation_rules -> 四個 artifact generators -> complete_validation。
validation_rules.json 內的 examples.sql 只作為 review 用的 boolean expression，Server 不會執行。
Agent Host 必須將 artifacts 寫入 artifacts/{workflow_id}/，並在完成前讀回及執行 pytest。
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
    """依 workflow 保存的 DataHub URN 取得上游 schema。"""
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
        message = f"取得資料表 schema 時發生例外：{exc}"
        workflow_store.block(workflow_id, message, WorkflowState.awaiting_schema)
        return f"ERROR: {message}"


@mcp.tool()
def get_field_spec(workflow_id: str) -> str:
    """
    回傳 dtype 專屬 col-rule 討論模板，並進入 drafting_rules。
    再次呼叫會使既有 confirmation 與 artifacts 失效。
    """
    try:
        contract = _SCHEMA_PATH.read_text(encoding="utf-8")
        workflow_store.contract_loaded(workflow_id, contract)
        return contract
    except WorkflowError as exc:
        return f"ERROR: {exc}"
    except FileNotFoundError:
        message = "找不到 core/schemas/field_spec.schema.json"
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
def submit_validation_rules(
    workflow_id: str,
    field_spec_json: str,
    row_rules_json: str,
) -> str:
    """
    將 field spec 拆成 col_rules，並合併使用者以自然語言、SQL 或其他方式討論後建立的
    row_rules。row_rules_json 必須是 rule array；若沒有 row rule，傳入 []。
    """
    try:
        spec = parse_field_spec(field_spec_json)
        col_rules = build_col_rules(spec)
        row_rules = parse_row_rules(row_rules_json)
        dataset_urn = workflow_store.dataset_reference(workflow_id)
        rules = build_validation_rules(dataset_urn, spec, col_rules, row_rules)
        return _json(workflow_store.submit_rules(workflow_id, spec, rules))
    except (WorkflowError, ValueError) as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        return f"ERROR: 提交 validation rules 時發生例外：{exc}"


@mcp.tool()
def get_submitted_validation_rules(workflow_id: str) -> str:
    """
    回傳實際提交的完整 validation_rules，供 Agent 以 col rules 與 row rules 分組表格顯示。
    只有 awaiting_confirmation state 可使用。
    """
    try:
        rules = workflow_store.pending_validation_rules(workflow_id)
        return render_validation_rules_json(rules)
    except WorkflowError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def confirm_validation_rules(workflow_id: str) -> str:
    """
    確認目前完整 col_rules 與 row_rules。Agent 必須先用分組 Markdown tables 顯示全部規則，
    並收到使用者明確肯定回覆後才能呼叫。
    """
    try:
        return _json(workflow_store.confirm(workflow_id))
    except WorkflowError as exc:
        return f"ERROR: {exc}"
@mcp.tool()
def gen_validation_rules(workflow_id: str) -> str:
    """產生 artifacts/{workflow_id}/validation_rules.json。"""
    try:
        rules = workflow_store.validation_rules(workflow_id)
        content = render_validation_rules_json(rules)
        workflow_store.artifact_generated(workflow_id, "validation_rules")
        return content
    except WorkflowError as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        message = f"產生 validation_rules.json 時發生例外：{exc}"
        workflow_store.block(workflow_id, message, _state(workflow_id))
        return f"ERROR: {message}"


@mcp.tool()
def gen_readme(workflow_id: str) -> str:
    """產生中文、分組且含 summary tables 的 artifacts/{workflow_id}/README.md。"""
    try:
        resume_state = _state(workflow_id)
        rules = workflow_store.validation_rules(workflow_id)
        content = render_readme(rules)
        workflow_store.artifact_generated(workflow_id, "readme")
        return content
    except WorkflowError as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        message = f"產生 README.md 時發生例外：{exc}"
        workflow_store.block(workflow_id, message, resume_state)
        return f"ERROR: {message}"


@mcp.tool()
def gen_data_validation(workflow_id: str, row_impl_code_json: str) -> str:
    """
    產生 Pandas-native data_validation.py。Agent 必須依已確認 row rules 提供每條 row rule 的
    pure Python function body；禁止直接使用使用者提供的 SQL/Python 原文。
    """
    try:
        resume_state = _state(workflow_id)
        rules = workflow_store.validation_rules(workflow_id)
        spec = workflow_store.field_spec(workflow_id)
        impl_code = build_impl_code(rules, spec, row_impl_code_json)
        content = render_data_validation_module(impl_code)
        workflow_store.artifact_generated(workflow_id, "data_validation")
        return content
    except (WorkflowError, ValueError) as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        message = f"產生 data_validation.py 時發生例外：{exc}"
        workflow_store.block(workflow_id, message, resume_state)
        return f"ERROR: {message}"


@mcp.tool()
def gen_test_data_validation(workflow_id: str, row_test_code_json: str) -> str:
    """
    產生 pytest；每條 col/row rule 都必須提供至少一組 concrete passing 與 failing rows。
    不產生 execution failure tests，但會驗證空 DataFrame 直接回傳兩個空 DataFrame。
    """
    try:
        resume_state = _state(workflow_id)
        rules = workflow_store.validation_rules(workflow_id)
        test_code = build_test_code(rules, row_test_code_json)
        content = render_test_module(test_code)
        workflow_store.artifact_generated(workflow_id, "test_data_validation")
        return content
    except (WorkflowError, ValueError) as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        message = f"產生 test_data_validation.py 時發生例外：{exc}"
        workflow_store.block(workflow_id, message, resume_state)
        return f"ERROR: {message}"


@mcp.tool()
def complete_validation(
    workflow_id: str,
    validation_rules_path: str,
    readme_path: str,
    data_validation_path: str,
    test_data_validation_path: str,
) -> str:
    """四個 artifacts 已寫入、讀回並通過 pytest 後，將 workflow 標記為完成。"""
    try:
        return _json(
            workflow_store.complete(
                workflow_id,
                validation_rules_path,
                readme_path,
                data_validation_path,
                test_data_validation_path,
            )
        )
    except WorkflowError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def resume_validation(workflow_id: str) -> str:
    """在修正輸入或環境後恢復 blocked workflow。"""
    try:
        return _json(workflow_store.resume(workflow_id))
    except WorkflowError as exc:
        return f"ERROR: {exc}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
