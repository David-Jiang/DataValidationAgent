-- Initializes poc.customer_orders.
CREATE DATABASE IF NOT EXISTS poc COMMENT 'POC catalog database for local data validation demos.';

CREATE TABLE IF NOT EXISTS poc.customer_orders
(
    order_id String COMMENT 'Unique order identifier from the upstream order system.',
    customer_id String COMMENT 'Unique customer identifier used to join customer profile data.',
    customer_email String COMMENT 'Customer contact email captured at checkout time.',
    order_status LowCardinality(String) COMMENT 'Current lifecycle state of the order, such as created, paid, shipped, delivered, or cancelled.',
    order_created_at DateTime COMMENT 'Timestamp when the order was created in the source application.',
    order_paid_at Nullable(DateTime) COMMENT 'Timestamp when payment was completed. Null means the order has not been paid.',
    product_sku String COMMENT 'Purchased product stock keeping unit.',
    product_name String COMMENT 'Human-readable product name at the time of purchase.',
    quantity UInt32 COMMENT 'Number of product units included in the order line.',
    unit_price Decimal(12, 2) COMMENT 'Single-unit selling price in the order currency.',
    discount_amount Decimal(12, 2) COMMENT 'Discount amount applied to this order line.',
    currency FixedString(3) COMMENT 'ISO 4217 currency code for all monetary values on the row.',
    payment_method LowCardinality(String) COMMENT 'Payment channel selected by the customer, such as credit_card, bank_transfer, or wallet.',
    shipping_country FixedString(2) COMMENT 'ISO 3166-1 alpha-2 destination country code.',
    is_first_order Bool COMMENT 'True when this is the first completed order for the customer.',
    ingested_at DateTime DEFAULT now() COMMENT 'Timestamp when the row was inserted into ClickHouse.'
)
ENGINE = MergeTree
ORDER BY (order_created_at, order_id)
COMMENT 'Mock ecommerce order fact table for validating DataHub metadata lookup and Trino SQL access.';

INSERT INTO poc.customer_orders
    (
        order_id,
        customer_id,
        customer_email,
        order_status,
        order_created_at,
        order_paid_at,
        product_sku,
        product_name,
        quantity,
        unit_price,
        discount_amount,
        currency,
        payment_method,
        shipping_country,
        is_first_order
    )
SELECT *
FROM
(
    SELECT
        'ORD-10001' AS order_id,
        'CUS-9001' AS customer_id,
        'alice.chen@example.com' AS customer_email,
        'delivered' AS order_status,
        toDateTime('2026-07-01 10:15:00') AS order_created_at,
        toNullable(toDateTime('2026-07-01 10:17:31')) AS order_paid_at,
        'SKU-KEYBOARD-001' AS product_sku,
        'Compact Mechanical Keyboard' AS product_name,
        toUInt32(1) AS quantity,
        toDecimal64(129.00, 2) AS unit_price,
        toDecimal64(10.00, 2) AS discount_amount,
        'USD' AS currency,
        'credit_card' AS payment_method,
        'TW' AS shipping_country,
        true AS is_first_order
    UNION ALL
    SELECT
        'ORD-10002',
        'CUS-9002',
        'ben.lin@example.com',
        'paid',
        toDateTime('2026-07-02 14:42:11'),
        toNullable(toDateTime('2026-07-02 14:44:05')),
        'SKU-MOUSE-002',
        'Wireless Productivity Mouse',
        toUInt32(2),
        toDecimal64(49.50, 2),
        toDecimal64(0.00, 2),
        'USD',
        'wallet',
        'TW',
        false
    UNION ALL
    SELECT
        'ORD-10003',
        'CUS-9003',
        'carol.wu@example.com',
        'created',
        toDateTime('2026-07-03 08:03:22'),
        CAST(NULL, 'Nullable(DateTime)'),
        'SKU-MONITOR-003',
        '27 Inch USB-C Monitor',
        toUInt32(1),
        toDecimal64(319.99, 2),
        toDecimal64(25.00, 2),
        'USD',
        'bank_transfer',
        'JP',
        true
)
WHERE NOT EXISTS (SELECT 1 FROM poc.customer_orders);
