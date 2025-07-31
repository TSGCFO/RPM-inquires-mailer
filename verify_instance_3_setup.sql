-- Verification script for Instance 3 (neondb) trigger and function setup
-- Run this to verify that the contact_submissions table, function, and trigger are correctly configured

\echo '=== Instance 3 (neondb) Setup Verification ==='
\echo ''

-- 1. Check if contact_submissions table exists
\echo '1. Checking contact_submissions table structure:'
\d contact_submissions

\echo ''
\echo '2. Checking if notify_new_contact_submission function exists:'
-- Check if the function exists
SELECT 
    p.proname as function_name,
    pg_get_function_result(p.oid) as return_type,
    pg_get_function_arguments(p.oid) as arguments,
    l.lanname as language
FROM pg_proc p
LEFT JOIN pg_language l ON p.prolang = l.oid
WHERE p.proname = 'notify_new_contact_submission';

\echo ''
\echo '3. Checking if contact_submission_notification_trigger exists:'
-- Check if the trigger exists
SELECT 
    t.tgname as trigger_name,
    c.relname as table_name,
    p.proname as function_name,
    CASE t.tgtype & 66
        WHEN 2 THEN 'BEFORE'
        WHEN 64 THEN 'INSTEAD OF'
        ELSE 'AFTER'
    END as trigger_timing,
    CASE t.tgtype & 28
        WHEN 4 THEN 'INSERT'
        WHEN 8 THEN 'DELETE'
        WHEN 16 THEN 'UPDATE'
        WHEN 12 THEN 'INSERT OR DELETE'
        WHEN 20 THEN 'INSERT OR UPDATE'
        WHEN 24 THEN 'DELETE OR UPDATE'
        WHEN 28 THEN 'INSERT OR DELETE OR UPDATE'
    END as trigger_events
FROM pg_trigger t
JOIN pg_class c ON t.tgrelid = c.oid
JOIN pg_proc p ON t.tgfoid = p.oid
WHERE t.tgname = 'contact_submission_notification_trigger'
  AND c.relname = 'contact_submissions';

\echo ''
\echo '4. Testing notification channel (listen for 5 seconds):'
-- Test the notification by inserting a test record
-- First, start listening
LISTEN contact_submission_channel;

-- Insert a test record
INSERT INTO contact_submissions (
    first_name,
    last_name,
    email,
    phone,
    inquiry_type,
    message
) VALUES (
    'Test',
    'User',
    'test@verification.com',
    '555-TEST',
    'Verification Test',
    'This is a test record to verify the trigger is working correctly.'
);

\echo ''
\echo '5. Check if test record was inserted:'
SELECT 
    id,
    first_name,
    last_name,
    email,
    inquiry_type,
    created_at
FROM contact_submissions 
WHERE email = 'test@verification.com' 
ORDER BY created_at DESC 
LIMIT 1;

\echo ''
\echo '6. Clean up test record:'
DELETE FROM contact_submissions WHERE email = 'test@verification.com';

\echo ''
\echo '=== Verification Complete ==='
\echo 'If you see:'
\echo '- Table structure with all required columns'
\echo '- Function notify_new_contact_submission with TRIGGER return type'
\echo '- Trigger contact_submission_notification_trigger on AFTER INSERT'
\echo '- Test record was inserted and deleted successfully'
\echo 'Then your Instance 3 setup is correct!'

-- Stop listening
UNLISTEN contact_submission_channel;