"""MCP Server POC 使用的記憶體內 validation workflow state machine。"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .models import FieldSpec
from .validation_rules import ValidationRules, canonical_validation_rules

_WORKFLOW_ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
_WORKFLOW_ID_SPACE = len(_WORKFLOW_ID_ALPHABET) ** 4
_REQUIRED_ARTIFACTS = (
    "validation_rules",
    "readme",
    "data_validation",
    "test_data_validation",
)


class WorkflowError(ValueError):
    """當 workflow 不存在或 state transition 無效時拋出。"""


class WorkflowState(str, Enum):
    awaiting_schema = "awaiting_schema"
    dataset_ready = "dataset_ready"
    drafting_rules = "drafting_rules"
    awaiting_confirmation = "awaiting_confirmation"
    confirmed = "confirmed"
    generating_artifacts = "generating_artifacts"
    completed = "completed"
    blocked = "blocked"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _workflow_date() -> str:
    """使用 UTC 日期，避免 Server 時區不同造成 workflow_id 含義不一致。"""
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _base36_suffix(value: int) -> str:
    chars = []
    for _ in range(4):
        value, remainder = divmod(value, len(_WORKFLOW_ID_ALPHABET))
        chars.append(_WORKFLOW_ID_ALPHABET[remainder])
    return "".join(reversed(chars))


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

        with self._lock:
            workflow_id = self._new_workflow_id()
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
                "validation_rules_json": None,
                "validation_rules_sha256": None,
                "confirmation": None,
                "generated_artifacts": {
                    artifact: False for artifact in _REQUIRED_ARTIFACTS
                },
                "delivered_artifacts": {},
                "blocked": None,
                "history": [],
            }
            self._append_event(record, "workflow_started")
            self._items[workflow_id] = record
        return self.snapshot(workflow_id)

    def snapshot(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            snapshot = deepcopy(record)
        snapshot.pop("field_spec_json", None)
        snapshot.pop("validation_rules_json", None)
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
            WorkflowState.drafting_rules,
            WorkflowState.awaiting_confirmation,
            WorkflowState.confirmed,
            WorkflowState.generating_artifacts,
        }
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, *allowed)
            record["field_spec_contract_sha256"] = _sha256_text(contract_text)
            record["confirmation"] = None
            record["validation_rules_json"] = None
            record["validation_rules_sha256"] = None
            record["generated_artifacts"] = {
                artifact: False for artifact in _REQUIRED_ARTIFACTS
            }
            record["delivered_artifacts"] = {}
            self._transition(record, WorkflowState.drafting_rules, "contract_loaded")
            return self.snapshot(workflow_id)

    def dataset_reference(self, workflow_id: str) -> str:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.drafting_rules)
            return str(record["dataset_urn"])

    def submit_rules(
        self,
        workflow_id: str,
        spec: FieldSpec,
        rules: ValidationRules,
    ) -> dict[str, Any]:
        canonical_spec = canonical_field_spec(spec)
        canonical_rules = canonical_validation_rules(rules)
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.drafting_rules)
            if not record["field_spec_contract_sha256"]:
                raise WorkflowError("尚未載入 field_spec 規格")
            if rules.dataset.urn != record["dataset_urn"]:
                raise WorkflowError("validation rules 的 dataset URN 與 workflow 不一致")
            record["field_spec_json"] = canonical_spec
            record["field_spec_sha256"] = _sha256_text(canonical_spec)
            record["validation_rules_json"] = canonical_rules
            record["validation_rules_sha256"] = _sha256_text(canonical_rules)
            record["confirmation"] = None
            self._transition(
                record,
                WorkflowState.awaiting_confirmation,
                "validation_rules_submitted",
            )
            return self.snapshot(workflow_id)

    def confirm(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.awaiting_confirmation)
            spec_hash = record["field_spec_sha256"]
            rules_hash = record["validation_rules_sha256"]
            if not spec_hash or not rules_hash:
                raise WorkflowError("沒有可確認的 col_rules 與 row_rules")
            record["confirmation"] = {
                "field_spec_sha256": spec_hash,
                "validation_rules_sha256": rules_hash,
                "confirmed_at": _now(),
                "confirmed_by": "human_via_agent",
            }
            self._transition(
                record, WorkflowState.confirmed, "validation_rules_confirmed"
            )
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
                or confirmation["validation_rules_sha256"]
                != record["validation_rules_sha256"]
            ):
                raise WorkflowError("目前 col_rules 與 row_rules 尚未獲得有效確認")
            raw = record["field_spec_json"]
        if not raw:
            raise WorkflowError("workflow 沒有正式的 field_spec")
        return FieldSpec(**json.loads(raw))

    def validation_rules(self, workflow_id: str) -> ValidationRules:
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
                or confirmation["validation_rules_sha256"]
                != record["validation_rules_sha256"]
            ):
                raise WorkflowError("目前 validation rules 尚未獲得有效確認")
            raw = record["validation_rules_json"]
        if not raw:
            raise WorkflowError("workflow 沒有正式的 validation rules")
        return ValidationRules(**json.loads(raw))

    def pending_validation_rules(self, workflow_id: str) -> ValidationRules:
        """只供人工確認畫面讀取已提交、尚未確認的完整規則。"""
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.awaiting_confirmation)
            raw = record["validation_rules_json"]
        if not raw:
            raise WorkflowError("workflow 沒有待確認的 validation rules")
        return ValidationRules(**json.loads(raw))

    def artifact_generated(self, workflow_id: str, artifact: str) -> dict[str, Any]:
        if artifact not in _REQUIRED_ARTIFACTS:
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
        self.validation_rules(workflow_id)
        root = f"artifacts/{workflow_id}"
        return {
            "validation_rules": f"{root}/validation_rules.json",
            "readme": f"{root}/README.md",
            "data_validation": f"{root}/data_validation.py",
            "test_data_validation": f"{root}/test_data_validation.py",
        }

    def complete(
        self,
        workflow_id: str,
        validation_rules_path: str,
        readme_path: str,
        data_validation_path: str,
        test_data_validation_path: str,
    ) -> dict[str, Any]:
        with self._lock:
            record = self._require(workflow_id)
            self._require_state(record, WorkflowState.generating_artifacts)
            missing = [
                artifact
                for artifact in _REQUIRED_ARTIFACTS
                if not record["generated_artifacts"][artifact]
            ]
            if missing:
                raise WorkflowError(f"尚未產生必要 artifacts：{', '.join(missing)}")

        expected = self.expected_artifact_paths(workflow_id)
        submitted = {
            "validation_rules": validation_rules_path,
            "readme": readme_path,
            "data_validation": data_validation_path,
            "test_data_validation": test_data_validation_path,
        }
        for artifact, path in submitted.items():
            if path != expected[artifact]:
                raise WorkflowError(f"{artifact}_path 必須是 {expected[artifact]}")

        with self._lock:
            record = self._require(workflow_id)
            record["delivered_artifacts"] = submitted
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

    def _new_workflow_id(self) -> str:
        """建立日期加四碼 suffix，並以完整 suffix 空間探查確保目前 process 內唯一。"""
        date = _workflow_date()
        start = secrets.randbelow(_WORKFLOW_ID_SPACE)
        for offset in range(_WORKFLOW_ID_SPACE):
            suffix = _base36_suffix((start + offset) % _WORKFLOW_ID_SPACE)
            workflow_id = f"dva_{date}_{suffix}"
            if workflow_id not in self._items:
                return workflow_id
        raise WorkflowError(f"{date} 的 workflow_id 四碼空間已用盡")

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
