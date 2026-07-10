# DataHub in Local

## Prerequisites

To install by DataHub CLI, Ref: [https://docs.datahub.com/docs/quickstart](https://docs.datahub.com/docs/quickstart)

```bash
datahub docker quickstart

# clean all
datahub docker nuke
```

## Step

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
