from __future__ import annotations

from unittest.mock import Mock

import httpx
import pytest

from core import datahub_client
from core.datahub_client import DataHubError


DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,orders,PROD)"


@pytest.fixture(autouse=True)
def configured_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(datahub_client, "DATAHUB_HOST", "https://datahub.example")
    monkeypatch.setattr(datahub_client, "DATAHUB_TOKEN", "secret-token")


def response(payload: dict, status_code: int = 200, text: str = "") -> Mock:
    mock = Mock()
    mock.json.return_value = payload
    mock.text = text
    if status_code >= 400:
        request = httpx.Request("POST", "https://datahub.example/api/graphql")
        http_response = httpx.Response(status_code, request=request, text=text)
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad response", request=request, response=http_response
        )
    return mock


@pytest.mark.parametrize(
    ("host", "token"),
    [("", "token"), ("https://datahub.example", ""), ("", "")],
)
def test_missing_connection_settings_fail_before_request(
    monkeypatch: pytest.MonkeyPatch, host: str, token: str
) -> None:
    post = Mock()
    monkeypatch.setattr(datahub_client, "DATAHUB_HOST", host)
    monkeypatch.setattr(datahub_client, "DATAHUB_TOKEN", token)
    monkeypatch.setattr(datahub_client.httpx, "post", post)

    with pytest.raises(DataHubError, match="連線設定不完整"):
        datahub_client.fetch_table_schema(DATASET_URN)
    post.assert_not_called()


def test_success_maps_dataset_and_request(monkeypatch: pytest.MonkeyPatch) -> None:
    post = Mock(
        return_value=response(
            {
                "data": {
                    "dataset": {
                        "name": "orders",
                        "properties": {"description": "Order table"},
                        "schemaMetadata": {
                            "fields": [
                                {
                                    "fieldPath": "order_id",
                                    "type": "NUMBER",
                                    "nativeDataType": "BIGINT",
                                    "description": "Primary key",
                                    "nullable": False,
                                    "isPartOfKey": True,
                                }
                            ]
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setattr(datahub_client.httpx, "post", post)

    result = datahub_client.fetch_table_schema(DATASET_URN)

    assert result == {
        "table": "orders",
        "description": "Order table",
        "fields": [
            {
                "name": "order_id",
                "type": "NUMBER",
                "nativeType": "BIGINT",
                "description": "Primary key",
                "nullable": False,
                "isPartOfKey": True,
            }
        ],
    }
    kwargs = post.call_args.kwargs
    assert post.call_args.args == ("https://datahub.example/api/graphql",)
    assert kwargs["headers"] == {"Authorization": "Bearer secret-token"}
    assert kwargs["json"]["variables"] == {"urn": DATASET_URN}
    assert "query datasetSchema" in kwargs["json"]["query"]
    assert kwargs["timeout"] == 10


@pytest.mark.parametrize(
    "dataset",
    [
        {"name": "orders", "properties": None, "schemaMetadata": None},
        {"name": "orders"},
    ],
)
def test_missing_optional_metadata_returns_empty_values(
    monkeypatch: pytest.MonkeyPatch, dataset: dict
) -> None:
    monkeypatch.setattr(
        datahub_client.httpx,
        "post",
        Mock(return_value=response({"data": {"dataset": dataset}})),
    )
    assert datahub_client.fetch_table_schema(DATASET_URN) == {
        "table": "orders",
        "description": None,
        "fields": [],
    }


def test_http_error_is_wrapped_and_body_is_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    body = "x" * 400
    monkeypatch.setattr(
        datahub_client.httpx,
        "post",
        Mock(return_value=response({}, status_code=503, text=body)),
    )
    with pytest.raises(DataHubError) as exc_info:
        datahub_client.fetch_table_schema(DATASET_URN)
    message = str(exc_info.value)
    assert "status=503" in message
    assert "x" * 300 in message
    assert "x" * 301 not in message


def test_request_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://datahub.example/api/graphql")
    monkeypatch.setattr(
        datahub_client.httpx,
        "post",
        Mock(side_effect=httpx.ConnectError("offline", request=request)),
    )
    with pytest.raises(DataHubError, match="無法連線.*offline"):
        datahub_client.fetch_table_schema(DATASET_URN)


def test_graphql_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        datahub_client.httpx,
        "post",
        Mock(return_value=response({"errors": [{"message": "forbidden"}]})),
    )
    with pytest.raises(DataHubError, match="GraphQL 回傳錯誤.*forbidden"):
        datahub_client.fetch_table_schema(DATASET_URN)


@pytest.mark.parametrize("payload", [{"data": {"dataset": None}}, {"data": {}}, {}])
def test_missing_dataset_is_wrapped(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    monkeypatch.setattr(
        datahub_client.httpx,
        "post",
        Mock(return_value=response(payload)),
    )
    with pytest.raises(DataHubError, match="找不到 dataset"):
        datahub_client.fetch_table_schema(DATASET_URN)
