CREATE TABLE IF NOT EXISTS minio.poc2.customer_segments AS
SELECT *
FROM (
    VALUES
        ('CUS-9001', 'high_value', 92, DATE '2026-07-10'),
        ('CUS-9002', 'growth', 71, DATE '2026-07-10'),
        ('CUS-9003', 'new', 45, DATE '2026-07-10')
) AS segments (
    customer_id,
    segment_name,
    segment_score,
    calculated_date
);
