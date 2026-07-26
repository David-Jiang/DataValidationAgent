import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TRINO_URL = os.environ.get("TRINO_URL", "http://localhost:18080")
TRINO_USER = os.environ.get("TRINO_USER", "poc_user")
SQL = os.environ.get("TRINO_SQL")


def trino_request(url, method="GET", body=None):
    data = body.encode("utf-8") if body is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "X-Trino-User": TRINO_USER,
            "Content-Type": "text/plain",
        },
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
    if not SQL:
        raise SystemExit("TRINO_SQL environment variable is required")

    columns, rows = run_query(SQL)
    headers = [column["name"] for column in columns]
    if headers:
        print("\t".join(headers))
    for row in rows:
        print("\t".join("" if value is None else str(value) for value in row))


if __name__ == "__main__":
    main()
