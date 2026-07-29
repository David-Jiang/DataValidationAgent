# Data Validation Agent－本機基礎設施

本目錄提供一套本機 POC 環境，包含：

- ClickHouse，內建範例資料表 `poc.customer_orders`。
- MariaDB，內建範例資料表 `poc.customer_accounts`。
- MinIO，儲存 Iceberg 資料；metadata 由 Hive Metastore 與一套獨立的內部 MariaDB 管理。
- Trino 479，可同時查詢以下三種資料來源：
  - `clickhouse.poc.customer_orders`
  - `mariadb.poc.customer_accounts`
  - `minio.poc.customer_preferences`

## 啟動基礎設施

```bash
docker compose up -d --build
```

服務資訊：

| 服務                   | URL／Port                | 用途                                  |
| ---------------------- | ------------------------ | ------------------------------------- |
| ClickHouse             | `localhost:18123`        | 本機 OLAP database                    |
| ClickHouse HTTP        | `http://localhost:19000` | ClickHouse HTTP 介面                  |
| MariaDB                | `localhost:13306`        | 本機關聯式 database                   |
| MinIO API              | `http://localhost:19001` | S3 相容物件儲存                       |
| MinIO Console          | `http://localhost:19002` | MinIO 管理介面（`admin`／`password`） |
| Hive Metastore         | 僅限容器內部             | 透過 Thrift 提供 Iceberg catalog      |
| Hive Metastore MariaDB | 僅限容器內部             | 專用的 Hive Metastore metadata DB     |
| Trino HTTP             | `http://localhost:18080` | 僅限 Trino 主機本機測試               |
| Trino HTTPS            | `https://<主機 IP>:443`  | 供另一台開發機上的 Airflow 連線       |

MinIO／Iceberg 的架構如下：

```text
Trino -> Hive Metastore -> 專用 MariaDB metadata database
  |
  +-> MinIO（Iceberg metadata 與 Parquet data files）
```

Hive Metastore 與專用 MariaDB 都不開放 host port。metadata database 使用獨立的 `hive-metastore-db-data` volume，不會與存放業務範例資料的 MariaDB 共用。

本機 Hive Metastore image 以固定版本 `srchangb/hive-metastore:20251203-openssl2.1.4` 為 base image，包含 Hive Metastore 3.0.0 與 Hadoop 3.3.3。該 image 僅提供 `linux/amd64`，所以 Apple Silicon 上的 Docker Desktop 會使用 amd64 模擬執行。

衍生 image 會將原本的 MySQL JDBC jar 替換成 MariaDB Connector/J 3.5.6，並將 catalog 存入專用的 `metastore_v3` database。Dockerfile 也修正了原始 entrypoint 每次啟動都執行 `initSchema` 的行為：重啟時只檢查 metastore schema version，只有全新、尚未初始化的 database 才會執行 `initSchema`。

## Schema 與 SQL 目錄規則

`clickhouse/`、`mariadb/`、`minio/` 下的每個第一層子目錄，都代表對應 Trino catalog 中的一個 schema。例如：

```text
clickhouse/poc2/ -> schema clickhouse.poc2
mariadb/poc2/    -> schema mariadb.poc2
minio/poc2/      -> bucket poc2 -> schema minio.poc2
minio/poc_ab_cd/ -> bucket poc-ab-cd -> schema minio.poc_ab_cd
```

MinIO bucket name 不允許底線 `_`。`minio/{schema}` 目錄名稱包含底線時，啟動程序會在建立 bucket 時自動轉成連字號 `-`，但 Trino schema 仍保留原本名稱。請勿同時建立 `poc_ab` 與 `poc-ab` 這類會映射到相同 bucket 的目錄；初始化程序偵測到衝突時會停止並顯示錯誤。

目前提供三組模擬 schema，每種 datasource 各有一張範例資料表：

| Schema | ClickHouse table         | MariaDB table            | MinIO／Iceberg table         |
| ------ | ------------------------ | ------------------------ | ---------------------------- |
| `poc`  | `customer_orders`        | `customer_accounts`      | `customer_preferences`       |
| `poc2` | `customer_events`        | `customer_profiles`      | `customer_segments`          |
| `poc3` | `customer_event_archive` | `customer_support_cases` | `customer_engagement_scores` |

MinIO 啟動時會掃描目錄並建立對應 bucket。Trino 進入 healthy 狀態後，`trino-init` 會掃描三種 datasource 下的所有 schema 目錄、建立對應 schema，並依序執行目錄中的每個 `*.sql`：

- `clickhouse/{schema}/*.sql`：放置 ClickHouse 原生 SQL。
- `mariadb/{schema}/*.sql`：放置 MariaDB 原生 SQL。請使用 `poc2.customer_accounts` 這類完整 table name，不要依賴 `USE poc2`，因為不同 statement 可能使用不同 JDBC connection。
- `minio/{schema}/*.sql`：放置由 Trino 執行的 Iceberg SQL。

每個 statement 應以分號結尾，最後一個 statement 沒有分號也能執行。DDL 應使用 `IF NOT EXISTS`，seed data 的 `INSERT` 也應避免重複寫入，確保重跑 `trino-init` 時保持冪等。

本機 MariaDB 的 Trino catalog 使用本機 `root` 帳號，以便建立其他 schema。這些開發環境帳號與密碼不可直接用於 production。

### 新增 schema 與 table

依需求建立 schema 目錄，每張 table 放置一個 SQL file：

```bash
mkdir -p clickhouse/poc2
mkdir -p mariadb/poc2
mkdir -p minio/poc2
```

```text
clickhouse/poc2/customer_events.sql
mariadb/poc2/customer_profiles.sql
minio/poc2/customer_segments.sql
```

如果新增了 `minio/{schema}` 目錄，先重啟一次 MinIO，讓啟動程序建立同名 bucket，再執行完整初始化：

```bash
docker compose restart minio
docker compose up trino-init
```

如果只是新增 ClickHouse 或 MariaDB 的 schema／table，或在既有 MinIO schema 加入另一個 SQL file，MinIO 不需要重啟，只需執行：

```bash
docker compose up trino-init
```

`trino-init` 會根據 SQL files 建立缺少的 schema、table 與 seed data，不會刪除或取代既有 table，因此原有資料會保留。

若要調整既有 table，請加入可重複執行的 statement，例如 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`。只修改 `CREATE TABLE IF NOT EXISTS` 的內容不會變更已存在的 table。

### 重新初始化 poc、poc2 與 poc3

三個 schema 目錄都會被動態偵測。重啟 MinIO 會重新掃描並補建 `poc`、`poc2`、`poc3` buckets，接著由 `trino-init` 重新執行所有 DDL files：

```bash
docker compose restart minio
docker compose up trino-init
```

以上指令可以安全地重複執行。一般 restart 不會刪除 named volumes，因此 ClickHouse rows、MariaDB rows、Hive Metastore registrations 與 MinIO objects 都會保留。

## 驗證 Trino SQL

Trino 連線設定與示範 SQL 都直接定義在 `demo/test-trino.py` 上方，執行：

```bash
python3 demo/test-trino.py
```

範例程式會透過 Trino JOIN 以下三張 table：

```text
clickhouse.poc.customer_orders
mariadb.poc.customer_accounts
minio.poc.customer_preferences
```

## 停止服務

停止容器並保留資料：

```bash
docker compose down
```

停止容器並刪除本機 database 與 MinIO 資料：

```bash
docker compose down -v
```

> `docker compose down -v` 會刪除 named volumes，其中的 ClickHouse、MariaDB、Hive Metastore 與 MinIO 資料都無法由 Docker Compose 自動復原。

## 修改 Trino 密碼

`trino/config/password.db` 只保存 bcrypt hash，不保存明文密碼。若要修改 `poc_user` 的密碼，請在 `infra` 目錄執行：

```bash
htpasswd -B -C 10 trino/config/password.db poc_user
```

指令會互動式要求輸入並確認新密碼，因此新密碼不會出現在 shell history。`-B` 代表使用 bcrypt，`-C 10` 是 Trino 支援的 bcrypt cost。若 Linux 尚未提供 `htpasswd`，Debian／Ubuntu 的套件名稱是 `apache2-utils`，RHEL 系列的套件名稱是 `httpd-tools`。

產生新 hash 後，將同一組明文密碼同步到以下位置：

```text
docker-compose.yml -> trino-init.environment.TRINO_PASSWORD
demo/test-trino.py -> TRINO_PASSWORD
```

接著只需重新建立 Trino 並重跑初始化程序：

```bash
docker compose up -d --no-deps --force-recreate trino
docker compose up --no-deps --force-recreate trino-init
```

最後以互動方式輸入新密碼驗證 HTTPS，避免將密碼直接寫入指令：

```bash
curl -k --user poc_user https://<主機 IP>:443/v1/info
```

啟動後可分別驗證：

```bash
curl --header "X-Trino-User: poc_user" http://localhost:18080/v1/info
curl -k --user poc_user:password https://<主機 IP>:443/v1/info
```

## 附錄：本機 DataHub

### 前置需求

透過 DataHub CLI 安裝，請參考 [DataHub Quickstart](https://docs.datahub.com/docs/quickstart)：

```bash
datahub docker quickstart

# 清除全部 DataHub 資料
datahub docker nuke
```

### 第一步：透過管理介面綁定 datasources

```text
http://localhost:9002

# datasource host 請設定為 host.docker.internal:{port}
```

### 第二步：呼叫 GraphQL API

取得 `clickhouse.poc.customer_orders`：

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

取得 `mariadb.poc.customer_accounts`：

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
