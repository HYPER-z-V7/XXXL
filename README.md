# RAIX — Guild Glory Dashboard & Bot Engine

RAIX is the rebranded version of the supplied project. Existing source modules, dashboard pages, API routes, account data, protocol files, and deployment configuration are retained.

## Run locally

```bash
python -m pip install -r requirements.txt
python app.py
```

The web interface is served by the application on the configured `WEB_HOST` / `WEB_PORT` values in `main.py`.

## Default panel login

- Username: `RAIX`
- Password: `RAIX123`

Change the password after first login. The seeded account is stored in `panel_db.json`; the application hashes the password before saving it.

## Deployment

Use Python 3.10+ and install dependencies from `requirements.txt`. Configure hosting environment variables and keep `accounts.json` private: it contains account credential data. Do not commit real credentials to a public repository.

## Project structure

- `main.py` — application server, API routes, and bot engine
- `dashboard_server.py` — dashboard state and API helpers
- `templates/` — dashboard interface and retained template backups
- `static/logo.gif` — RAIX-branded animated logo
- `accounts.json` — saved account credentials (preserved as supplied)
- `panel_db.json` — panel users, sessions, settings, and stored data
- `*_pb2.py`, `message_ids.py` — protocol support modules

## Important

RAIX is an independent project and is not affiliated with Garena, Free Fire, or Sea Ltd. Game names and trademarks belong to their respective owners. Use the software only in ways permitted by the applicable game terms and laws.
