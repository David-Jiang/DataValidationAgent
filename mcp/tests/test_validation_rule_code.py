from __future__ import annotations

import pytest

from core import validation_rules
from core.validation_rules import validate_row_rule_body


RULE_ID = "row.amount_required_when_status_paid"
VALID_RETURN = 'return df["amount"].notna()'


def test_valid_pandas_boolean_series_body_is_accepted() -> None:
    body = 'series = df["amount"]\nreturn series.notna()'
    assert validate_row_rule_body(RULE_ID, body) == body


def test_body_requires_valid_python_syntax() -> None:
    with pytest.raises(ValueError, match="語法錯誤"):
        validate_row_rule_body(RULE_ID, "return (")


def test_body_requires_return() -> None:
    with pytest.raises(ValueError, match="必須 return boolean Series"):
        validate_row_rule_body(RULE_ID, 'series = df["amount"]')


@pytest.mark.parametrize(
    "body",
    [
        f"import os\n{VALID_RETURN}",
        f"from os import path\n{VALID_RETURN}",
        f"def nested():\n    return True\n{VALID_RETURN}",
        f"class Nested:\n    pass\n{VALID_RETURN}",
        f"while True:\n    break\n{VALID_RETURN}",
        f"try:\n    value = 1\nexcept Exception:\n    value = 0\n{VALID_RETURN}",
        f"with manager:\n    value = 1\n{VALID_RETURN}",
        f"value = lambda item: item\n{VALID_RETURN}",
        f"raise ValueError()\n{VALID_RETURN}",
        f"yield 1\n{VALID_RETURN}",
    ],
)
def test_forbidden_python_syntax_is_rejected(body: str) -> None:
    with pytest.raises(ValueError, match="不允許"):
        validate_row_rule_body(RULE_ID, body)


@pytest.mark.parametrize("name", sorted(validation_rules._FORBIDDEN_NAMES))
def test_forbidden_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="不允許的名稱"):
        validate_row_rule_body(RULE_ID, f"{name}\n{VALID_RETURN}")


def test_dunder_name_and_attribute_are_rejected() -> None:
    with pytest.raises(ValueError, match="不允許的名稱"):
        validate_row_rule_body(RULE_ID, f"__secret\n{VALID_RETURN}")
    with pytest.raises(ValueError, match="不允許的屬性"):
        validate_row_rule_body(RULE_ID, f"df.__class__\n{VALID_RETURN}")


@pytest.mark.parametrize(
    "attribute", sorted(validation_rules._FORBIDDEN_ATTRIBUTES)
)
def test_forbidden_attributes_are_rejected(attribute: str) -> None:
    with pytest.raises(ValueError, match="不允許的屬性"):
        validate_row_rule_body(RULE_ID, f"df.{attribute}\n{VALID_RETURN}")
