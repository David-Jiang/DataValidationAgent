-- Initializes poc2.customer_profiles.
CREATE DATABASE IF NOT EXISTS poc2 COMMENT 'Second local schema for production-shape simulations.';

CREATE TABLE IF NOT EXISTS poc2.customer_profiles
(
    customer_id VARCHAR(32) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    customer_segment VARCHAR(32) NOT NULL,
    profile_updated_at DATETIME NOT NULL,
    PRIMARY KEY (customer_id)
)
COMMENT = 'Customer profiles in the second simulated schema.';

INSERT INTO poc2.customer_profiles
    (customer_id, display_name, customer_segment, profile_updated_at)
SELECT *
FROM
(
    SELECT 'CUS-9001', 'Alice Chen', 'high_value', TIMESTAMP '2026-07-10 10:00:00'
    UNION ALL
    SELECT 'CUS-9002', 'Ben Lin', 'growth', TIMESTAMP '2026-07-10 10:00:00'
    UNION ALL
    SELECT 'CUS-9003', 'Carol Wu', 'new', TIMESTAMP '2026-07-10 10:00:00'
) AS seed
WHERE NOT EXISTS (SELECT 1 FROM poc2.customer_profiles);
