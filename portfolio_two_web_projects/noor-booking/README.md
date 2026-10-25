# NOOR Studio — Appointment Booking Website

A standalone bilingual Arabic/English Flask booking application for a fictional grooming studio. This is a portfolio/demo project: all studio details, prices, staff names and seeded appointments are sample data.

## Main features

- Modern, responsive, RTL/LTR landing page with service menu, team, hours, visit details, and FAQ.
- Availability API that calculates times from the selected service duration, working hours (09:00–19:00), Sunday closure, staff preference, active bookings, and a 45-day booking horizon.
- Validated appointment form with CSRF protection, optional email/notes, consent, and honeypot field.
- New requests start as `pending`, not auto-confirmed. Each booking has a high-entropy private reference link to review status and cancel more than 24 hours before the appointment.
- Protected admin panel to confirm, cancel, or complete bookings.
- SQLite for local development and PostgreSQL support for hosting.
- Clearly marked demo records, optional SMTP admin notifications, security headers, health endpoint, deployment configuration, and tests.

## Run on Windows

1. Extract the ZIP into a normal folder.
2. Open that folder in VS Code.
3. Run `run_windows.bat`, or use the following in the VS Code terminal:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

Set your own `SECRET_KEY` and `ADMIN_PASSWORD` in `.env`. The local fallback password is a placeholder and must never be reused online.

## Admin and sample records

- Admin login: `/admin/login`
- Admin dashboard: `/admin`
- Login password comes from `ADMIN_PASSWORD`.
- There is no public registration page.
- Sample bookings are tagged `DEMO`. Set `SEED_DEMO_DATA=false` to stop seeding fictional appointments.

## Deployment

The included `render.yaml` creates a Render web service and asks for `ADMIN_PASSWORD` and `DATABASE_URL`. Provide a durable PostgreSQL connection string for production; the application normalizes `postgres://` and `postgresql://` URLs to use the `psycopg` driver. Render generates `SECRET_KEY`. The service intentionally fails to start on Render if the password or database URL is missing; this prevents bookings being saved to an ephemeral local SQLite file by accident.

**Free-hosting warning:** Render free web services have an ephemeral filesystem and free PostgreSQL databases currently expire after 30 days. This can be used for a temporary portfolio preview, not as permanent booking storage. Before a real launch, attach durable database storage with an appropriate backup plan, set `SEED_DEMO_DATA=false`, replace studio identity/prices/team/hours/contact details, configure SMTP notifications, and confirm applicable privacy and cancellation requirements. See https://render.com/docs/free and https://render.com/docs/postgresql.

## Environment variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Unique long random Flask session/CSRF secret. |
| `ADMIN_PASSWORD` | Admin login password. |
| `DATABASE_URL` | PostgreSQL connection string; omitted locally to use SQLite. |
| `DATABASE_PATH` | Optional local SQLite location. |
| `SEED_DEMO_DATA` | Defaults to `true`; set to `false` to stop inserting demo appointments. |
| `STUDIO_NAME`, `PUBLIC_PHONE`, `PUBLIC_EMAIL`, `PUBLIC_CITY` | Public studio details. |
| `BUSINESS_TIMEZONE` | Defaults to `Africa/Algiers`. |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, `MAIL_TO` | Optional SMTP notification settings. |

## Tests

```powershell
python -m pytest
```

## Before accepting real bookings

Update all fictional details, define appointment and cancellation rules, use a durable PostgreSQL database and backups, change all secrets, disable demo data, configure and test notification email, review your privacy policy, and test booking conflicts and cancellations in the deployed environment. This starter does not take payments, sync calendars, or send customer confirmations unless you add and configure that integration.
