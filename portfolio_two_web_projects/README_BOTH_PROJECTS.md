# Two portfolio-ready Flask projects

This bundle contains two independent applications. Do not run them from the bundle root: extract a project folder and follow its own README.

## 1. `madar-services/` — MADAR Services
A bilingual service-business site with a quote-request form and protected request-management dashboard.

## 2. `noor-booking/` — NOOR Studio
A bilingual booking site with service-duration-aware availability, private booking references, cancellation rules, and protected appointment-management dashboard.

## Local setup
Each project has its own `run_windows.bat`, `requirements.txt`, `.env.example`, tests, and deployment configuration. On Windows, extract one folder, run `run_windows.bat`, then edit the created `.env` file before using admin features. The example brands, prices, contact details, requests, and appointments are fictional portfolio data.

## Before a public demo
Set unique `SECRET_KEY` and `ADMIN_PASSWORD` values, replace the example contact information, and inspect the project-specific README for database and email settings. Turn off sample records with `SEED_DEMO_DATA=false` if you do not want them in the admin dashboard.

## Before real commercial use
Use a durable PostgreSQL database with backups, set `SEED_DEMO_DATA=false`, configure and test SMTP notifications, replace the starter privacy notice with one appropriate to the actual business and local law, and test forms, appointments, status changes, and cancellation rules in the live environment. The apps do not include payment processing or external calendar/CRM integrations.

The files passed static Python syntax checks, Jinja template parsing, CSS parsing, JavaScript syntax checks, and archive-integrity checks. A live Flask/HTTP integration run was not possible in the build environment because Flask dependencies could not be downloaded there. Run the included `python -m pytest` tests after installing the requirements locally.
