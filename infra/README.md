# Data Validation Agent - Infra

This workspace provides a local POC for:

- ClickHouse database with a mock `poc.customer_orders` table.
- MariaDB database with a mock `poc.customer_accounts` table.
- MinIO object storage for Iceberg tables in the `poc.customer_preferences` table.
- Trino 479 engine that can query all three data sources:
  - `clickhouse.poc.customer_orders`
  - `mariadb.poc.customer_accounts`
  - `minio.poc.customer_preferences`

## Start the infrastructure

```bash
docker compose up -d
```

Services:

| Service          | URL / Port               | Purpose                             |
| ---------------- | ------------------------ | ----------------------------------- |
| ClickHouse       | `localhost:19000`        | Local OLAP database                 |
| ClickHouse HTTP  | `http://localhost:18123` | Local OLAP database                 |
| MariaDB          | `localhost:13306`        | Local relational database           |
| MinIO API        | `http://localhost:19001` | S3-compatible object storage        |
| MinIO Console    | `http://localhost:19002` | MinIO web UI (`admin` / `password`) |
| Iceberg REST API | `http://localhost:19003` | Iceberg metadata catalog            |
| Trino HTTP       | `http://localhost:18080` | SQL engine over all data sources    |

Each direct subdirectory under `clickhouse/`, `mariadb/`, or `minio/`
represents a schema in the corresponding Trino catalog. For example:

```text
clickhouse/poc2/ -> schema clickhouse.poc2
mariadb/poc2/    -> schema mariadb.poc2
minio/poc2/      -> bucket poc2 -> schema minio.poc2
```

MinIO discovers directories and creates buckets during startup. After Trino is
healthy, `trino-init` scans every schema directory under all three data source
folders, creates the corresponding schema, and executes every `*.sql` file in
that directory.

- `clickhouse/{schema}/*.sql` contains ClickHouse-native SQL.
- `mariadb/{schema}/*.sql` contains MariaDB-native SQL. Use fully qualified
  table names such as `poc2.customer_accounts`; do not rely on `USE poc2`,
  because statements may use different JDBC connections.
- `minio/{schema}/*.sql` contains Trino SQL for Iceberg tables.

Each statement should end with a semicolon. A final statement without a
semicolon is also accepted. DDL should use `IF NOT EXISTS`, and seed inserts
should guard against duplicate rows, so rerunning `trino-init` is idempotent.
The local MariaDB Trino catalog uses the local `root` account so it can create
additional schemas. Do not use these development credentials in production.

### Add schemas and tables

Create schema directories as needed and add one SQL file per table:

```bash
mkdir -p clickhouse/poc2
mkdir -p mariadb/poc2
mkdir -p minio/poc2
```

```text
clickhouse/poc2/customer_events.sql
mariadb/poc2/customer_accounts.sql
minio/poc2/customer_segments.sql
```

If a new `minio/{schema}` directory was added, restart MinIO once so it creates
the matching bucket, and then run the complete initializer:

```bash
docker compose restart minio
docker compose up trino-init
```

When adding ClickHouse or MariaDB schemas/tables, or another SQL file to an
existing MinIO schema, MinIO does not need to restart. Run only:

```bash
docker compose up trino-init
```

`trino-init` creates missing schemas/tables and seed rows according to the SQL
files. It does not drop or replace existing tables, so existing data remains.

## Verify Trino SQL

Trino's HTTP API can return the first response before query results are ready. If the response includes `nextUri`, the client must keep polling it until no `nextUri` is returned.

```bash
set -a; source demo/.env; python3 demo/test-trino.py
```

## Stop Services

```bash
docker compose down
```

To remove local database data as well:

```bash
docker compose down -v
```

## Appendix: DataHub in Local

### Prerequisites

To install by DataHub CLI, Ref: [https://docs.datahub.com/docs/quickstart](https://docs.datahub.com/docs/quickstart)

```bash
datahub docker quickstart

# clean all
datahub docker nuke
```

### First, use portal to bind datasources

```text
http://localhost:9002

# Set source host as host.docker.internal:{port}
```

### Second, call GraphQL API

Get `clickhouse.poc.customer_orders`:

```bash
curl -s -X POST http://localhost:8080/api/graphql \
  -H "Content-Type: application/json" \
  --data '{
    "query": "query datasetSchema($urn: String!) { dataset(urn: $urn) { urn name properties { description } schemaMetadata { fields { fieldPath nativeDataType type description nullable isPartOfKey } } } }",
    "variables": {
      "urn": "urn:li:dataset:(urn:li:dataPlatform:clickhouse,poc.customer_orders,PROD)"
    }
  }'
```

Get `mariadb.poc.customer_accounts`:

```bash
curl -s -X POST http://localhost:8080/api/graphql \
  -H "Content-Type: application/json" \
  --data '{
    "query": "query datasetSchema($urn: String!) { dataset(urn: $urn) { urn name properties { description } schemaMetadata { fields { fieldPath nativeDataType type description nullable isPartOfKey } } } }",
    "variables": {
      "urn": "urn:li:dataset:(urn:li:dataPlatform:mariadb,poc.customer_accounts,PROD)"
    }
  }'
```
