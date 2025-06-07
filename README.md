# inquiries-mail-notification

## Description
This project listens for new inquiry records in a PostgreSQL database and
sends notification emails via Microsoft Graph. It is designed as a small
background worker to be run alongside your application.

## Installation
Create a Python virtual environment and install the dependencies from
`requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment
Set the following environment variables before running the listener:

- `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
- `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`
- `FROM_EMAIL`, `TO_EMAIL`
- `PGHOST_2`, `PGDATABASE_2`, `PGUSER_2`, `PGPASSWORD_2`
- `FROM_EMAIL_2`, `TO_EMAIL_2`

The variables ending with `_2` configure the second database connection
and mail sender.

## Usage
Set the required environment variables and start the listener:

```bash
python listener.py
```

The script waits for notifications on the `new_record_channel` channel and
emails the inquiry details when a notification is received. It now runs two
threads, each connected to its own database and sending mail from its
corresponding user. The expected channel name, `new_record_channel`, remains
the same for both databases.

## License
This project is licensed under the terms of the [MIT](LICENSE) license.
