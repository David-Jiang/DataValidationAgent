from __future__ import annotations

import hashlib
import json
import re

import pytest

from conftest import spec_document, string_field
from core import workflow as workflow_module
from core.field_spec import FieldSpec
from core.rules import build_col_rules, build_validation_rules
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
    rules = build_validation_rules(DATASET_URN, spec, build_col_rules(spec), [])
    store.submit_rules(workflow_id, spec, rules)
    return workflow_id, spec, rules


def generate_all(store: WorkflowStore, workflow_id: str) -> dict[str, str]:
    for artifact in REQUIRED_ARTIFACTS:
        store.artifact_generated(workflow_id, artifact, digest(artifact))
    return store.expected_artifact_paths(workflow_id)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record_passing_pytest(store: WorkflowStore, workflow_id: str) -> None:
    store.record_pytest_result(
        workflow_id,
        digest("data_validation"),
        digest("repaired_test"),
        0,
        "python -m pytest -q test_data_validation.py",
        "2 passed",
    )


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
    record_passing_pytest(store, workflow_id)
    completed = store.complete(
        workflow_id,
        paths["validation_rules"],
        paths["readme"],
        paths["data_validation"],
        paths["test_data_validation"],
        digest("data_validation"),
        digest("repaired_test"),
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
    store.artifact_generated(
        workflow_id, "validation_rules", digest("validation_rules")
    )

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
    store.artifact_generated(
        workflow_id, "validation_rules", digest("validation_rules")
    )
    paths = store.expected_artifact_paths(workflow_id)

    with pytest.raises(WorkflowError, match="readme, data_validation, test_data_validation"):
        store.complete(
            workflow_id,
            paths["validation_rules"],
            paths["readme"],
            paths["data_validation"],
            paths["test_data_validation"],
            digest("data_validation"),
            digest("repaired_test"),
        )


def test_completion_rejects_non_workflow_path() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    paths = generate_all(store, workflow_id)
    record_passing_pytest(store, workflow_id)

    with pytest.raises(WorkflowError, match="readme_path"):
        store.complete(
            workflow_id,
            paths["validation_rules"],
            "artifacts/README.md",
            paths["data_validation"],
            paths["test_data_validation"],
            digest("data_validation"),
            digest("repaired_test"),
        )


def test_completion_requires_passing_pytest_evidence() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    paths = generate_all(store, workflow_id)

    with pytest.raises(WorkflowError, match="尚未記錄成功"):
        store.complete(
            workflow_id,
            paths["validation_rules"],
            paths["readme"],
            paths["data_validation"],
            paths["test_data_validation"],
            digest("data_validation"),
            digest("repaired_test"),
        )


def test_pytest_loop_freezes_data_validation_but_allows_test_repairs() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    generate_all(store, workflow_id)

    failed = store.record_pytest_result(
        workflow_id,
        digest("data_validation"),
        digest("initial_test"),
        1,
        "uv run pytest -q test_data_validation.py tests",
        "fixture failed",
    )
    assert failed["pytest_verification"]["passed"] is False
    assert len(failed["pytest_verification"]["attempts"]) == 1

    passed = store.record_pytest_result(
        workflow_id,
        digest("data_validation"),
        digest("repaired_test"),
        0,
        "uv run pytest -q test_data_validation.py tests",
        "all passed",
    )
    assert passed["pytest_verification"]["passed"] is True
    assert passed["pytest_verification"]["test_data_validation_sha256"] == digest(
        "repaired_test"
    )

    with pytest.raises(WorkflowError, match="凍結版本不一致"):
        store.record_pytest_result(
            workflow_id,
            digest("unauthorized_data_change"),
            digest("repaired_test"),
            0,
            "pytest",
            "passed against changed production code",
        )


def test_data_validation_generator_is_immutable_after_first_generation() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    store.artifact_generated(
        workflow_id, "data_validation", digest("data_validation")
    )

    with pytest.raises(WorkflowError, match="已凍結"):
        store.artifact_generated(
            workflow_id, "data_validation", digest("changed_data_validation")
        )


def test_five_failed_pytest_attempts_require_human_resume() -> None:
    store = WorkflowStore()
    workflow_id, _spec, _rules = ready_for_confirmation(store)
    store.confirm(workflow_id)
    generate_all(store, workflow_id)

    snapshot = None
    for attempt in range(5):
        snapshot = store.record_pytest_result(
            workflow_id,
            digest("data_validation"),
            digest(f"test_attempt_{attempt}"),
            1,
            "pytest",
            f"failure {attempt}",
        )

    assert snapshot is not None
    assert snapshot["state"] == WorkflowState.blocked.value
    assert snapshot["blocked"]["resume_state"] == WorkflowState.generating_artifacts.value
    resumed = store.resume(workflow_id)
    assert resumed["state"] == WorkflowState.generating_artifacts.value


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
