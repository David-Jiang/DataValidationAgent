from __future__ import annotations

import unittest
from unittest.mock import patch

from core import datahub_client


class DataHubClientTest(unittest.TestCase):
    @patch("core.datahub_client.httpx.post")
    def test_request_uses_timeout(self, post) -> None:
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "data": {
                "dataset": {
                    "name": "orders",
                    "properties": {"description": None},
                    "schemaMetadata": {"fields": []},
                }
            }
        }

        with (
            patch.object(datahub_client, "DATAHUB_HOST", "https://datahub.example"),
            patch.object(datahub_client, "DATAHUB_TOKEN", "token"),
        ):
            datahub_client.fetch_table_schema("urn:li:dataset:test")

        self.assertEqual(10, post.call_args.kwargs["timeout"])


if __name__ == "__main__":
    unittest.main()
