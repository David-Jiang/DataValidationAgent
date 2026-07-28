CREATE TABLE IF NOT EXISTS minio.poc3.customer_engagement_scores AS
SELECT *
FROM (
    VALUES
        ('CUS-9001', 88.5, 14, TIMESTAMP '2026-07-10 18:00:00'),
        ('CUS-9002', 67.0, 8, TIMESTAMP '2026-07-10 18:00:00'),
        ('CUS-9003', 51.5, 5, TIMESTAMP '2026-07-10 18:00:00')
) AS engagement (
    customer_id,
    engagement_score,
    active_days_30d,
    calculated_at
);
