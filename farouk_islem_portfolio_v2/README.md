# Farouk Islem — Portfolio

A lightweight, responsive, single-page Flask portfolio in Arabic and English. It includes a manual language switch, dark/light themes, an expandable project gallery, contact form, visitor feedback with moderation, and an optional contribution link. Subtle scroll-reveal animations respect reduced-motion preferences. No JavaScript framework, external font, or third-party front-end library is required.

## Run on Windows

1. Extract the entire ZIP into a folder. Do not launch `app.py` before extracting the archive.
2. Install Python 3.12 or newer from [python.org](https://www.python.org/downloads/windows/) and select **Add python.exe to PATH**.
3. Double-click `run_windows.bat` and keep its window open.
4. When the server starts, open `http://127.0.0.1:5000`.

The first run downloads the Python dependencies, so it needs an internet connection. If installation fails, keep the window open and read the error shown there.

### Run manually

From PowerShell inside the project folder:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`. The site works without SMTP or a payment URL, but email sending and financial contributions stay disabled until you configure those destinations.

## Language and appearance

- The initial language follows the browser's language preference (Arabic or English); the visitor can switch manually using **English / العربية**.
- The selected language is saved in a cookie for one year.
- The theme control switches between dark and light mode and remembers the selection.
- The English page uses left-to-right layout; Arabic uses right-to-left layout.

## Project gallery

The first two projects are shown initially. The **Show more projects / عرض المزيد من المشاريع** control only appears when the list in `app.py` contains more projects than `INITIAL_PROJECT_COUNT`. Each card has two independent destinations: a live preview and source code. If a destination does not exist, it is shown as unavailable rather than linking to an invented page.

To add a project, add a dictionary to `PROJECTS` in `app.py` with these fields:

- `title`
- `category_ar`, `category_en`
- `description_ar`, `description_en`
- `stack` (a list of technology tags)
- `live_url` and `source_url` (use an empty string until the destination really exists)
- `visual` (`lumina` or `kora` for the current preview artwork)
- `alt_ar`, `alt_en`

The project gallery is generated from this list, so you do not need to add another card manually in the HTML.

## Visitor ratings and comments

The feedback form stores ratings in a local SQLite database. New submissions are **pending by default** and are not published until you approve them. The visitor's name and comment are only kept for possible public display when they explicitly tick the consent checkbox; without consent, only the rating is stored. Submitted text is escaped by Jinja when displayed.

1. Copy `.env.example` to `.env` for local setup.
2. Set `FEEDBACK_ADMIN_PASSWORD` to a strong, unique password. Do not reuse your email password.
3. Open `/manage-feedback` on your website and sign in using that password.
4. Approve appropriate submissions or reject them. Only approved ratings contribute to the published rating summary; a written review is displayed only when the visitor consented to publication.

No testimonials, customer names, ratings, or quotes are pre-filled. The empty state is intentional until real visitors send feedback.

### Keep feedback when deployed

SQLite data is stored at `instance/portfolio.sqlite3` by default. On a hosting service with an ephemeral filesystem, stored feedback may be lost on redeploy/restart. If your host supports a persistent disk, mount it (for example at `/var/data`) and set `PORTFOLIO_DB_PATH=/var/data/portfolio.sqlite3`. Otherwise use a managed persistent database before relying on feedback storage for a live site. Do not commit database files to GitHub.

## Optional financial support link

A real payment destination must be created by you first. Put your actual support page URL in `SUPPORT_URL` in `.env` locally or in your hosting provider's environment settings. The portfolio presents support as a discreet text link alongside the existing footer links, with no separate card, extra description, or floating button. The link appears only when `SUPPORT_URL` contains a valid HTTPS destination; if it is blank, no support link is shown. The application does not invent or assume a PayPal/Ko-fi account. Support remains optional and separate from client services.

## Contact form email delivery

The contact form sends to `CONTACT_EMAIL` using SMTP, and does not store project enquiries in the database. To enable it, configure these environment values (for Gmail, use an App Password, not your normal account password):

- `MAIL_SERVER=smtp.gmail.com`
- `MAIL_PORT=587`
- `MAIL_USERNAME` — the sending email address
- `MAIL_PASSWORD` — its app password
- `CONTACT_EMAIL` — the inbox that receives messages

Without SMTP values, the site remains usable and shows visitors direct email/WhatsApp alternatives; it does not falsely report that an email was sent.

## Deploy on Render

1. Upload the **contents** of this folder to your GitHub repository.
2. Create a Render Web Service and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn --bind 0.0.0.0:$PORT app:app` (the included `Procfile` also configures Gunicorn).
5. Add environment variables in Render settings rather than committing `.env`. At minimum set a strong `SECRET_KEY`, `FEEDBACK_ADMIN_PASSWORD`, and the correct `SITE_URL`. Set `COOKIE_SECURE=1` on an HTTPS deployment.
6. Add SMTP settings to enable email delivery. Add `SUPPORT_URL` only after you have created and tested a real contribution link.
7. For feedback to persist, configure a persistent disk/database and point `PORTFOLIO_DB_PATH` to it. A writable but ephemeral local filesystem is not reliable long-term storage.
8. Test the live URL, both languages, both themes, contact delivery, the feedback moderation flow, mobile layout, and all project links.

## Helpful routes

- `/` — portfolio
- `/health` — health check (`{"status":"ok"}`)
- `/manage-feedback` — password-protected review moderation
- `/robots.txt` and `/sitemap.xml` — basic search crawler files (set the correct `SITE_URL` for a sitemap)

## Security and privacy notes

- Set a long, random `SECRET_KEY` in production. Never commit `.env`.
- The admin moderation route uses a password and CSRF-protected forms. Keep `FEEDBACK_ADMIN_PASSWORD` private.
- Contact enquiries are sent to email only when SMTP is configured. Feedback ratings are stored in SQLite; names/comments are retained for possible publication only after explicit consent, and remain pending until approval.
- Use HTTPS in production, and configure `COOKIE_SECURE=1` when using HTTPS.
- The feedback database is not an identity-verification mechanism. Approve only feedback you consider appropriate and never represent unverified submissions as confirmed client testimonials.
