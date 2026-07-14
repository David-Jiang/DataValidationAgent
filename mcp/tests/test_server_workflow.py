from __future__ import annotations

import json

import pytest

import server
from conftest import spec_document, string_field
from core import workflow_store


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"


@pytest.fixture(autouse=True)
def empty_workflow_store() -> None:
    workflow_store.clear()


def start_ready_workflow(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(
        server,
        "fetch_table_schema",
        lambda _urn: {"table": "orders", "fields": [{"name": "code"}]},
    )
    workflow_id = json.loads(server.start_validation(DATASET_URN))["workflow_id"]
    assert json.loads(server.get_table_schema(workflow_id))["table"] == "orders"
    assert json.loads(server.get_field_spec(workflow_id))["title"] == "field_spec"
    result = json.loads(
        server.submit_field_spec(
            workflow_id, json.dumps(spec_document(string_field()))
        )
    )
    assert result["state"] == "awaiting_confirmation"
    return workflow_id


def test_server_rejects_generator_before_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = start_ready_workflow(monkeypatch)

    result = server.gen_validation_suite(workflow_id)

    assert result.startswith("ERROR:")
    assert json.loads(server.get_validation_state(workflow_id))["state"] == (
        "awaiting_confirmation"
    )


def test_server_runs_complete_confirmed_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = start_ready_workflow(monkeypatch)
    assert json.loads(server.confirm_field_spec(workflow_id))["state"] == "confirmed"

    suite = json.loads(server.gen_validation_suite(workflow_id))
    assert suite["name"] == "orders_validation_suite"
    assert suite["meta"]["great_expectations_version"] == "1.18.2"

    suite_path = f"artifacts/{workflow_id}/orders_validation_suite.json"
    completed = json.loads(server.complete_validation(workflow_id, suite_path))
    assert completed["state"] == "completed"
    assert completed["delivered_artifacts"] == {"validation_suite": suite_path}
