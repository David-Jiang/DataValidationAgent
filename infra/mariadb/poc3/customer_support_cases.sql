-- Initializes poc3.customer_support_cases.
CREATE DATABASE IF NOT EXISTS poc3 COMMENT 'Third local schema for production-shape simulations.';

CREATE TABLE IF NOT EXISTS poc3.customer_support_cases
(
    case_id VARCHAR(32) NOT NULL,
    customer_id VARCHAR(32) NOT NULL,
    case_status VARCHAR(32) NOT NULL,
    opened_at DATETIME NOT NULL,
    resolved_at DATETIME NULL,
    PRIMARY KEY (case_id)
)
COMMENT = 'Customer support cases in the third simulated schema.';

INSERT INTO poc3.customer_support_cases
    (case_id, customer_id, case_status, opened_at, resolved_at)
SELECT *
FROM
(
    SELECT 'CASE-30001', 'CUS-9001', 'resolved', TIMESTAMP '2026-07-04 08:00:00', TIMESTAMP '2026-07-04 09:30:00'
    UNION ALL
    SELECT 'CASE-30002', 'CUS-9002', 'open', TIMESTAMP '2026-07-09 11:15:00', NULL
    UNION ALL
    SELECT 'CASE-30003', 'CUS-9003', 'pending', TIMESTAMP '2026-07-10 14:20:00', NULL
) AS seed
WHERE NOT EXISTS (SELECT 1 FROM poc3.customer_support_cases);
