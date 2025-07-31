-- Test contact submission insertion for Instance 3 (neondb)
-- This will trigger the contact_submission_channel notification

INSERT INTO contact_submissions (
    first_name,
    last_name,
    email,
    phone,
    inquiry_type,
    message,
    created_at
) VALUES (
    'John',
    'Doe',
    'john.doe@example.com',
    '+1-555-123-4567',
    'Business Inquiry',
    'I am interested in learning more about your services and would like to schedule a consultation to discuss potential partnership opportunities.',
    NOW()
);

-- Note: This should trigger a notification on 'contact_submission_channel'
-- Expected email: FROM no-reply@talencor.com TO info@talencor.com