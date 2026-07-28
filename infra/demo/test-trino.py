import base64
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TRINO_URL = "http://localhost:18080"
TRINO_USER = "poc_user"
TRINO_PASSWORD = "password"
SQL = """SELECT
    o.order_id,
    o.customer_id,
    a.customer_name,
    o.order_status,
    p.preferred_contact_channel,
    p.preferred_language,
    p.personalization_enabled
FROM clickhouse.poc.customer_orders o
JOIN mariadb.poc.customer_accounts a
    ON o.customer_id = a.customer_id
JOIN minio.poc.customer_preferences p
    ON o.customer_id = p.customer_id
ORDER BY o.order_id"""


def trino_request(url, method="GET", body=None):
    data = body.encode("utf-8") if body is not None else None
    headers = {
        "X-Trino-User": TRINO_USER,
        "Content-Type": "text/plain",
    }
    if url.lower().startswith("https://"):
        credentials = base64.b64encode(
            f"{TRINO_USER}:{TRINO_PASSWORD}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {credentials}"

    request = Request(
        url,
        data=data,
        method=method,
        headers=headers,
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Trino HTTP request failed: HTTP {exc.code}: {detail}") from exc


def run_query(sql):
    result = trino_request(f"{TRINO_URL.rstrip('/')}/v1/statement", method="POST", body=sql)
    columns = result.get("columns")
    rows = []

    while True:
        if columns is None and result.get("columns"):
            columns = result["columns"]
        rows.extend(result.get("data", []))

        if result.get("error"):
            raise RuntimeError(json.dumps(result["error"], indent=2))

        next_uri = result.get("nextUri")
        if not next_uri:
            break

        time.sleep(0.2)
        result = trino_request(next_uri)

    return columns or [], rows


def main():
    columns, rows = run_query(SQL)
    headers = [column["name"] for column in columns]
    if headers:
        print("\t".join(headers))
    for row in rows:
        print("\t".join("" if value is None else str(value) for value in row))


if __name__ == "__main__":
    main()
