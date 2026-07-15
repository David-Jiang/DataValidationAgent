from __future__ import annotations

import json
import re

import pytest

import server
from conftest import spec_document, string_field
from core import workflow_store


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"


@pytest.fixture(autouse=True)
def empty_workflow_store() -> None:
    workflow_store.clear()


def submitted_row_rule() -> dict:
    return {
        "id": "row.alt_required_when_code_empty",
        "desc": "code 為空字串時，alt 不可為 null",
        "columns": ["code", "alt"],
        "examples": {
            "pass": [{"name": "alt 有值", "sql": "code = '' AND alt IS NOT NULL"}],
            "fail": [{"name": "alt 缺值", "sql": "code = '' AND alt IS NULL"}],
        },
    }


def start_submitted_workflow(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(
        server,
        "fetch_table_schema",
        lambda _urn: {
            "table": "orders",
            "fields": [{"name": "code"}, {"name": "alt"}],
        },
    )
    workflow_id = json.loads(server.start_validation(DATASET_URN))["workflow_id"]
    assert re.fullmatch(r"dva_\d{8}_[0-9a-z]{4}", workflow_id)
    server.get_table_schema(workflow_id)
    assert json.loads(server.get_field_spec(workflow_id))["title"] == "field_spec"
    field_spec = spec_document(
        string_field(
            "code",
            nullable=False,
            invalid_value_tokens=[],
            allow_empty_string=True,
        ),
        string_field(
            "alt",
            nullable=True,
            invalid_value_tokens=[],
            allow_empty_string=True,
        ),
    )
    submitted = json.loads(
        server.submit_validation_rules(
            workflow_id,
            json.dumps(field_spec),
            json.dumps([submitted_row_rule()]),
        )
    )
    assert submitted["state"] == "awaiting_confirmation"
    return workflow_id


def test_server_rejects_artifact_before_combined_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = start_submitted_workflow(monkeypatch)
    assert server.gen_validation_rules(workflow_id).startswith("ERROR:")


def test_pending_rules_include_col_and_row_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = start_submitted_workflow(monkeypatch)
    rules = json.loads(server.get_submitted_validation_rules(workflow_id))
    assert [rule["id"] for rule in rules["col_rules"]] == ["col.code.not_null"]
    assert rules["row_rules"] == [submitted_row_rule()]


def test_server_runs_complete_validation_as_code_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = start_submitted_workflow(monkeypatch)
    confirmed = json.loads(server.confirm_validation_rules(workflow_id))
    assert confirmed["state"] == "confirmed"

    rules_text = server.gen_validation_rules(workflow_id)
    rules = json.loads(rules_text)
    assert len(rules["col_rules"]) == 1
    assert len(rules["row_rules"]) == 1

    readme = server.gen_readme(workflow_id)
    assert "| 規則總數 | 2 |" in readme

    data_validation = server.gen_data_validation(
        workflow_id,
        json.dumps(
            [
                {
                    "id": "row.alt_required_when_code_empty",
                    "body": (
                        'condition = df["code"].eq("").fillna(False)\n'
                        'return (~condition | df["alt"].notna()).fillna(False)'
                    ),
                }
            ]
        ),
    )
    compile(data_validation, "data_validation.py", "exec")

    tests = server.gen_test_data_validation(
        workflow_id,
        json.dumps(
            [
                {
                    "id": "col.code.not_null",
                    "pass_cases": [{"name": "有值", "rows": [{"code": "A"}]}],
                    "fail_cases": [{"name": "缺值", "rows": [{"code": None}]}],
                },
                {
                    "id": "row.alt_required_when_code_empty",
                    "pass_cases": [
                        {"name": "alt 有值", "rows": [{"code": "", "alt": "B"}]}
                    ],
                    "fail_cases": [
                        {"name": "alt 缺值", "rows": [{"code": "", "alt": None}]}
                    ],
                },
            ]
        ),
    )
    compile(tests, "test_data_validation.py", "exec")
    assert "execution_failure" not in tests

    root = f"artifacts/{workflow_id}"
    completed = json.loads(
        server.complete_validation(
            workflow_id,
            f"{root}/validation_rules.json",
            f"{root}/README.md",
            f"{root}/data_validation.py",
            f"{root}/test_data_validation.py",
        )
    )
    assert completed["state"] == "completed"
    assert len(completed["delivered_artifacts"]) == 4
