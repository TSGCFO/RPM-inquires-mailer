# RPM Inquiries Mailer

## Description

This project listens for new inquiry records in PostgreSQL databases and sends notification emails via Microsoft Graph. It supports monitoring multiple databases simultaneously with different email configurations, making it perfect for multi-tenant or multi-application deployments.

**✨ New Feature**: Multi-database support allows monitoring up to 2 databases concurrently, each with its own email sender and recipient configuration.

## Features

- 🔄 **Concurrent Database Monitoring**: Monitor multiple PostgreSQL databases simultaneously
- 📧 **Multi-Tenant Email Support**: Different Microsoft Graph users and recipients per database
- 🛡️ **Resilient Architecture**: Individual instance failures don't affect others
- 🔒 **Secure Token Management**: Isolated token caching per Microsoft Graph tenant
- ⚡ **24/7 Background Processing**: Designed for continuous operation on cloud platforms
- 🐳 **Cloud-Ready**: Optimized for Render, Docker, and other cloud deployments

## Quick Start

### Single Database Setup (Original)

1. Set up your environment variables for one database:

    ```bash
    # Database
    PGHOST=your-db-host
    PGDATABASE=your-database
    PGUSER=your-username
    PGPASSWORD=your-password

    # Microsoft Graph
    TENANT_ID=your-tenant-id
    CLIENT_ID=your-client-id
    CLIENT_SECRET=your-client-secret
    FROM_EMAIL=sender@yourdomain.com
    TO_EMAIL=recipient@yourdomain.com
    ```

2. Install and run:

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python listener.py
    ```

### Multi-Database Setup (New)

Add additional environment variables for the second database:

```bash
# Second Database
PGHOST_2=your-second-db-host
PGDATABASE_2=your-second-database
PGUSER_2=your-second-username
PGPASSWORD_2=your-second-password

# Second Microsoft Graph User
TENANT_ID_2=your-second-tenant-id
CLIENT_ID_2=your-second-client-id
CLIENT_SECRET_2=your-second-client-secret
FROM_EMAIL_2=sender2@yourdomain.com
TO_EMAIL_2=recipient2@yourdomain.com
```

The system automatically detects and starts listeners for all configured instances.

## Environment Variables

### 🔑 Database Connection Options

You can configure database connections using either:

1. **Connection Strings (Recommended)**: `DATABASE_URL` and `DATABASE_URL_2`
2. **Individual Variables**: `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` (and `_2` variants)

### Required for Instance 1

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string (preferred) | `postgresql://user:pass@host:5432/dbname?sslmode=require` |
| `PGHOST` | PostgreSQL host (if not using DATABASE_URL) | `localhost` |
| `PGDATABASE` | Database name (if not using DATABASE_URL) | `production_db` |
| `PGUSER` | Database username (if not using DATABASE_URL) | `app_user` |
| `PGPASSWORD` | Database password (if not using DATABASE_URL) | `secure_password` |
| `TENANT_ID` | Microsoft Graph tenant ID | `12345678-1234-1234-1234-123456789012` |
| `CLIENT_ID` | Microsoft Graph client ID | `87654321-4321-4321-4321-210987654321` |
| `CLIENT_SECRET` | Microsoft Graph client secret | `your-client-secret` |
| `FROM_EMAIL` | Email sender address | `notifications@company.com` |
| `TO_EMAIL` | Email recipient address | `alerts@company.com` |

### Optional for Instance 2

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL_2` | PostgreSQL connection string for second database | `postgresql://user:pass@host:5432/dbname2?sslmode=require` |
| `PGHOST_2` | PostgreSQL host (if not using DATABASE_URL_2) | `localhost` |
| `PGDATABASE_2` | Database name (if not using DATABASE_URL_2) | `secondary_db` |
| `PGUSER_2` | Database username (if not using DATABASE_URL_2) | `app_user` |
| `PGPASSWORD_2` | Database password (if not using DATABASE_URL_2) | `secure_password` |
| `TENANT_ID_2` | Microsoft Graph tenant ID for second instance | `87654321-4321-4321-4321-210987654321` |
| `CLIENT_ID_2` | Microsoft Graph client ID for second instance | `12345678-1234-1234-1234-123456789012` |
| `CLIENT_SECRET_2` | Microsoft Graph client secret for second instance | `your-second-client-secret` |
| `FROM_EMAIL_2` | Email sender address for second instance | `notifications2@company.com` |
| `TO_EMAIL_2` | Email recipient address for second instance | `alerts2@company.com` |

## Deployment

### Render.com (Recommended)

1. Fork this repository
2. Create a new Worker service on Render
3. Set environment variables in the Render dashboard
4. Deploy using the included `render.yaml` blueprint

### Docker

```bash
docker build -t rpm-inquiries-mailer .
docker run -d --env-file .env rpm-inquiries-mailer
```

### Manual Deployment

```bash
# Clone and setup
git clone https://github.com/TSGCFO/RPM-inquires-mailer.git
cd RPM-inquires-mailer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export PGHOST=your-host
# ... other variables

# Run
python listener.py
```

## Database Setup

Each monitored database needs triggers to send notifications. **IMPORTANT**: Each instance uses a unique notification channel to prevent cross-database interference.

### Instance 1 Database Setup (inquiries table)

```sql
-- Create notification function for inquiries (Instance 1)
CREATE OR REPLACE FUNCTION notify_new_inquiry()
RETURNS TRIGGER AS $$
BEGIN
    -- Use unique channel: new_record_channel
    PERFORM pg_notify('new_record_channel', json_build_object('id', NEW.id)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on inquiries table
CREATE TRIGGER inquiry_notification_trigger
    AFTER INSERT ON inquiries
    FOR EACH ROW
    EXECUTE FUNCTION notify_new_inquiry();
```

### Instance 2 Database Setup (quote_requests table)

```sql
-- Create notification function for quote requests (Instance 2)
CREATE OR REPLACE FUNCTION notify_new_quote_request()
RETURNS TRIGGER AS $$
BEGIN
    -- Use unique channel: quote_request_channel
    PERFORM pg_notify('quote_request_channel', json_build_object('id', NEW.id)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on quote_requests table
CREATE TRIGGER quote_request_notification_trigger
    AFTER INSERT ON quote_requests
    FOR EACH ROW
    EXECUTE FUNCTION notify_new_quote_request();
```

### 🔧 Thread Safety Notes

- Each instance creates database connections **within worker threads** for reliability
- Separate connections are used for LISTEN operations and data fetching
- This prevents PostgreSQL connection interference in multi-threaded environments

## Microsoft Graph Setup

1. Register an application in Azure Portal for each tenant
2. Grant `Mail.Send` application permissions
3. Generate client secrets
4. Ensure sender email accounts exist in respective tenants

## Testing

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/test_listener.py -v
```

## Monitoring

The application provides detailed logging for each instance:

```console
✅ Loaded configuration for Instance-2
✅ Loaded configuration for Instance-1
🚀 Starting 2 database listener(s) with supervision...
🧵 Started supervised thread for Instance-1
🧵 Started supervised thread for Instance-2
🔧 [Instance-1] Creating database connection in worker thread...
🔗 [Instance-1] Connected via connection string to database: rpm_auto
🔔 [Instance-1] Listening on channel new_record_channel...
🔧 [Instance-2] Creating database connection in worker thread...
🔗 [Instance-2] Connected via connection string to database: tsg_fulfillment
🔔 [Instance-2] Listening on channel quote_request_channel...
📥 [Instance-2] Received notification on quote_request_channel: {"id" : 42}
📋 [Instance-2] Fetching full record for ID: 42
📨 [Instance-2] Email sent successfully to notifications@tsgfulfillment.com for record id: 42
```

### 🚨 Troubleshooting Common Issues

**Issue**: Notifications received but emails not sent

- **Cause**: Database connection thread safety
- **Solution**: Ensure connections are created within worker threads (already implemented)

**Issue**: Cross-database notification interference  

- **Cause**: Multiple instances using same notification channel
- **Solution**: Use unique channels (`new_record_channel` vs `quote_request_channel`)

**Issue**: Connection errors in threaded environment

- **Cause**: Shared connections between LISTEN and data operations  
- **Solution**: Use separate connections for notifications and data fetching (already implemented)

## Documentation

- **[Multi-Database Setup Guide](MULTI_DATABASE_SETUP.md)** - Comprehensive setup instructions
- **[CLAUDE.md](CLAUDE.md)** - Development and architecture notes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the terms of the [MIT](LICENSE) license.
