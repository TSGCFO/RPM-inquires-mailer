# Real-Life Email Testing Guide

## Prerequisites
1. Ensure both databases are accessible
2. Verify Microsoft Graph permissions are granted
3. Check that email accounts exist and have send permissions

## Step 1: Start the Listener

```bash
# Load environment variables and start the listener
source .env && python listener.py
```

Expected output:
```
✅ Loaded configuration for Instance-1
✅ Loaded configuration for Instance-2
🚀 Starting 2 database listener(s) with supervision...
🧵 Started supervised thread for Instance-1
🧵 Started supervised thread for Instance-2
🔗 [Instance-1] Connected to database: rpm_auto
🔗 [Instance-2] Connected to database: tsg_fulfillment
🔔 [Instance-1] Listening on channel new_record_channel...
🔔 [Instance-2] Listening on channel new_record_channel...
```

## Step 2: Test Instance 1 (RPM Auto - Car Inquiries)

In a separate terminal, connect to the rpm_auto database and run:

```bash
# Connect to Instance 1 database
psql -h dpg-d0dtgaidbo4c739abnv0-a -d rpm_auto -U rpm_auto_user

# Run the test inquiry
\i test_instance_1_inquiry.sql
```

Expected listener output:
```
📨 [Instance-1] Email sent to info@rpmautosales.ca for inquiry id: 123
```

## Step 3: Test Instance 2 (TSG Fulfillment - Quote Requests)

In another terminal, connect to the tsg_fulfillment database:

```bash
# Connect to Instance 2 database  
psql -h dpg-d0dtgaidbo4c739abnv0-a -d tsg_fulfillment -U rpm_auto_user

# Run the test quote request
\i test_instance_2_quote.sql
```

Expected listener output:
```
📨 [Instance-2] Email sent to noreply@tsgfulfillment.com for inquiry id: 456
```

## Step 4: Verify Email Delivery

### Instance 1 Email (RPM Auto):
- **From**: fateh@rpmautosales.ca
- **To**: info@rpmautosales.ca  
- **Subject**: 🆕 New Inquiry Received
- **Content**: Customer inquiry about 2023 Honda Civic

### Instance 2 Email (TSG Fulfillment):
- **From**: notifications@tsgfulfillment.com
- **To**: noreply@tsgfulfillment.com
- **Subject**: 🆕 New Quote Request Received  
- **Content**: Quote request for freight shipping services

## Step 5: Test Error Scenarios

### Test Database Disconnection:
1. Temporarily block database access
2. Verify listener attempts reconnection
3. Check thread supervision restarts failed listeners

### Test Invalid Email:
1. Temporarily revoke Graph permissions
2. Verify error logging and token refresh attempts

## Troubleshooting

### No Email Received:
1. Check listener console for error messages
2. Verify Microsoft Graph token acquisition
3. Test database trigger functionality
4. Check email account permissions

### Database Connection Issues:
1. Verify connection string and credentials
2. Check database firewall rules
3. Test manual psql connection

### Thread Failures:
1. Check supervision loop is detecting failures
2. Verify automatic thread restart messages
3. Monitor for repeated failures

## Success Criteria

✅ Both instances start successfully  
✅ Database connections established  
✅ Notifications received and processed  
✅ Emails delivered to correct recipients  
✅ Different email templates used appropriately  
✅ Thread supervision working (if errors occur)  
✅ Proper error logging and recovery