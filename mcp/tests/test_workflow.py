from __future__ import annotations

import json
import re

import pytest

from conftest import spec_document, string_field
from core import workflow as workflow_module
from core.models import FieldSpec
from core.workflow import WorkflowError, WorkflowState, WorkflowStore


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"
CONTRACT = '{"title":"field_spec"}'
REQUIRED_ARTIFACTS = ("validation_suite", "mock_data", "field_spec")


def ready_for_confirmation(store: WorkflowStore) -> tuple[str, FieldSpec]:
    workflow_id = store.start(DATASET_URN)["workflow_id"]
    store.schema_loaded(workflow_id, {"table": "orders", "fields": []})
    store.contract_loaded(workflow_id, CONTRACT)
    spec = FieldSpec(**spec_document(string_field()))
    store.submit_spec(workflow_id, spec)
    return workflow_id, spec


def generate_all(store: WorkflowStore, workflow_id: str) -> dict[str, str]:
    for artifact in REQUIRED_ARTIFACTS:
        store.artifact_generated(workflow_id, artifact)
    return store.expected_artifact_paths(workflow_id)


def test_workflow_id_contains_utc_date_and_four_base36_characters() -> None:
    workflow_id = WorkflowStore().start(DATASET_URN)["workflow_id"]
    assert re.fullmatch(r"dva_\d{8}_[0-9a-z]{4}", workflow_id)


def test_workflow_id_collision_probes_next_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflow_module, "_workflow_date", lambda: "20260715")
    monkeypatch.setattr(workflow_module.secrets, "randbelow", lambda _space: 0)
    store = WorkflowStore()

    assert store.start(DATASET_URN)["workflow_id"] == "dva_20260715_0000"
    assert store.start(DATASET_URN)["workflow_id"] == "dva_20260715_0001"


def test_happy_path_requires_and_delivers_all_three_artifacts() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)

    confirmed = store.confirm(workflow_id)
    assert confirmed["state"] == WorkflowState.confirmed.value
    assert confirmed["confirmation"]["field_spec_sha256"] == confirmed["field_spec_sha256"]
    assert store.field_spec(workflow_id).table_name == "orders"

    paths = generate_all(store, workflow_id)
    completed = store.complete(
        workflow_id,
        paths["validation_suite"],
        paths["mock_data"],
        paths["field_spec"],
    )

    assert completed["state"] == WorkflowState.completed.value
    assert completed["delivered_artifacts"] == paths
    assert paths == {
        "validation_suite": f"artifacts/{workflow_id}/orders_validation_suite.json",
        "mock_data": f"artifacts/{workflow_id}/orders_mock.csv",
        "field_spec": f"artifacts/{workflow_id}/orders_field_spec.csv",
    }


def test_artifact_generation_is_rejected_before_human_confirmation() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)

    with pytest.raises(WorkflowError, match="只允許 state=confirmed"):
        store.field_spec(workflow_id)


def test_loading_contract_after_confirmation_invalidates_all_artifacts() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)
    store.confirm(workflow_id)
    store.artifact_generated(workflow_id, "validation_suite")

    snapshot = store.contract_loaded(workflow_id, CONTRACT)

    assert snapshot["state"] == WorkflowState.drafting_spec.value
    assert snapshot["confirmation"] is None
    assert snapshot["generated_artifacts"] == {
        "validation_suite": False,
        "mock_data": False,
        "field_spec": False,
    }
    with pytest.raises(WorkflowError):
        store.field_spec(workflow_id)


def test_completion_rejects_any_missing_required_artifact() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)
    store.confirm(workflow_id)
    store.artifact_generated(workflow_id, "validation_suite")
    paths = store.expected_artifact_paths(workflow_id)

    with pytest.raises(WorkflowError, match="mock_data, field_spec"):
        store.complete(
            workflow_id,
            paths["validation_suite"],
            paths["mock_data"],
            paths["field_spec"],
        )


@pytest.mark.parametrize(
    ("path_name", "bad_path", "error"),
    [
        ("validation_suite", "artifacts/orders_validation_suite.json", "suite_path"),
        ("mock_data", "artifacts/orders_mock.csv", "mock_path"),
        ("field_spec", "artifacts/orders_field_spec.csv", "field_spec_path"),
    ],
)
def test_completion_rejects_non_workflow_paths(
    path_name: str, bad_path: str, error: str
) -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)
    store.confirm(workflow_id)
    paths = generate_all(store, workflow_id)
    paths[path_name] = bad_path

    with pytest.raises(WorkflowError, match=error):
        store.complete(
            workflow_id,
            paths["validation_suite"],
            paths["mock_data"],
            paths["field_spec"],
        )


def test_unknown_artifact_is_rejected() -> None:
    store = WorkflowStore()
    workflow_id, _spec = ready_for_confirmation(store)
    store.confirm(workflow_id)
    with pytest.raises(WorkflowError, match="未知的 artifact"):
        store.artifact_generated(workflow_id, "optional_report")


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
