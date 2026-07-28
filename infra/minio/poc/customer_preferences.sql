CREATE TABLE IF NOT EXISTS minio.poc.customer_preferences AS
SELECT *
FROM (
    VALUES
        ('CUS-9001', 'email', 'zh-TW', true, TIMESTAMP '2026-07-08 09:15:00'),
        ('CUS-9002', 'sms', 'zh-TW', false, TIMESTAMP '2026-07-07 16:30:00'),
        ('CUS-9003', 'email', 'ja-JP', true, TIMESTAMP '2026-07-06 11:45:00')
) AS preferences (
    customer_id,
    preferred_contact_channel,
    preferred_language,
    personalization_enabled,
    preference_updated_at
)
