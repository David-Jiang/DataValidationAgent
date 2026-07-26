-- Initializes poc.customer_accounts.
CREATE DATABASE IF NOT EXISTS poc COMMENT 'POC catalog database for local data validation demos.';

CREATE TABLE IF NOT EXISTS poc.customer_accounts
(
    customer_id VARCHAR(32) NOT NULL COMMENT 'Unique customer identifier used across source systems.',
    customer_email VARCHAR(255) NOT NULL COMMENT 'Primary customer email address captured during registration.',
    customer_name VARCHAR(120) NOT NULL COMMENT 'Customer display name used by support and account operations.',
    account_status VARCHAR(32) NOT NULL COMMENT 'Current account lifecycle state such as active, suspended, or closed.',
    signup_at DATETIME NOT NULL COMMENT 'Timestamp when the customer account was created.',
    last_login_at DATETIME NULL COMMENT 'Most recent successful login timestamp. Null means the customer has never logged in.',
    marketing_opt_in BOOLEAN NOT NULL COMMENT 'True when the customer agreed to receive marketing communication.',
    loyalty_tier VARCHAR(32) NOT NULL COMMENT 'Current loyalty program tier assigned by customer value rules.',
    country_code CHAR(2) NOT NULL COMMENT 'ISO 3166-1 alpha-2 customer country code.',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp when the row was last updated in MariaDB.',
    PRIMARY KEY (customer_id)
)
COMMENT = 'Mock customer account dimension table for validating MariaDB access through Trino.';

INSERT INTO poc.customer_accounts
    (
        customer_id,
        customer_email,
        customer_name,
        account_status,
        signup_at,
        last_login_at,
        marketing_opt_in,
        loyalty_tier,
        country_code
    )
SELECT *
FROM
(
    SELECT
        'CUS-9001' AS customer_id,
        'alice.chen@example.com' AS customer_email,
        'Alice Chen' AS customer_name,
        'active' AS account_status,
        TIMESTAMP '2026-01-12 09:10:00' AS signup_at,
        TIMESTAMP '2026-07-09 21:33:05' AS last_login_at,
        TRUE AS marketing_opt_in,
        'gold' AS loyalty_tier,
        'TW' AS country_code
    UNION ALL
    SELECT
        'CUS-9002',
        'ben.lin@example.com',
        'Ben Lin',
        'active',
        TIMESTAMP '2026-03-05 13:20:44',
        TIMESTAMP '2026-07-02 15:01:12',
        FALSE,
        'silver',
        'TW'
    UNION ALL
    SELECT
        'CUS-9003',
        'carol.wu@example.com',
        'Carol Wu',
        'active',
        TIMESTAMP '2026-06-18 18:45:39',
        NULL,
        TRUE,
        'standard',
        'JP'
) AS seed
WHERE NOT EXISTS (SELECT 1 FROM poc.customer_accounts);
