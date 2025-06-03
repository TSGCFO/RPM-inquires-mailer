# inquires-mail-notification

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

## Usage
Set the required environment variables and start the listener:

```bash
python listener.py
```

The script waits for notifications on the `new_record_channel` channel and
emails the inquiry details when a notification is received.

## License
This project is licensed under the terms of the [MIT](LICENSE) license.
