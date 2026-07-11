"""
DataHub client:呼叫 DataHub GraphQL API 取得 dataset schema。
Token 從環境變數讀取,不暴露給呼叫端(Claude)。
"""
from __future__ import annotations

import os

import httpx

DATAHUB_GMS_URL = os.environ.get("DATAHUB_GMS_URL", "")
DATAHUB_TOKEN = os.environ.get("DATAHUB_TOKEN", "")

_SCHEMA_QUERY = """
query getDataset($urn: String!) {
  dataset(urn: $urn) {
    name
    schemaMetadata {
      fields {
        fieldPath
        type
        nativeDataType
        description
      }
    }
  }
}
"""


class DataHubError(Exception):
    pass


def fetch_table_schema(dataset_urn: str) -> dict:
    """呼叫 DataHub API,回傳整理後的 schema 資訊。失敗時拋出 DataHubError。"""
    if not DATAHUB_GMS_URL or not DATAHUB_TOKEN:
        raise DataHubError(
            "DataHub 連線設定不完整,請確認環境變數 DATAHUB_GMS_URL 與 DATAHUB_TOKEN 已設定"
        )

    try:
        resp = httpx.post(
            f"{DATAHUB_GMS_URL}/api/graphql",
            json={"query": _SCHEMA_QUERY, "variables": {"urn": dataset_urn}},
            headers={"Authorization": f"Bearer {DATAHUB_TOKEN}"},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise DataHubError(
            f"DataHub API 回傳錯誤 (status={e.response.status_code}): {e.response.text[:300]}"
        ) from e
    except httpx.RequestError as e:
        raise DataHubError(f"無法連線到 DataHub API: {e}") from e

    payload = resp.json()
    if "errors" in payload:
        raise DataHubError(f"DataHub GraphQL 回傳錯誤: {payload['errors']}")

    dataset = payload.get("data", {}).get("dataset")
    if not dataset:
        raise DataHubError(f"找不到 dataset: {dataset_urn},請確認 URN 是否正確")

    fields = dataset.get("schemaMetadata", {}).get("fields", []) or []
    return {
        "dataset_urn": dataset_urn,
        "table_name": dataset.get("name"),
        "fields": [
            {
                "name": f["fieldPath"],
                "type": f.get("type"),
                "native_type": f.get("nativeDataType"),
                "description": f.get("description"),
            }
            for f in fields
        ],
    }
