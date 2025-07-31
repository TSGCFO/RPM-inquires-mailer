-- Create contact_submissions table and trigger for Instance 3 (neondb)
-- This sets up the database schema and notification system for the third instance

-- Create the contact_submissions table (if not exists)
CREATE TABLE IF NOT EXISTS contact_submissions (
    id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    inquiry_type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create notification function for contact submissions (Instance 3)
CREATE OR REPLACE FUNCTION notify_new_contact_submission()
RETURNS TRIGGER AS $$
BEGIN
    -- Use unique channel: contact_submission_channel
    PERFORM pg_notify('contact_submission_channel', json_build_object('id', NEW.id)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on contact_submissions table
DROP TRIGGER IF EXISTS contact_submission_notification_trigger ON contact_submissions;
CREATE TRIGGER contact_submission_notification_trigger
    AFTER INSERT ON contact_submissions
    FOR EACH ROW
    EXECUTE FUNCTION notify_new_contact_submission();

-- Verify the setup
SELECT 'contact_submissions table and trigger created successfully' AS status;