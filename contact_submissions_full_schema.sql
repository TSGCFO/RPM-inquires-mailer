-- Table structure
\d+ contact_submissions

-- Column details
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default,
    character_maximum_length,
    numeric_precision,
    numeric_scale
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name = 'contact_submissions'
ORDER BY ordinal_position;

-- Constraints
SELECT conname, contype, pg_get_constraintdef(oid) as definition
FROM pg_constraint 
WHERE conrelid = 'public.contact_submissions'::regclass;

-- Indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'contact_submissions'
AND schemaname = 'public';

-- Triggers
SELECT trigger_name, event_manipulation, action_statement
FROM information_schema.triggers
WHERE event_object_table = 'contact_submissions'
AND event_object_schema = 'public';
