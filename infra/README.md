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

Each direct subdirectory under `minio/` represents both a MinIO bucket and a
schema in the `minio` Trino catalog. For example:

```text
minio/poc/  -> bucket poc  -> schema minio.poc
minio/poc2/ -> bucket poc2 -> schema minio.poc2
minio/poc3/ -> bucket poc3 -> schema minio.poc3
```

MinIO discovers directories and creates buckets during startup. After Trino is
healthy, `trino-init` independently scans every `minio/*/` directory, creates
the corresponding schema, and executes every `*.sql` file in that directory.

### Add a MinIO catalog and tables

Create the catalog directory and add one SQL file per table:

```bash
mkdir -p minio/poc2
```

```text
minio/poc2/customer_segments.sql
```

Run the complete refresh operation:

```bash
docker compose restart minio
docker compose up trino-init
```

When only adding another SQL file to an existing catalog, MinIO does not need to
restart. Rerun only:

```bash
docker compose up trino-init
```

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
