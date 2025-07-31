# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-database email notification service that listens for PostgreSQL database notifications and sends email alerts via Microsoft Graph API. It supports monitoring multiple databases concurrently with different email configurations, designed as a robust background worker for multi-tenant environments.

### Architecture

- **Multi-instance Python service** (`listener.py`) - Main application supporting concurrent database monitoring
- **Threaded architecture** - Each database/email pair runs in its own thread for isolation and resilience
- **Microsoft Graph integration** - Uses OAuth2 client credentials flow with per-tenant token caching
- **PostgreSQL event listening** - Uses `psycopg` library with unique channels per instance (`new_record_channel` for Instance 1, `quote_request_channel` for Instance 2)
- **Configurable email formatting** - Converts inquiry records to plain-text emails with instance-specific routing

### Core Components

#### Configuration Management
- `InstanceConfig` - Dataclass encapsulating database and email settings for one instance
- `load_instance_configs()` - Loads and validates environment variables for all configured instances

#### Database and Email Handling
- `DatabaseListener` - Class managing database connection, listening, and email sending per instance
- `graph_token(config)` - Handles Microsoft Graph OAuth token acquisition with per-tenant caching
- `DatabaseListener.send_email(record)` - Formats inquiry data and sends via Microsoft Graph API per instance
- `DatabaseListener.listen_and_process()` - PostgreSQL LISTEN loop with error recovery

#### Multi-Instance Coordination
- `main()` - Loads configurations and starts concurrent listener threads
- Threading with daemon threads for clean shutdown
- Per-instance error handling and reconnection logic

## Development Commands

### Setup Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for testing
```

### Running the Service
```bash
python listener.py
```

### Testing
```bash
pytest
pytest tests/test_listener.py  # specific test file
```

## Required Environment Variables

### Instance 1 (Required for backward compatibility)
- **Database**: `DATABASE_URL` (preferred) OR `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
- **Microsoft Graph**: `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`
- **Email addresses**: `FROM_EMAIL`, `TO_EMAIL`
- **Notification Channel**: `new_record_channel` (for inquiries table)

### Instance 2 (Optional for multi-database support)
- **Database**: `DATABASE_URL_2` (preferred) OR `PGHOST_2`, `PGDATABASE_2`, `PGUSER_2`, `PGPASSWORD_2`
- **Microsoft Graph**: `TENANT_ID_2`, `CLIENT_ID_2`, `CLIENT_SECRET_2`
- **Email addresses**: `FROM_EMAIL_2`, `TO_EMAIL_2`
- **Notification Channel**: `quote_request_channel` (for quote_requests table)

The system automatically detects which instances are configured and starts the appropriate number of listener threads.

## Key Dependencies

- `psycopg[binary]>=3.1` - PostgreSQL adapter with LISTEN/NOTIFY support
- `requests>=2.31` - HTTP client for Microsoft Graph API calls
- `python-dotenv>=1.0` - Environment variable loading from .env files
- `pytest>=7.0` - Test framework (dev dependency)

## Development Best Practices

- Always install dependencies in a virtual environment
- Always update/create tests, and documentation whenever there a changes/updates to the codebase, or when new features are introduced.

## Critical Architecture Notes

### Thread Safety Requirements
- **Database connections MUST be created within worker threads** - PostgreSQL LISTEN/NOTIFY doesn't work reliably when connections are created in main thread and used in worker threads
- **Separate connections for different operations** - Use dedicated connections for LISTEN operations and separate connections for data fetching to prevent interference
- **Unique notification channels** - Each instance must use different channel names to prevent cross-database notification interference

### Notification Channel Architecture
- **Instance 1**: Uses `new_record_channel` for `inquiries` table notifications
- **Instance 2**: Uses `quote_request_channel` for `quote_requests` table notifications
- **Channel isolation**: Prevents notifications from one database affecting another database's listener

### Known Issues & Solutions
- **Silent email failures in threads**: Fixed by creating connections within worker threads
- **Cross-database interference**: Fixed by using unique notification channels per instance
- **Connection blocking**: Fixed by using separate connections for LISTEN vs data operations

## Development Workflow Guidelines

- When creating PRs, commits or issues all messages and comments should start with the following prefix "@claude Review the changes for any Bugs, issues, errors and typos."

## Developer Workflow Notes

- Before committing changes or pushing commits run all tests. Investigate the test results and fix any bugs, errors or issues.
- **Thread safety testing**: Always test multi-instance functionality in threaded environment
- **Connection string support**: Prefer `DATABASE_URL` format over individual database variables

## Deployment Configuration

### Render.com Deployment
- Uses `render.yaml` blueprint with worker service configuration
- Supports both `DATABASE_URL` connection strings (preferred) and individual database variables
- Region: Ohio, Plan: Starter
- Build command: `pip install -r requirements.txt python-dotenv`
- Start command: `python listener.py`

### Environment Setup Commands
```bash
# Windows activation (current platform)
python3 -m venv .venv
.venv\Scripts\activate

# Linux/Mac activation  
source .venv/bin/activate
```

## Debug and Testing Utilities

### Debug Scripts
- `debug_instance_2.py` - Debugging tool for second instance
- `debug_quote_requests.py` - Quote request debugging utility

### SQL Test Files
- `test_instance_1_inquiry.sql` - Test inquiry insertion for Instance 1
- `test_instance_2_quote.sql` - Test quote request insertion for Instance 2
- `instance_2_pg_table.sql` - Table creation for Instance 2

### Testing Documentation
- `testing_guide.md` - Comprehensive real-life testing procedures
- Test with: `pytest tests/test_listener.py -v` for verbose output

## File Structure Context
```
├── listener.py              # Main application
├── tests/test_listener.py    # Unit tests with mocking utilities
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies (pytest)
├── render.yaml             # Cloud deployment configuration
├── testing_guide.md        # Manual testing procedures
└── debug_*.py              # Debugging utilities
```

## Important Instruction Reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

## Workflow Best Practices
- Always run SQL commands instead of asking the user to run them.