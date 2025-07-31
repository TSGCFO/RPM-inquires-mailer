# Multi-Database Setup Guide

This document explains how to configure and deploy the RPM Inquiries Mailer to monitor multiple databases and send emails from different user accounts.

## Overview

The RPM Inquiries Mailer now supports monitoring multiple PostgreSQL databases simultaneously, with each database configured to send emails from different Microsoft Graph user accounts. This allows you to:

- Monitor Database 1 → Send emails from User 1 to Recipient 1
- Monitor Database 2 → Send emails from User 2 to Recipient 2
- Monitor additional databases in the future with similar configurations
- Run all instances concurrently in a single deployment

## Architecture

The system uses a threaded architecture where each database/email configuration runs in its own thread:

```txt
Main Process
├── Thread 1: Database 1 Listener
│   ├── PostgreSQL Connection (DB1)
│   ├── Microsoft Graph Token (Tenant 1)
│   └── Email Sender (User 1 → Recipient 1)
└── Thread 2: Database 2 Listener
│   ├── PostgreSQL Connection (DB2)
│   ├── Microsoft Graph Token (Tenant 2)
│   └── Email Sender (User 2 → Recipient 2)
│── Thread 3: Database 3 Listener
│   ├── PostgreSQL Connection (DB3)
│   ├── Microsoft Graph Token (Tenant 3)
│   └── Email Sender (User 3 → Recipient 3)
|__ Thread N: Database N Listener
    ├── PostgreSQL Connection (DBN)
    ├── Microsoft Graph Token (Tenant N)
    └── Email Sender (User N → Recipient N)
```

## Environment Variables

### Required for Instance 1 (Backward Compatible)

```bash
# Database Connection
PGHOST=your-db-host
PGDATABASE=your-database-name
PGUSER=your-db-username
PGPASSWORD=your-db-password

# Microsoft Graph API
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret

# Email Configuration
FROM_EMAIL=sender@yourdomain.com
TO_EMAIL=recipient@yourdomain.com
```

### Optional for Instance 2

```bash
# Database Connection
PGHOST_2=your-second-db-host
PGDATABASE_2=your-second-database-name
PGUSER_2=your-second-db-username
PGPASSWORD_2=your-second-db-password

# Microsoft Graph API
TENANT_ID_2=your-second-tenant-id
CLIENT_ID_2=your-second-client-id
CLIENT_SECRET_2=your-second-client-secret

# Email Configuration
FROM_EMAIL_2=sender2@yourdomain.com
TO_EMAIL_2=recipient2@yourdomain.com
```

## Deployment Options

### Single Database (Current Setup)

Configure only the Instance 1 environment variables. The system will run with one database listener.

### Dual Database Setup

Configure both Instance 1 and Instance 2 environment variables. The system will automatically detect and start both listeners.

## Render.com Deployment

### Environment Variables in Render Dashboard

1. Navigate to your Render service dashboard
2. Go to Environment tab
3. Add all required environment variables for your configuration:

**For Single Database:**

- Add all Instance 1 variables listed above

**For Dual Database:**

- Add all Instance 1 variables
- Add all Instance 2 variables (with `_2` suffix)

### Service Configuration

The service will automatically:

- Detect available configurations
- Start appropriate number of listener threads
- Log startup information for each instance
- Handle individual instance failures gracefully

## Database Requirements

Each database must have:

1. A table that triggers notifications (usually an `inquiries` table)
2. A PostgreSQL trigger that sends NOTIFY signals
3. Proper network access for the worker service

### Example Trigger Setup

```sql
-- Create notification function
CREATE OR REPLACE FUNCTION notify_new_inquiry()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('new_record_channel', row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
CREATE TRIGGER inquiry_notification_trigger
    AFTER INSERT ON inquiries
    FOR EACH ROW
    EXECUTE FUNCTION notify_new_inquiry();
```

## Microsoft Graph Setup

Each instance requires its own Microsoft Graph application registration:

1. **Azure Portal Setup:**
   - Register separate applications for each tenant/user
   - Grant `Mail.Send` permissions
   - Generate client secrets

2. **Email Account Requirements:**
   - Each `FROM_EMAIL` must be a valid user in the respective tenant
   - The application must have permission to send emails on behalf of the user

## Monitoring and Logs

The system provides detailed logging with instance identification:

```console
✅ Loaded configuration for Instance-1
✅ Loaded configuration for Instance-2
🚀 Starting 2 database listener(s)...
🧵 Started thread for Instance-1
🧵 Started thread for Instance-2
🔗 [Instance-1] Connected to database: main_db
🔗 [Instance-2] Connected to database: secondary_db
🔔 [Instance-1] Listening on channel new_record_channel...
🔔 [Instance-2] Listening on channel new_record_channel...
📨 [Instance-1] Email sent to recipient1@domain.com for inquiry id: 123
📨 [Instance-2] Email sent to recipient2@domain.com for inquiry id: 456
```

## Troubleshooting

### Instance 2 Not Starting

- Check all `*_2` environment variables are set
- Verify database connectivity for the second instance
- Review logs for specific error messages

### Email Sending Failures

- Verify Microsoft Graph permissions
- Check client credentials are correct
- Ensure `FROM_EMAIL` user exists in the tenant

### Database Connection Issues

- Test database connectivity separately
- Verify firewall rules allow connections
- Check PostgreSQL user permissions

### Token Caching

- Each tenant maintains its own token cache
- Tokens are automatically refreshed
- No manual token management required

## Performance Considerations

- Each database connection runs in its own thread
- Microsoft Graph tokens are cached per tenant
- System handles network interruptions gracefully
- Individual instance failures don't affect others

## Security Notes

- Store all credentials as environment variables
- Use least-privilege database accounts
- Rotate client secrets regularly
- Monitor email sending for abuse

## Migration from Single to Dual Database

1. Deploy current configuration (Instance 1 only)
2. Add Instance 2 environment variables
3. Redeploy service
4. Verify both instances start successfully
5. Test notifications from both databases
