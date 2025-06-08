-- Test Script for Instance 2 (TSG Fulfillment - Quote Requests)
-- This will trigger an email from notifications@tsgfulfillment.com to noreply@tsgfulfillment.com

-- Insert a test quote request into the quote_requests table
INSERT INTO quote_requests (
    name,
    email,
    phone, 
    company,
    service,
    message,
    consent,
    current_shipments,
    expected_shipments,
    services,
    status
) VALUES (
    'Sarah Business Owner',
    'sarah.owner@testcompany.com',
    '+1-555-987-6543',
    'Test Logistics Inc',
    'Freight Shipping',
    'We are looking for a reliable freight shipping partner for our expanding business. We need regular shipments from Toronto to Vancouver. Could you provide a quote for weekly LTL shipments?',
    true,
    '5-10 per month',
    '15-20 per month',
    'LTL Freight, Warehousing, Distribution',
    'new'
);

-- The trigger will automatically:
-- 1. Fire notify_new_quote_request() function  
-- 2. Send pg_notify('new_record_channel', json_build_object('id', NEW.id)::text)
-- 3. Listener will receive notification
-- 4. Fetch full record from quote_requests table
-- 5. Send quote request email via Microsoft Graph