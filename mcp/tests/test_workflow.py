from __future__ import annotations

import json
import re

import pytest

from conftest import spec_document, string_field
from core import workflow as workflow_module
from core.models import FieldSpec
from core.validation_rules import build_validation_rules
from core.workflow import WorkflowError, WorkflowState, WorkflowStore


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"
CONTRACT = '{"title":"field_spec"}'
REQUIRED_ARTIFACTS = (
    "validation_rules",
    "readme",
    "data_validation",
    "test_data_validation",
)


def ready_for_confirmation(store: WorkflowStore):
    workflow_id = store.start(DATASET_URN)["workflow_id"]
    store.schema_loaded(workflow_id, {"table": "orders", "fields": []})
    store.contract_loaded(workflow_id, CONTRACT)
    spec = FieldSpec(**spec_document(string_field()))
    rules = build_validation_rules(DATASET_URN, spec, [])
    store.submit_rules(workflow_id, spec, rules)
    return workflow_id, spec, rules


def generate_all(store: WorkflowStore, workflow_id: str) -> dict[str, str]:
    for artifact in REQUIRED_ARTIFACTS:
        store.artifact_generated(workflow_id, artifact)
    return store.expected_artifact_paths(workflow_id)


def test_workflow_id_contains_utc_date_and_four_base36_characters() -> None:
    workflow_id = WorkflowStore().start(DATASET_URN)["workflow_id"]
    assert re.fullmatch(r"dva_\d{8}_[0-9a-z]{4}", workflow_id)


def test_workflow_id_collision_probes_next_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow_module, "_workflow_date", lambda: "20260715")
    monkeypatch.setattr(workflow_module.secrets, "randbelow", lambda _space: 0)
    store = WorkflowStore()
    assert store.start(DATASET_URN)["workflow_id"] == "dva_20260715_0000"
    assert store.start(DATASET_URN)["workflow_id"] == "dva_20260715_0001"


def test_happy_path_confirms_both_rule_groups_and_delivers_four_artifacts() -> None:
    store = WorkflowStore()
    workflow_id, _spec, rules = ready_for_confirmation(store)

    pending = store.pending_validation_rules(workflow_id)
    assert pending == rules
    confirmed = store.confirm(workflow_id)
    assert confirmed["state"] == WorkflowState.confirmed.value
    assert confirmed["confirmation"]["field_spec_sha256"]
    assert confirmed["confirmation"]["validation_rules_sha256"]

    paths = generate_all(store, workflow_id)
    completed = store.complete(
        workflow_id,
        paths["validation_rules"],
        paths["readme"],
        paths["data_validation"],
        paths["test_data_validation"],
    )

    assert completed["state"] == WorkflowState.completed.value
    assert completed["delivered_artifacts"] == paths
    assert paths == {
        "validation_rules": f"artifacts/{workflow_id}/validation_rules.json",
        "readme": f"artifacts/{workflow_id}/README.md",
        "data_validation": f"artifacts/{workflow_id}/data_validation.py",
        "test_data_validation": f"artifacts/{workflow_id}/test_data_validation.py",
    }


def test_artifact_generation_is_rejected_before_human_confirmation() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    with pytest.raises(WorkflowError, match="只允許 state=confirmed"):
        store.validation_rules(workflow_id)


def test_loading_contract_after_confirmation_invalidates_rules_and_artifacts() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    store.artifact_generated(workflow_id, "validation_rules")

    snapshot = store.contract_loaded(workflow_id, CONTRACT)

    assert snapshot["state"] == WorkflowState.drafting_rules.value
    assert snapshot["confirmation"] is None
    assert snapshot["validation_rules_sha256"] is None
    assert snapshot["generated_artifacts"] == {
        artifact: False for artifact in REQUIRED_ARTIFACTS
    }


def test_completion_rejects_missing_artifacts() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    store.artifact_generated(workflow_id, "validation_rules")
    paths = store.expected_artifact_paths(workflow_id)

    with pytest.raises(WorkflowError, match="readme, data_validation, test_data_validation"):
        store.complete(
            workflow_id,
            paths["validation_rules"],
            paths["readme"],
            paths["data_validation"],
            paths["test_data_validation"],
        )


def test_completion_rejects_non_workflow_path() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    paths = generate_all(store, workflow_id)

    with pytest.raises(WorkflowError, match="readme_path"):
        store.complete(
            workflow_id,
            paths["validation_rules"],
            "artifacts/README.md",
            paths["data_validation"],
            paths["test_data_validation"],
        )


def test_snapshot_hides_rule_documents_but_keeps_hashes() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    snapshot = store.snapshot(workflow_id)
    assert "upstream_schema" not in snapshot
    assert "field_spec_json" not in snapshot
    assert "validation_rules_json" not in snapshot
    assert snapshot["field_spec_sha256"]
    assert snapshot["validation_rules_sha256"]
    json.dumps(snapshot)


def test_block_and_resume_returns_to_recorded_state() -> None:
    store = WorkflowStore()
    workflow_id = store.start(DATASET_URN)["workflow_id"]
    store.block(workflow_id, "DataHub offline", WorkflowState.awaiting_schema)
    resumed = store.resume(workflow_id)
    assert resumed["state"] == WorkflowState.awaiting_schema.value
    assert resumed["blocked"] is None
