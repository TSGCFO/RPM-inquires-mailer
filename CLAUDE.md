# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-database email notification service that listens for PostgreSQL database notifications and sends email alerts via Microsoft Graph API. It supports monitoring multiple databases concurrently with different email configurations, designed as a robust background worker for multi-tenant environments.

### Architecture

- **Multi-instance Python service** (`listener.py`) - Main application supporting concurrent database monitoring
- **Threaded architecture** - Each database/email pair runs in its own thread for isolation and resilience
- **Microsoft Graph integration** - Uses OAuth2 client credentials flow with per-tenant token caching
- **PostgreSQL event listening** - Uses `psycopg` library to listen on `new_record_channel` for multiple databases
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
- **Database**: `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
- **Microsoft Graph**: `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`
- **Email addresses**: `FROM_EMAIL`, `TO_EMAIL`

### Instance 2 (Optional for multi-database support)
- **Database**: `PGHOST_2`, `PGDATABASE_2`, `PGUSER_2`, `PGPASSWORD_2`
- **Microsoft Graph**: `TENANT_ID_2`, `CLIENT_ID_2`, `CLIENT_SECRET_2`
- **Email addresses**: `FROM_EMAIL_2`, `TO_EMAIL_2`

The system automatically detects which instances are configured and starts the appropriate number of listener threads.

## Key Dependencies

- `psycopg[binary]>=3.1` - PostgreSQL adapter with LISTEN/NOTIFY support
- `requests>=2.31` - HTTP client for Microsoft Graph API calls
- `pytest>=7.0` - Test framework (dev dependency)

## Development Best Practices

- Always install dependencies in a virtual environment
- Always update/create tests, and documentation whenever there a changes/updates to the codebase, or when new features are introduced.

## Development Workflow Guidelines

- When creating PRs, commits or issues all messages and comments should start with the following prefix "@claude Review the changes for any Bugs, issues, errors and typos."

## Developer Workflow Notes

- Before committing changes or pushing commits run all tests. Investigate the test results and fix any bugs, errors or issues.