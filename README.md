# Data Validation Agent Local POC

This workspace provides a local POC for:

- ClickHouse database with a mock `poc.customer_orders` table.
- MariaDB database with a mock `poc.customer_accounts` table.
- Trino engine that can query both databases:
  - `clickhouse.poc.customer_orders`
  - `mariadb.poc.customer_accounts`

## Start ClickHouse, MariaDB, and Trino

```bash
docker compose up -d
```

Services:

| Service         | URL / Port               | Purpose                   |
| --------------- | ------------------------ | ------------------------- |
| ClickHouse      | `localhost:19000`        | Local OLAP database       |
| ClickHouse HTTP | `http://localhost:18123` | Local OLAP database       |
| MariaDB         | `localhost:13306`        | Local relational database |
| Trino HTTP      | `http://localhost:18080` | SQL engine over both DBs  |

The initialized mock tables are:

```text
clickhouse.poc.customer_orders
mariadb.poc.customer_accounts
```

## Verify Trino SQL

Trino's HTTP API can return the first response before query results are ready. If the response includes `nextUri`, the client must keep polling it until no `nextUri` is returned.

Create a `.env` file in the demo directory:

```bash
TRINO_URL=http://localhost:18080
TRINO_USER=poc_user
TRINO_SQL=
```

Run the Python demo:

```bash
python3 demo/trino_query.py
```

## Stop Services

```bash
docker compose down
```

To remove local database data as well:

```bash
docker compose down -v
```
