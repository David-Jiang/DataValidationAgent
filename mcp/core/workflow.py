"""MCP Server POC 使用的記憶體內 validation workflow state machine。"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .models import FieldSpec


class WorkflowError(ValueError):
    """當 workflow 不存在或 state transition 無效時拋出。"""


class WorkflowState(str, Enum):
    awaiting_schema = "awaiting_schema"
    dataset_ready = "dataset_ready"
    drafting_spec = "drafting_spec"
    awaiting_confirmation = "awaiting_confirmation"
    confirmed = "confirmed"
    generating_artifacts = "generating_artifacts"
    completed = "completed"
    blocked = "blocked"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_field_spec(spec: FieldSpec) -> str:
    return json.dumps(
        spec.model_dump(mode="json", exclude_unset=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class WorkflowStore:
    """具 state transition 防護的 thread-safe、process-local key-value store。"""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def clear(self) -> None:
        """清除所有 workflow，供測試使用；Server 重啟也會產生相同效果。"""
        with self._lock:
            self._items.clear()

    def start(self, dataset_urn: str) -> dict[str, Any]:
        dataset_urn = dataset_urn.strip()
        if not dataset_urn:
            raise WorkflowError("dataset_urn 不可為空")

        workflow_id = f"dva_{uuid.uuid4().hex}"
        now = _now()
        record: dict[str, Any] = {
            "workflow_id": workflow_id,
            "state": WorkflowState.awaiting_schema.value,
            "dataset_urn": dataset_urn,
            "created_at": now,
            "updated_at": now,
            "upstream_schema": None,
            "upstream_schema_sha256": None,
            "field_spec_contract_sha256": None,
            "field_spec_json": None,
            "field_spec_sha256": None,
            "confirmation": None,
            "generated_artifacts": {
                "validation_suite": False,
                "mock_data": False,
            },
            "delivered_artifacts": {},
            "blocked": None,
            "history": [],
        }
        self._append_event(record, "workflow_started")
        with self._lock:
            self._items[workflow_id] = record
        return self.snapshot(workflow_id)

    def snapshot(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            snapshot = deepcopy(record)
        snapshot.pop("field_spec_json", None)
        snapshot.pop("upstream_schema", None)
        return snapshot

    def dataset_urn(self, workflow_id: str) -> str:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.awaiting_schema)
            return str(record["dataset_urn"])

    def schema_loaded(self, workflow_id: str, schema: dict[str, Any]) -> dict[str, Any]:
        canonical = json.dumps(
            schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.awaiting_schema)
            record["upstream_schema"] = deepcopy(schema)
            record["upstream_schema_sha256"] = _sha256_text(canonical)
            self._transition(record, WorkflowState.dataset_ready, "schema_loaded")
            return self.snapshot(workflow_id)

    def contract_loaded(self, workflow_id: str, contract_text: str) -> dict[str, Any]:
        allowed = {
            WorkflowState.dataset_ready,
            WorkflowState.drafting_spec,
            WorkflowState.awaiting_confirmation,
            WorkflowState.confirmed,
        }
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, *allowed)
            record["field_spec_contract_sha256"] = _sha256_text(contract_text)
            record["confirmation"] = None
            record["generated_artifacts"] = {
                "validation_suite": False,
                "mock_data": False,
            }
            record["delivered_artifacts"] = {}
            self._transition(record, WorkflowState.drafting_spec, "contract_loaded")
            return self.snapshot(workflow_id)

    def submit_spec(self, workflow_id: str, spec: FieldSpec) -> dict[str, Any]:
        canonical = canonical_field_spec(spec)
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.drafting_spec)
            if not record["field_spec_contract_sha256"]:
                raise WorkflowError("尚未載入 field_spec 規格")
            record["field_spec_json"] = canonical
            record["field_spec_sha256"] = _sha256_text(canonical)
            record["confirmation"] = None
            self._transition(
                record, WorkflowState.awaiting_confirmation, "field_spec_submitted"
            )
            return self.snapshot(workflow_id)

    def confirm(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.awaiting_confirmation)
            spec_hash = record["field_spec_sha256"]
            if not spec_hash:
                raise WorkflowError("沒有可確認的 field_spec")
            record["confirmation"] = {
                "field_spec_sha256": spec_hash,
                "confirmed_at": _now(),
                "confirmed_by": "human_via_agent",
            }
            self._transition(record, WorkflowState.confirmed, "field_spec_confirmed")
            return self.snapshot(workflow_id)

    def field_spec(self, workflow_id: str) -> FieldSpec:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(
                record,
                WorkflowState.confirmed,
                WorkflowState.generating_artifacts,
            )
            confirmation = record["confirmation"]
            if (
                not confirmation
                or confirmation["field_spec_sha256"] != record["field_spec_sha256"]
            ):
                raise WorkflowError("目前 field_spec 尚未獲得有效確認")
            raw = record["field_spec_json"]
        if not raw:
            raise WorkflowError("workflow 沒有正式的 field_spec")
        return FieldSpec(**json.loads(raw))

    def artifact_generated(self, workflow_id: str, artifact: str) -> dict[str, Any]:
        if artifact not in {"validation_suite", "mock_data"}:
            raise WorkflowError(f"未知的 artifact：{artifact}")
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(
                record,
                WorkflowState.confirmed,
                WorkflowState.generating_artifacts,
            )
            record["generated_artifacts"][artifact] = True
            self._transition(
                record,
                WorkflowState.generating_artifacts,
                f"{artifact}_generated",
            )
            return self.snapshot(workflow_id)

    def expected_artifact_paths(self, workflow_id: str) -> dict[str, str]:
        spec = self.field_spec(workflow_id)
        root = f"artifacts/{workflow_id}"
        return {
            "validation_suite": f"{root}/{spec.table_name}_validation_suite.json",
            "mock_data": f"{root}/{spec.table_name}_mock.csv",
        }

    def complete(
        self, workflow_id: str, suite_path: str, mock_path: str = ""
    ) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.generating_artifacts)
            if not record["generated_artifacts"]["validation_suite"]:
                raise WorkflowError("尚未產生 validation suite")

        expected = self.expected_artifact_paths(workflow_id)
        if suite_path != expected["validation_suite"]:
            raise WorkflowError(
                f"suite_path 必須是 {expected['validation_suite']}"
            )

        with self._lock:
            record = self._require(workflow_id)
            mock_generated = record["generated_artifacts"]["mock_data"]
            if mock_generated and mock_path != expected["mock_data"]:
                raise WorkflowError(f"mock_path 必須是 {expected['mock_data']}")
            if not mock_generated and mock_path:
                raise WorkflowError("尚未產生 mock data，不可登記 mock_path")

            delivered = {"validation_suite": suite_path}
            if mock_generated:
                delivered["mock_data"] = mock_path
            record["delivered_artifacts"] = delivered
            self._transition(record, WorkflowState.completed, "workflow_completed")
            return self.snapshot(workflow_id)

    def block(
        self, workflow_id: str, error: str, resume_state: WorkflowState
    ) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            record["blocked"] = {
                "error": error,
                "resume_state": resume_state.value,
                "blocked_at": _now(),
            }
            self._transition(record, WorkflowState.blocked, "workflow_blocked")
            return self.snapshot(workflow_id)

    def resume(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.blocked)
            blocked = record["blocked"]
            if not blocked:
                raise WorkflowError("workflow 沒有可恢復的 blocked 狀態")
            target = WorkflowState(blocked["resume_state"])
            record["blocked"] = None
            self._transition(record, target, "workflow_resumed")
            return self.snapshot(workflow_id)

    def _require(self, workflow_id: str) -> dict[str, Any]:
        try:
            return self._items[workflow_id]
        except KeyError as exc:
            raise WorkflowError(f"找不到 workflow_id：{workflow_id}") from exc

    @staticmethod
    def _require_state(
        record: dict[str, Any], *states: WorkflowState
    ) -> None:
        allowed = {state.value for state in states}
        if record["state"] not in allowed:
            expected = ", ".join(sorted(allowed))
            raise WorkflowError(
                f"workflow {record['workflow_id']} 目前 state={record['state']}；"
                f"此操作只允許 state={expected}"
            )

    @staticmethod
    def _append_event(record: dict[str, Any], event: str) -> None:
        record["history"].append(
            {"event": event, "state": record["state"], "at": _now()}
        )

    def _transition(
        self, record: dict[str, Any], state: WorkflowState, event: str
    ) -> None:
        record["state"] = state.value
        record["updated_at"] = _now()
        self._append_event(record, event)


workflow_store = WorkflowStore()
