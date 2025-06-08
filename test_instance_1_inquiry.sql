-- Test Script for Instance 1 (RPM Auto - Inquiries)
-- This will trigger an email from fateh@rpmautosales.ca to info@rpmautosales.ca

-- Insert a test inquiry into the inquiries table
INSERT INTO inquiries (
    name,
    email, 
    phone,
    subject,
    message,
    status
) VALUES (
    'John Test Customer',
    'john.test@example.com',
    '1-555-123-4567',
    'Interested in 2023 Honda Civic',
    'Hi, I am interested in learning more about the 2023 Honda Civic you have listed. Could you please provide more details about the vehicle condition, mileage, and availability for a test drive? Thank you!',
    'new'
);

-- The trigger will automatically:
-- 1. Fire notify_new_inquiry() function
-- 2. Send pg_notify('new_record_channel', json_build_object('id', NEW.id)::text)
-- 3. Listener will receive notification
-- 4. Fetch full record using the ID
-- 5. Send email via Microsoft Graph