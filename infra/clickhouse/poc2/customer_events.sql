-- Initializes poc2.customer_events.
CREATE DATABASE IF NOT EXISTS poc2 COMMENT 'Second local schema for production-shape simulations.';

CREATE TABLE IF NOT EXISTS poc2.customer_events
(
    event_id String,
    customer_id String,
    event_type LowCardinality(String),
    event_at DateTime,
    source_system LowCardinality(String),
    ingested_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (event_at, event_id)
COMMENT 'Customer activity events in the second simulated schema.';

INSERT INTO poc2.customer_events (event_id, customer_id, event_type, event_at, source_system)
SELECT *
FROM
(
    SELECT 'EVT-20001', 'CUS-9001', 'page_view', toDateTime('2026-07-10 09:00:00'), 'web'
    UNION ALL
    SELECT 'EVT-20002', 'CUS-9002', 'add_to_cart', toDateTime('2026-07-10 09:05:00'), 'web'
    UNION ALL
    SELECT 'EVT-20003', 'CUS-9003', 'app_open', toDateTime('2026-07-10 09:10:00'), 'mobile'
)
WHERE NOT EXISTS (SELECT 1 FROM poc2.customer_events);
