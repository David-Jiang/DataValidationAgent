from __future__ import annotations

import json

import pytest

from conftest import spec_document, string_field
from core.models import FieldSpec
from core.workflow import WorkflowError, WorkflowState, WorkflowStore


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"
CONTRACT = '{"title":"field_spec"}'


def ready_for_confirmation(store: WorkflowStore) -> tuple[str, FieldSpec]:
    workflow_id = store.start(DATASET_URN)["workflow_id"]
    store.schema_loaded(workflow_id, {"table": "orders", "fields": []})
    store.contract_loaded(workflow_id, CONTRACT)
    spec = FieldSpec(**spec_document(string_field()))
    store.submit_spec(workflow_id, spec)
    return workflow_id, spec


def test_happy_path_enforces_confirmed_spec_and_delivery_paths() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)

    confirmed = store.confirm(workflow_id)
    assert confirmed["state"] == WorkflowState.confirmed.value
    assert confirmed["confirmation"]["field_spec_sha256"] == confirmed["field_spec_sha256"]

    assert store.field_spec(workflow_id).table_name == "orders"
    store.artifact_generated(workflow_id, "validation_suite")
    paths = store.expected_artifact_paths(workflow_id)
    completed = store.complete(workflow_id, paths["validation_suite"])

    assert completed["state"] == WorkflowState.completed.value
    assert completed["delivered_artifacts"] == {
        "validation_suite": f"artifacts/{workflow_id}/orders_validation_suite.json"
    }


def test_artifact_generation_is_rejected_before_human_confirmation() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)

    with pytest.raises(WorkflowError, match="只允許 state=confirmed"):
        store.field_spec(workflow_id)


def test_loading_contract_after_confirmation_invalidates_confirmation() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)
    store.confirm(workflow_id)

    snapshot = store.contract_loaded(workflow_id, CONTRACT)

    assert snapshot["state"] == WorkflowState.drafting_spec.value
    assert snapshot["confirmation"] is None
    with pytest.raises(WorkflowError):
        store.field_spec(workflow_id)


def test_completion_requires_generated_mock_path_when_mock_was_generated() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)
    store.confirm(workflow_id)
    store.artifact_generated(workflow_id, "validation_suite")
    store.artifact_generated(workflow_id, "mock_data")
    paths = store.expected_artifact_paths(workflow_id)

    with pytest.raises(WorkflowError, match="mock_path 必須是"):
        store.complete(workflow_id, paths["validation_suite"])

    completed = store.complete(
        workflow_id, paths["validation_suite"], paths["mock_data"]
    )
    assert completed["delivered_artifacts"]["mock_data"].endswith("orders_mock.csv")


def test_completion_rejects_paths_outside_workflow_artifact_root() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)
    store.confirm(workflow_id)
    store.artifact_generated(workflow_id, "validation_suite")

    with pytest.raises(WorkflowError, match="suite_path 必須是"):
        store.complete(workflow_id, "artifacts/orders_validation_suite.json")


def test_block_and_resume_returns_to_recorded_state() -> None:
    store = WorkflowStore()
    workflow_id = store.start(DATASET_URN)["workflow_id"]

    blocked = store.block(workflow_id, "DataHub offline", WorkflowState.awaiting_schema)
    assert blocked["state"] == WorkflowState.blocked.value
    assert blocked["blocked"]["resume_state"] == WorkflowState.awaiting_schema.value

    resumed = store.resume(workflow_id)
    assert resumed["state"] == WorkflowState.awaiting_schema.value
    assert resumed["blocked"] is None


def test_snapshot_hides_full_schema_and_field_spec_but_keeps_hashes() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)

    snapshot = store.snapshot(workflow_id)

    assert "upstream_schema" not in snapshot
    assert "field_spec_json" not in snapshot
    assert snapshot["upstream_schema_sha256"]
    assert snapshot["field_spec_sha256"]
    json.dumps(snapshot)


def test_unknown_workflow_is_rejected() -> None:
    with pytest.raises(WorkflowError, match="找不到 workflow_id"):
        WorkflowStore().snapshot("dva_missing")
