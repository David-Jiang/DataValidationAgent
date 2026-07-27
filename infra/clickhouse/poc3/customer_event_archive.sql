-- Initializes poc3.customer_event_archive.
CREATE DATABASE IF NOT EXISTS poc3 COMMENT 'Third local schema for production-shape simulations.';

CREATE TABLE IF NOT EXISTS poc3.customer_event_archive
(
    event_id String,
    customer_id String,
    event_type LowCardinality(String),
    event_date Date,
    archived_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (event_date, event_id)
COMMENT 'Archived customer activity events in the third simulated schema.';

INSERT INTO poc3.customer_event_archive (event_id, customer_id, event_type, event_date)
SELECT *
FROM
(
    SELECT 'EVT-10001', 'CUS-9001', 'signup', toDate('2026-01-12')
    UNION ALL
    SELECT 'EVT-10002', 'CUS-9002', 'signup', toDate('2026-03-05')
    UNION ALL
    SELECT 'EVT-10003', 'CUS-9003', 'signup', toDate('2026-06-18')
)
WHERE NOT EXISTS (SELECT 1 FROM poc3.customer_event_archive);
