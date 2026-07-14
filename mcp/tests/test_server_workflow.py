from __future__ import annotations

import csv
import inspect
import io
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


def start_ready_workflow(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(
        server,
        "fetch_table_schema",
        lambda _urn: {"table": "orders", "fields": [{"name": "code"}]},
    )
    workflow_id = json.loads(server.start_validation(DATASET_URN))["workflow_id"]
    assert re.fullmatch(r"dva_\d{8}_[0-9a-z]{4}", workflow_id)
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


def test_mock_tool_exposes_no_row_count_parameter() -> None:
    assert list(inspect.signature(server.gen_mock_data).parameters) == ["workflow_id"]


def test_server_runs_complete_confirmed_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = start_ready_workflow(monkeypatch)
    assert json.loads(server.confirm_field_spec(workflow_id))["state"] == "confirmed"

    suite = json.loads(server.gen_validation_suite(workflow_id))
    assert suite["name"] == "orders_validation_suite"
    assert suite["meta"]["great_expectations_version"] == "1.18.2"

    mock_rows = list(csv.DictReader(io.StringIO(server.gen_mock_data(workflow_id))))
    assert len(mock_rows) == 100

    field_spec_rows = list(
        csv.DictReader(io.StringIO(server.gen_field_spec_csv(workflow_id)))
    )
    assert field_spec_rows[0]["name"] == "code"

    paths = {
        "validation_suite": f"artifacts/{workflow_id}/orders_validation_suite.json",
        "mock_data": f"artifacts/{workflow_id}/orders_mock.csv",
        "field_spec": f"artifacts/{workflow_id}/orders_field_spec.csv",
    }
    completed = json.loads(
        server.complete_validation(
            workflow_id,
            paths["validation_suite"],
            paths["mock_data"],
            paths["field_spec"],
        )
    )
    assert completed["state"] == "completed"
    assert completed["delivered_artifacts"] == paths
