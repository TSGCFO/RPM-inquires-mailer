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

### Required for Instance 1
| Variable | Description | Example |
|----------|-------------|---------|
| `PGHOST` | PostgreSQL host | `localhost` |
| `PGDATABASE` | Database name | `production_db` |
| `PGUSER` | Database username | `app_user` |
| `PGPASSWORD` | Database password | `secure_password` |
| `TENANT_ID` | Microsoft Graph tenant ID | `12345678-1234-1234-1234-123456789012` |
| `CLIENT_ID` | Microsoft Graph client ID | `87654321-4321-4321-4321-210987654321` |
| `CLIENT_SECRET` | Microsoft Graph client secret | `your-client-secret` |
| `FROM_EMAIL` | Email sender address | `notifications@company.com` |
| `TO_EMAIL` | Email recipient address | `alerts@company.com` |

### Optional for Instance 2
Add `_2` suffix to all variable names above for the second instance.

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
Each monitored database needs a trigger to send notifications:

```sql
-- Create notification function
CREATE OR REPLACE FUNCTION notify_new_inquiry()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('new_record_channel', row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on your inquiries table
CREATE TRIGGER inquiry_notification_trigger
    AFTER INSERT ON inquiries
    FOR EACH ROW
    EXECUTE FUNCTION notify_new_inquiry();
```

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
```
✅ Loaded configuration for Instance-1
✅ Loaded configuration for Instance-2
🚀 Starting 2 database listener(s)...
🔔 [Instance-1] Listening on channel new_record_channel...
🔔 [Instance-2] Listening on channel new_record_channel...
📨 [Instance-1] Email sent to recipient1@domain.com for inquiry id: 123
```

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
