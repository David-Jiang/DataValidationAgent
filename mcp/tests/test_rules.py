from __future__ import annotations

import json

import pytest

from core.rules import parse_row_rules


def row_rule(**overrides) -> dict:
    return {
        "id": "row.code_required_when_alt_empty",
        "desc": "alt 為空字串時，code 不可為 null",
        "columns": ["alt", "code"],
        "examples": {
            "pass": [{"name": "code 有值", "sql": "alt = '' AND code IS NOT NULL"}],
            "fail": [{"name": "code 缺值", "sql": "alt = '' AND code IS NULL"}],
        },
        **overrides,
    }


def test_parse_row_rules_returns_valid_minimal_contract() -> None:
    submitted = row_rule()
    parsed = parse_row_rules(json.dumps([submitted]))
    assert parsed[0].model_dump(mode="json", by_alias=True) == submitted


def test_parse_row_rules_reports_invalid_json() -> None:
    with pytest.raises(ValueError, match="不是合法的 JSON"):
        parse_row_rules("{")


def test_parse_row_rules_requires_top_level_array() -> None:
    with pytest.raises(ValueError, match="最外層必須是 array"):
        parse_row_rules(json.dumps(row_rule()))


@pytest.mark.parametrize(
    "rule_id",
    ["col.not_a_row_rule", "row.-leading", "row.trailing-", "row.two..dots"],
)
def test_parse_row_rules_rejects_invalid_or_restricted_ids(rule_id: str) -> None:
    with pytest.raises(ValueError, match="row_rules|id 格式錯誤"):
        parse_row_rules(json.dumps([row_rule(id=rule_id)]))


def test_parse_row_rules_requires_at_least_two_columns() -> None:
    with pytest.raises(ValueError, match="至少包含兩個欄位"):
        parse_row_rules(json.dumps([row_rule(columns=["code"])]))


def test_parse_row_rules_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="重複 id"):
        parse_row_rules(json.dumps([row_rule(), row_rule()]))


@pytest.mark.parametrize(
    "overrides",
    [
        {"desc": "   "},
        {"desc": "看不見的字元\u200b"},
        {"columns": ["alt", "code\u0000"]},
        {
            "examples": {
                "pass": [{"name": "名稱\n換行", "sql": "code IS NOT NULL"}],
                "fail": [{"name": "失敗", "sql": "code IS NULL"}],
            }
        },
    ],
)
def test_parse_row_rules_rejects_blank_control_or_invisible_text(
    overrides: dict,
) -> None:
    with pytest.raises(ValueError, match="不可為空|控制或不可見字元"):
        parse_row_rules(json.dumps([row_rule(**overrides)]))
