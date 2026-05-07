# MedConsult - Telehealth Platform

A Django 4.2 LTS telehealth platform connecting patients with verified doctors through a slot-based appointment system. Built with a clean **Services/Selectors** architecture for maintainability and domain isolation.

---

## Features

### Authentication & Accounts
- Username **or** email login via a custom authentication backend
- Email verification enforced at login - unverified users are blocked with a resend link
- Multi-step signup wizards - 5 steps for patients, 6 steps for doctors
- Camera/microphone readiness test during signup
- Profile image uploads (PNG, JPG, JPEG, max 5 MB)
- Email verification and password reset via secure tokens
- Light / Dark / System theme preference per user
- **Two-factor authentication (2FA)** for doctors and admins via TOTP (django-two-factor-auth); manage from Settings - enable, disable, view backup code count, regenerate backup codes

### Scheduling
- Doctor self-service availability management with a visual weekly calendar
- Recurring availability windows with configurable buffer times
- Multi-type appointments per window (Video, Chat, Phone) with individual pricing
- Automatic slot generation from availability windows (nightly Celery task extends 60 days out)
- Manual / urgent slot creation
- Block / unblock individual slots
- Doctor time-off blocks - block date ranges, auto-block existing unbooked slots
- Group consultations - slots with `max_capacity > 1`, shows spots remaining to patients *(see Known Bugs - DB layer fix pending)*
- Real-time calendar updates via WebSocket (Django Channels) with HTMX polling fallback

### Patient Booking
- Browse and filter verified doctors (search, specialization, rating, price, availability, group sessions)
- Live slot availability updates - no page refresh needed
- Structured symptom/injury selector (20 body parts, 95 conditions, 10 symptom categories, 54 symptoms) powered by Alpine.js
- Price display before booking
- View, cancel, and reschedule appointments
- Join/leave waitlist when a doctor has no available slots - auto-notified when a slot opens
- **Patient data export** - download a full JSON copy of your data (profile, appointments, health records, prescriptions) at `/patient/export/`

### Reviews
- Patients rate doctors (1–5 stars) after completed appointments
- Optional comment per review
- Doctor detail pages show average rating, review count, and individual reviews

### Prescriptions
- Doctors write digital prescriptions for completed appointments
- Patients download prescriptions as PDF (ReportLab)
- Prescription content (diagnosis, medications, instructions) stored **encrypted at rest**

### Health Records
- Patients upload health documents (lab results, imaging, discharge summaries, etc.)
- Share specific records with individual doctors
- Doctors view shared records on patient history page
- All record views and shares logged to `HealthRecordAccessLog` for HIPAA audit trail

### Referrals
- Doctors refer patients to other specialists on the platform
- Patient receives in-app notification with link to target doctor's profile
- 30-day expiry per referral; patient sees all referrals in a dedicated page

### Notifications
- In-app notification bell in navbar (Alpine.js dropdown, HTMX-powered)
- Unread count badge; mark individual or all as read
- Triggered by: appointment booked/cancelled/rescheduled, prescription ready, doctor verified/rejected, waitlist slot available, referral received, health record shared

### Doctor Tools
- Analytics dashboard - monthly appointment volume (Chart.js), status breakdown, busiest days, type breakdown, ratings
- Patient history timeline - all past appointments, prescriptions, shared health records with a patient
- Schedule follow-up - send patient a link to book a specific future slot
- Refer patient to another specialist

### Admin Panel (`/internal/`)
- Dashboard with Chart.js analytics (user growth, appointment distribution)
- Doctor verification queue with document viewer (medical license, government ID)
- Doctor slot management - create, block, unblock, delete slots on behalf of doctors
- Patient management - view history, cancel appointments
- User management - search, filter, activate/deactivate, export to CSV
- Appointments list with filtering and CSV export
- Financial overview (revenue by doctor, appointment type usage)
- Full audit log - all admin actions, slot changes, and health record access with IP addresses

### Messaging & Consultations
- In-app chat (WebSocket-powered) linked to appointments or started directly without one
- Direct messaging between any patient and verified doctor - no appointment required
- Amber disclaimer banner on direct chats (dismissible); conversations only appear in list once a real message is sent
- Per-user soft delete - each side can delete a conversation from their view; admin retains all records
- File attachments in chat - upload documents, images, PDFs (10 MB max); rendered as inline download links
- **"Join Call" button** appears in chat header when an active video room exists for the appointment *(see Known Bugs - URL reference fix pending)*
- Video consultations via Daily.co (raises `ImproperlyConfigured` in prod if `DAILY_API_KEY` missing)

### Support & Legal
- Help center with dark mode support and quick-link cards to FAQ and Contact
- FAQ page with animated accordion interaction
- Contact form persists to DB and emails admin via Celery
- **Privacy Policy** at `/support/privacy/` - 8-section HIPAA-aware policy (data collection, HIPAA compliance, data sharing, retention, rights, cookies)
- **Terms of Service** at `/support/terms/` - 13-section telehealth ToS with emergency disclaimer, cancellation/refund policy, and governing law

### Payments
- Stripe integration (PaymentIntent + Checkout Session)
- Refund tracking

### Knowledge Graph (`/internal/knowledge-graph/`)
- Living network graph of the entire project state - auto-updates on every model change, git commit, and Celery heartbeat
- **Visualization**: Cytoscape.js force-directed interactive graph; nodes color-coded by type (users, appointments, slots, payments, code modules, system health); click any node for details; filter panel by node type; export JSON
- **Auto-update triggers**: Django signals (`post_save`/`post_delete`) on User, Appointment, Slot, Conversation, Payment → debounced Celery rebuild (max once per 10s); Celery Beat every 5 min; git `post-commit` hook
- **AI agent / CLI access**: `GET /api/v1/knowledge-graph/` returns structured JSON (metadata, stats summary, app structure, recent git commits, full nodes + edges); 60s Redis cache; `IsAdmin` auth
- **CLI**: `python manage.py export_knowledge_graph` writes `knowledge_graph.json` at project root; `--quick` flag for git hook (updates only git + stats nodes)

### Notifications & Reminders
- Email reminders at 24h and 1h before appointments (Celery Beat, every 15 min)
- SMS reminders via Twilio for patients with `phone_notifications=True`
- Appointment confirmation email + SMS on booking
- Doctor rejection email with reason
- Welcome email sent on successful email verification

---

## Security & Compliance

| Control | Status |
|---------|--------|
| Email verification enforced at login | ✅ |
| PHI encrypted at rest (prescriptions, license #, bank details) | ✅ django-cryptography |
| 2FA for doctors and admins (TOTP) | ✅ django-two-factor-auth |
| `SECRET_KEY` validated at startup in production | ✅ raises `ImproperlyConfigured` |
| `HealthRecordAccessLog` wired on all PHI reads/shares | ✅ |
| Patient data export (HIPAA Right of Access) | ✅ `/patient/export/` |
| Rate limiting - login (10/min), booking (10/h), messaging (60/min), API (30–120/min) | ✅ django-ratelimit + DRF throttle |
| Structured logging + optional Sentry integration | ✅ set `SENTRY_DSN` env var |
| Baseline test suite (pytest-django, 40% coverage gate) | ✅ |
| HSTS, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` in production | ✅ |
| Argon2 password hashing (memory-hard, HIPAA-recommended) | ✅ argon2-cffi |
| `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE='Lax'`, 30-min session age | ✅ |

---

## Frontend Design System

All pages are being progressively redesigned to share a cohesive look. When updating any page, match the palette, animation style, and layout patterns documented here.

### Color Palette

| Role | Light mode | Dark mode | Tailwind class |
|------|-----------|-----------|----------------|
| Page background | `#eff6ff → #eef2ff → #faf5ff` (animated gradient) | `#0f172a → #1e1b4b → #0f172a` | `hero-gradient` CSS class |
| Auth split - left panel | `#1e3a8a → #312e81 → #1e1b4b` (deep blue/indigo) | same | `hero-panel` CSS class |
| Public navbar | `bg-blue-50/90` + `backdrop-blur-sm` | `bg-gray-950/90` | `border-blue-100/60` separator |
| Authenticated navbar / sidebar | `bg-white dark:bg-gray-800` | same | unchanged |
| Primary action | `bg-blue-600 hover:bg-blue-700` | same | |
| Secondary / doctor accent | `bg-emerald-500` / `text-emerald-600` | `dark:text-emerald-400` | |
| Destructive | `bg-red-600` | `dark:bg-red-700` | |
| Card surface | `bg-white dark:bg-gray-800` | | |
| Subtle surface | `bg-gray-50 dark:bg-gray-900` | | |
| Glass card (on dark hero) | `bg-white/10 backdrop-blur-sm border border-white/20` | same | used for floating cards |

Exact gradient CSS:
```css
/* Landing hero - light */
.hero-gradient {
  background: linear-gradient(135deg, #eff6ff 0%, #eef2ff 50%, #faf5ff 100%);
  background-size: 200% 200%;
  animation: gradShift 8s ease infinite;
}
/* Landing hero - dark */
.dark .hero-gradient {
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
}
/* Auth split panel (always dark blue regardless of theme) */
.hero-panel {
  background: linear-gradient(145deg, #1e3a8a 0%, #312e81 45%, #1e1b4b 100%);
  background-size: 200% 200%;
  animation: gradShift 10s ease infinite;
}
```

### Animation Keyframes

Every redesigned page uses the same keyframe set defined in an inline `<style>` block within the template. **Do not put these in `custom.css` or `base.html` - keep them per-template so each page is self-contained.**

```css
@keyframes fadeUp    { from { opacity:0; transform:translateY(24px); } to { opacity:1; transform:translateY(0); } }
@keyframes fadeIn    { from { opacity:0; } to { opacity:1; } }
@keyframes floatY    { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-12px); } }
@keyframes floatSlow { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-8px); } }
@keyframes gradShift { 0%,100% { background-position:0% 50%; } 50% { background-position:100% 50%; } }
@keyframes blobPulse { 0%,100% { transform:scale(1) translate(0,0); } 33% { transform:scale(1.05) translate(8px,-8px); } 66% { transform:scale(.96) translate(-6px,6px); } }
```

Utility classes (also defined inline per template):
```css
.animate-fade-up    { animation: fadeUp .65s cubic-bezier(.16,1,.3,1) both; }
.animate-float      { animation: floatY 3.8s ease-in-out infinite; }
.animate-float-slow { animation: floatSlow 5.5s ease-in-out infinite; }
.delay-50  { animation-delay: .05s; }  /* through .delay-600 in steps of 50ms */
```

Entry animations are staggered: first element `.delay-50`, next `.delay-100`, next `.delay-150`, etc. - creating a cascade effect on page load.

### Layout Patterns

**Auth pages (login, signup role-select, and future: forgot password, reset password)**
- Extend `base.html` directly and override `{% block body %}` for full-screen control
- `min-h-screen flex` outer wrapper - no public header/footer
- Left 48–52% (`hidden lg:flex`): `hero-panel` dark blue gradient + floating glass cards + logo + tagline
- Right flex-1: `bg-white dark:bg-gray-900`, form with staggered `.animate-fade-up` entries
- Floating cards on the left use `animate-float` / `animate-float-slow` with staggered `animation-delay`
- Background decorative blobs: `border-radius: 60% 40% 30% 70% / ...` + `filter: blur(52px)` + `blobPulse` animation

**Landing page**
- Extends `layouts/public.html` (gets the blue-50 navbar)
- Full-width sections: hero gradient → blue stats bar → feature cards grid → "how it works" → CTA
- Feature cards use `.feature-card { transition: transform .25s; }` + `:hover { transform: translateY(-4px); }`

**Authenticated app pages** - defer to existing `layouts/app.html` styling (no redesign needed unless requested).

**Admin pages** - defer to existing `layouts/admin.html` (dark sidebar, `bg-gray-900`).

### Dark Mode

All redesigned templates use Tailwind `dark:` variant classes directly (e.g. `dark:bg-gray-900`, `dark:text-white`). The `.dark` class is toggled on `<html>` by `static/js/theme_switcher.js`. **Do not use CSS custom properties (`var(--color)`) or global overrides in `custom.css`** - they break button styles. Only `dark:` Tailwind classes.

### Pages Redesigned So Far

| Page | Template | Status |
|------|----------|--------|
| Landing / home | `apps/accounts/templates/accounts/landing.html` | ✅ Done |
| Login | `apps/accounts/templates/accounts/login.html` | ✅ Done |
| Sign up - role select | `apps/accounts/templates/accounts/signup_role_select.html` | ✅ Done |
| Sign up wizard (patient 5-step / doctor 6-step) | `apps/accounts/templates/accounts/signup_wizard.html` + partials | ✅ Done (animated gradient, frosted glass card, dark mode throughout) |
| Public navbar | `templates/layouts/public.html` | ✅ Done (blue-50 glass) |
| Admin layout dark mode | `templates/layouts/admin.html` | ✅ Done |
| Help center | `apps/support/templates/support/help.html` | ✅ Done (full dark mode, icon badges, hover cards) |
| FAQ | `apps/support/templates/support/faq.html` | ✅ Done (accordion interaction, dark mode) |
| Privacy Policy | `apps/support/templates/support/privacy_policy.html` | ✅ Done |
| Terms of Service | `apps/support/templates/support/terms_of_service.html` | ✅ Done |
| Forgot Password | `apps/accounts/templates/accounts/forgot_password.html` | ✅ Done (split layout, animated lock icon, floating security cards) |
| Reset Password | `apps/accounts/templates/accounts/reset_password.html` | ✅ Done (split layout, password strength meter, show/hide toggles, match indicator) |

All remaining pages will be redesigned one by one. Each must follow the palette, animation keyframes, and layout patterns above.

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 4.2.27 LTS |
| Database | PostgreSQL 16 |
| Cache / Channel Layer | Redis 7 |
| WebSocket | Django Channels 4 + Daphne |
| Async Tasks | Celery + django-celery-beat |
| Frontend | Tailwind CSS (CDN) + HTMX + Alpine.js |
| PHI Encryption | django-cryptography |
| Password Hashing | argon2-cffi (Argon2, memory-hard) |
| 2FA | django-two-factor-auth + django-otp |
| Rate Limiting | django-ratelimit + DRF throttle |
| Error Tracking | Sentry SDK (optional, via `SENTRY_DSN`) |
| PDF Generation | ReportLab |
| Payments | Stripe |
| Video | Daily.co |
| SMS | Twilio |
| Testing | pytest-django + pytest-cov |
| Graph Visualization | Cytoscape.js |
| Container | Docker + Docker Compose |

---

## Project Structure

```
MedConsult/
├── apps/
│   ├── accounts/        # User auth, profiles, tokens, notifications, 2FA middleware
│   ├── scheduling/      # Availability, slots, appointments, reviews, symptoms,
│   │                    # prescriptions, health records, referrals, waitlist, time-off
│   ├── dashboard/       # Role-based home pages
│   ├── adminpanel/      # Admin dashboard, management, HealthRecordAccessLog
│   ├── payments/        # Stripe payments and refunds
│   ├── messaging/       # In-app chat (WebSocket)
│   ├── consultations/   # Video rooms (Daily.co)
│   ├── api/             # REST API (JWT auth, DRF - requires authentication)
│   ├── support/         # Help, FAQ, contact
│   └── knowledge_graph/ # Living knowledge graph - signals, Celery task, Cytoscape UI, AI agent API
├── config/
│   ├── settings/
│   │   ├── base.py      # Shared settings (logging, Sentry, throttle, Beat schedule)
│   │   ├── dev.py       # Development
│   │   └── prod.py      # Production (SECRET_KEY guard, HSTS, SSL)
│   ├── urls.py
│   └── asgi.py          # ASGI + Django Channels routing
├── templates/
│   ├── base.html
│   ├── layouts/         # public.html, app.html, admin.html
│   ├── partials/        # navbar (with notification bell), footer, messages
│   └── components/      # avatar, dropdown
├── static/
│   └── js/
│       ├── availability_calendar.js
│       ├── signup_wizard.js
│       ├── dropdown.js
│       └── theme_switcher.js
├── .github/workflows/django-ci.yml   # CI: check → migrations → pytest --cov
├── pytest.ini
├── docker-compose.yml
├── dev_gui.py           # Desktop launcher (Control / SQL / Terminal / Accounts tabs)
└── requirements.txt
```

Each app follows a consistent layout:

```
apps/<name>/
├── models.py      # Database models
├── services.py    # Write operations (wrapped in @transaction.atomic)
├── selectors.py   # Read operations (queries, filters)
├── views.py       # Thin HTTP handlers
├── urls.py        # URL routing
├── forms.py
├── tests.py
└── templates/
```

---

## Quick Start

### Option 1 - Automated (recommended)

```bash
./init.sh
```

This starts Docker services, creates a virtual environment, installs dependencies, runs migrations, and seeds the admin account.

Then:

```bash
source venv/bin/activate
python manage.py runserver --settings=config.settings.dev
```

### Option 2 - Manual

```bash
# 1. Start PostgreSQL and Redis
docker-compose up -d

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file
cp .env.example .env

# 5. Run migrations
python manage.py migrate --settings=config.settings.dev

# 6. Create admin user
python manage.py createsuperuser --settings=config.settings.dev

# 7. Start the server
python manage.py runserver --settings=config.settings.dev
```

Visit: **http://127.0.0.1:8000**

### Local GUI Control Panel

Run the unified desktop launcher:

```bash
python dev_gui.py
```

Tabs:
- **Control** - start/stop Docker, server, Celery worker, Beat; live logs
- **SQL** - write raw SQL against the dev database and see results inline
- **Terminal** - run shell commands with streaming output and command history
- **Accounts** - view seeded users, reset passwords, toggle active status
- **Page Health** - one-click check that hits every page as admin, doctor, and patient; color-codes 200 / warnings / 500 errors so broken routes are caught immediately

Startup sequence:

```
Start Stack       # Docker + server + worker + beat in one click
```

Or manually:
1. `Start Docker` → `Run Migrations` → `Start Server` → `Start Worker` → `Start Beat`

### WebSocket support (Daphne)

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Async tasks (Celery)

```bash
# Worker (email, SMS, notifications)
celery -A config worker -l info

# Beat scheduler (reminders, nightly slot extension)
celery -A config beat -l info
```

---

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@medconsult.com | admin123 |
| Doctor | doctor@test.com | testpass123 |
| Patient | patient@test.com | testpass123 |

> **Note:** Doctors and admins are redirected to TOTP 2FA setup on first login after the `EnforceTwoFactorMiddleware` triggers. Use an authenticator app (Google Authenticator, Authy, etc.) to scan the QR code at `/account/two_factor/setup/`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes (prod) | Django secret key - startup raises `ImproperlyConfigured` if missing or insecure in production |
| `DB_*` | Yes | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| `REDIS_HOST` / `REDIS_URL` | Yes | Redis connection |
| `SENTRY_DSN` | Optional | Sentry error tracking - Sentry is disabled if not set |
| `SENTRY_TRACES_RATE` | Optional | Sample rate for performance tracing (default `0.1`) |
| `DJANGO_LOG_LEVEL` | Optional | Django log level (default `INFO`) |
| `STRIPE_PUBLISHABLE_KEY` | Optional | Stripe public key |
| `STRIPE_SECRET_KEY` | Optional | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Optional | Stripe webhook signing secret |
| `DAILY_API_KEY` | Optional | Daily.co video rooms - raises `ImproperlyConfigured` in prod if missing |
| `TWILIO_ACCOUNT_SID` | Optional | Twilio SMS |
| `TWILIO_AUTH_TOKEN` | Optional | Twilio SMS |
| `TWILIO_PHONE_NUMBER` | Optional | Twilio SMS sender |
| `EMAIL_HOST` / `EMAIL_PORT` | Optional | SMTP config for prod email |
| `DEFAULT_FROM_EMAIL` | Optional | Sender address |

---

## Running Tests

```bash
# Run full test suite with coverage
pytest

# Run specific app
pytest apps/accounts/
pytest apps/scheduling/

# Coverage only (no fail threshold)
pytest --cov=apps --cov-report=term-missing --no-cov-on-fail
```

CI enforces **40% coverage minimum**. Coverage XML report is uploaded as a build artifact on every run.

---

## URL Reference

```
Public
/                                         Landing page
/auth/login/                              Login (email or username)
/auth/signup/                             Role selection
/auth/signup/patient/<step>/              Patient signup wizard (5 steps)
/auth/signup/doctor/<step>/               Doctor signup wizard (6 steps)
/account/two_factor/setup/               2FA TOTP setup (doctors + admins)
/account/two_factor/                     2FA profile / backup tokens
/support/help/                            Help center
/support/faq/                             FAQ
/support/contact/                         Contact
/support/privacy/                         Privacy Policy
/support/terms/                           Terms of Service

Authenticated (all roles)
/app/                                     Role-based dashboard redirect
/auth/profile/                            Profile (edit, upload image, languages)
/auth/settings/                           Account settings (theme, notifications)
/auth/notifications/                      Full notification history

Patient - /patient/
  doctors/                                Browse verified doctors
  doctors/<id>/                           Doctor detail (slots, reviews, bio, languages)
  doctors/<id>/slots/                     Live slot updates (HTMX polling)
  doctors/<id>/waitlist/join/             Join waitlist
  doctors/<id>/waitlist/leave/            Leave waitlist
  book/<slot_id>/                         Book appointment
  appointments/                           My appointments (cancel, reschedule, download Rx)
  appointments/<id>/cancel/               Cancel appointment
  appointments/<id>/reschedule/           Reschedule appointment
  appointments/<id>/prescription/download/ Download prescription PDF
  reviews/<appointment_id>/submit/        Submit review
  referrals/                              My referrals from doctors
  health-records/                         Upload and manage health records
  health-records/<id>/delete/             Delete health record
  health-records/<id>/share/              Share record with a doctor
  export/                                 Download full personal data export (JSON)
  symptoms/body-parts/                    Symptom selector - body parts (HTMX)
  symptoms/body-parts/<id>/conditions/    Conditions for a body part (HTMX)
  symptoms/list/                          Symptom list (HTMX)

Doctor - /doctor/
  availability/                           Availability management (calendar + windows)
  availability/windows/create/            Create availability window
  availability/windows/<id>/              Edit availability window form (HTMX)
  availability/windows/<id>/update/       Update availability window
  availability/windows/<id>/delete/       Delete availability window
  availability/slots/create/              Create manual/urgent/group slot
  availability/slots/<id>/block/          Block slot
  availability/slots/<id>/unblock/        Unblock slot
  availability/slots/<id>/delete/         Delete slot
  availability/calendar/                  Calendar partial (HTMX)
  availability/types/                     Configure appointment types & pricing
  availability/time-off/                  Manage time-off / vacation blocks
  availability/time-off/<id>/delete/      Delete time-off block
  schedule/                               Upcoming appointments (write Rx, follow-up, refer)
  generate-slots/                         Generate slots from windows
  analytics/                              Analytics dashboard (Chart.js)
  appointments/<id>/prescription/write/   Write prescription
  appointments/<id>/followup/             Schedule follow-up for patient
  appointments/<id>/referral/             Refer patient to specialist
  patients/<id>/history/                  Full patient history timeline
  patients/<id>/records/                  Shared health records from patient

Admin - /internal/
  (dashboard)                             Metrics, charts, activity feed
  verify/                                 Doctor verification queue
  verify/<id>/approve/                    Approve doctor
  verify/<id>/reject/                     Reject doctor with reason
  users/                                  User list (search, filter)
  users/<id>/toggle-active/              Activate / deactivate user
  users/export/                           Export users CSV
  doctors/                                Doctor list with statistics
  doctors/<id>/manage/                    Doctor slot management
  doctors/<id>/calendar/                  Doctor calendar (HTMX)
  doctors/<id>/slots/create/              Create slot for doctor
  doctors/<id>/document/<type>/           View doctor documents
  slots/<id>/block/                       Block slot
  slots/<id>/unblock/                     Unblock slot
  slots/<id>/delete/                      Delete slot
  patients/<id>/manage/                   Patient appointment management
  appointments/                           Appointments list
  appointments/<id>/cancel/               Cancel appointment
  appointments/export/                    Export appointments CSV
  financial/                              Revenue and pricing overview
  audit/                                  Audit logs + health record access log

Other
/payments/checkout/<slot_id>/             Payment checkout
/payments/history/                        Payment history
/messages/                                Conversations list
/messages/<id>/                           Chat window
/messages/<id>/delete/                    Delete conversation (soft, per-user)
/messages/start/<appointment_id>/         Start appointment-linked chat
/messages/direct/doctor/<id>/            Patient starts direct chat with doctor
/messages/direct/patient/<id>/           Doctor starts direct chat with patient
/consultation/<id>/                       Video room
/api/v1/                                  REST API (JWT)
/api/v1/knowledge-graph/                 Full project knowledge graph (JSON, IsAdmin)
/internal/knowledge-graph/               Interactive Cytoscape.js graph UI
/admin/                                   Django admin
```

---

## Development Commands

```bash
# Database
python manage.py migrate --settings=config.settings.dev

# Check for missing migrations
python manage.py makemigrations --check --dry-run --settings=config.settings.dev

# Run tests
pytest
pytest apps/scheduling/

# System check
python manage.py check --settings=config.settings.dev

# Django shell
python manage.py shell --settings=config.settings.dev
```

### Docker

```bash
docker-compose up -d
docker-compose down
docker-compose logs postgres
docker-compose exec postgres psql -U medconsult_user -d medconsult
docker-compose exec redis redis-cli
```

> **WSL2 note:** If you see `client version 1.43 is too old`, add `export DOCKER_API_VERSION=1.44` to your `~/.bashrc` and reload (`source ~/.bashrc`). `dev_gui.py` sets this automatically.

---

## Architecture

### Services / Selectors Pattern

- **`services.py`** - all write operations (create, update, delete), wrapped in `@transaction.atomic`
- **`selectors.py`** - all read operations (queries, filters)
- **`views.py`** - thin HTTP handlers; call services/selectors, return responses

### Real-Time Updates

- `ws/doctor/<id>/calendar/` - doctor's weekly calendar (Django Channels)
- `ws/patient/doctor/<id>/slots/` - patient booking view (Django Channels)
- HTMX polling (5s interval, `X-Last-Update` header) as WebSocket fallback

### Template Inheritance (4 layers)

```
base.html                   Tailwind CDN, meta, scripts
└── layouts/public.html     Non-authenticated pages
└── layouts/app.html        Authenticated pages (navbar + footer)
└── layouts/admin.html      Admin panel (dark sidebar)
    └── page templates
        └── partials/       HTMX swap targets
```

### Celery Beat Schedule

| Task | Schedule |
|------|----------|
| `schedule_appointment_reminders` | Every 15 minutes |
| `mark_completed_appointments` | Every 5 minutes |
| `mark_no_show_appointments` | Every 10 minutes |
| `extend_slots_for_all_doctors` | Daily at 02:00 UTC |

### Migration State

| App | Latest Migration |
|-----|-----------------|
| accounts | 0014_clear_plaintext_encrypted_fields |
| scheduling | 0017_clear_plaintext_prescription_fields |
| adminpanel | 0003_rename_healthrecordaccesslog_indexes |
| payments | (initial) |
| messaging | 0004_conversation_delete_flags |
| consultations | (initial) |
| support | 0002_seed_faqs |
| knowledge_graph | 0001_initial |

---

## Known Bugs

These are confirmed broken - not gaps or missing features, but code that silently fails or errors at runtime. Fix before adding new features.

| # | Severity | Bug |
|---|----------|-----|
| B1 | 🔴 High | **Group consultations silently broken** - `Appointment.slot` is `OneToOneField`; a second booking on the same group slot hits a DB constraint. `max_capacity > 1` is currently impossible to honor. Fix: change to `ForeignKey` + `select_for_update()` capacity check. |
| B2 | 🔴 High | **No booking/payment state machine** - if a user abandons the Stripe redirect, the appointment is left in an indeterminate state with no timeout or cleanup. Needs `booking_status` (held/confirmed/expired/cancelled), `payment_status`, slot hold timeout (10–15 min), and webhook-first confirmation. |
| B3 | 🟡 Medium | **Patient data export has field mismatches** - the export service references model paths that don't match the actual schema (phone field relation, appointment type path). HIPAA Right of Access must be reliable. Needs a tested export selector + assertion test. |
| B4 | 🟡 Medium | **"Join Call" URL is wrong** - chat template references a consultation URL namespace/name that doesn't exist in `apps/consultations/urls.py`. Results in `NoReverseMatch` at runtime. |
| B5 | 🟡 Medium | **Admin decorator redirects to wrong namespace** - `accounts:login` may not resolve, causing `NoReverseMatch` when unauthenticated users hit admin routes. |
| B6 | 🟡 Medium | **2FA policy inconsistent** - docs say doctors/admins required, patients optional. Middleware allows all users to bypass via session flag. Doctors/admins must not be able to skip. |
| B7 | 🟡 Medium | **CI never runs the test suite** - GitHub workflow stops after migrations. `pytest` is declared but never executed; the 40% coverage gate is not enforced in CI. |
| B8 | 🔴 High | **Slot booking has no row lock** - no `select_for_update()` around the availability check. Two concurrent requests can book the same slot. |

---

## Known Limitations

- **Stripe payments** - admin refund button wired (`/internal/appointments/` → modal); patient-side refund request not yet implemented.
- **Booking/payment state machine** - see Bug B2 above.
- **Daily.co video** - API integration present; no test run documented. Raises `ImproperlyConfigured` in prod if `DAILY_API_KEY` is missing (safe fail).
- **Twilio SMS** - configured in `.env`; not verified with real credentials.
- **Email sending** - uses Django console backend in dev (no real emails sent).
- **Doctor location/geographic search** - `DoctorProfile` has no city/state/country fields; no location filter on doctor search.
- **Private media** - uploaded files (health records, IDs, profile images) are served from `/media/` without auth checks or signed URLs. Not suitable for production PHI storage.
- **Production frontend assets** - Tailwind, HTMX, Alpine, Chart.js, Cytoscape all loaded from CDN. No CSP headers or SRI hashes yet.
- **i18n** - `LocaleMiddleware` and `LANGUAGES` configured; zero translated `.po` files exist. UI is English-only.

---

## Backlog

> Items are ordered by impact. Bugs = confirmed broken code (fix first); P0 = security/HIPAA compliance; P1 = functional gaps; P2 = quality/ops; P3 = future features.

### Bugs - Fix Before New Features

| # | Status | Item |
|---|--------|------|
| B1 | 🔲 Open | **Group booking DB fix** - change `Appointment.slot` from `OneToOneField` → `ForeignKey`; add `select_for_update()` capacity check |
| B2 | 🔲 Open | **Booking/payment state machine** - `booking_status`, `payment_status`, slot hold timeout, idempotency key, webhook-first confirmation |
| B3 | 🔲 Open | **Patient data export field audit** - verify all serialized fields match actual model schema; add assertion test |
| B4 | 🔲 Open | **"Join Call" URL fix** - correct namespace/name in `apps/messaging/templates/messaging/chat.html` |
| B5 | 🔲 Open | **Admin redirect namespace fix** - verify `accounts:login` resolves or use literal path |
| B6 | 🔲 Open | **2FA policy enforcement** - doctors/admins cannot bypass via session flag |
| B7 | 🔲 Open | **CI actually run pytest** - add `pytest --cov=apps --cov-fail-under=40` to `.github/workflows/django-ci.yml` |
| B8 | 🔲 Open | **Slot booking race condition** - wrap availability check + appointment create in `select_for_update()` transaction |

### P0 - Security & HIPAA Compliance

| # | Status | Item |
|---|--------|------|
| 1 | ✅ Done | **PHI encrypted at rest** - `medical_license_number`, `account_number`, `routing_number`, prescription fields encrypted with `django-cryptography` |
| 2 | ✅ Done | **2FA/MFA for doctors + admins** - TOTP via `django-two-factor-auth`; `EnforceTwoFactorMiddleware` redirects on first login |
| 3 | ✅ Done | **Email verification enforced at login** - unverified users blocked, resend link shown |
| 4 | ✅ Done | **`SECRET_KEY` insecure fallback removed** - `prod.py` raises `ImproperlyConfigured` if key is missing or starts with `django-insecure-` |
| 5 | ✅ Done | **`HealthRecordAccessLog` wired** - logged on all doctor views and patient share actions |
| 6 | ✅ Done | **Patient data export** - `/patient/export/` returns JSON with profile, appointments, health records, prescriptions |
| 7 | ✅ Done | **Baseline test suite** - `pytest-django`, 40% coverage gate enforced in CI and locally |
| 8 | ✅ Done | **Rate limiting expanded** - booking `10/h/user`, messaging `60/m/user`, API `30/m anon` + `120/m user` via DRF throttle |
| 9 | ✅ Done | **Structured logging + Sentry** - `LOGGING` dict in `base.py`; Sentry auto-initialised when `SENTRY_DSN` is set |

### P1 - Functional Gaps

| # | Status | Item |
|---|--------|------|
| 10 | ✅ Done | **Real contact form + FAQ model** - persists to DB, emails admin via Celery; 8 default FAQs seeded |
| 11 | 🔶 Partial | **Stripe end-to-end + refund button** - admin refund wired (`/internal/appointments/` → amber modal); patient-side refund request still open |
| 12 | ✅ Done | **Daily.co: fix silent demo fallback** - raises `ImproperlyConfigured` in prod; logs warning in dev |
| 13 | ✅ Done | **Message file attachments UI** - file input in chat, 10 MB max, extension allowlist, download links rendered |
| 14 | ✅ Done | **"Join video call" from chat** - green "Join Call" button in chat header when active VideoRoom exists |
| 15 | ✅ Done | **Group consultation browse filter** - "Group Sessions Available" checkbox in doctor search sidebar |
| 16 | ✅ Done | **`send_welcome_email_task`** - now called from `verify_email_token` after email confirmation |
| 17 | ✅ Done | **Doctor catalog API auth** - `DoctorListAPIView` + `DoctorSlotsAPIView` now require `IsAuthenticated` |
| 18 | 🔲 Open | **Doctor location/geographic search** - add `city`, `state`, `country` to `DoctorProfile`; wire into `get_filtered_doctors` |
| 19 | ✅ Done | **Living Knowledge Graph** - `apps/knowledge_graph/` app; Cytoscape.js UI at `/internal/knowledge-graph/`; AI agent JSON at `/api/v1/knowledge-graph/`; auto-updates via Django signals + Celery + git hook |
| 20 | 🔲 Open | **Patient-side refund request** - patient can request refund from appointments list; goes to admin review queue |
| 21 | 🔲 Open | **Privacy Cockpit** - patient-facing trust center: who accessed my record, consent history, device/session log, revoke doctor access, download audit log, delete request workflow |
| 22 | 🔲 Open | **Insurance + price transparency** - insurance accepted field on doctor profile; estimated cost before booking; superbill PDF after appointment; cancellation fee preview |
| 23 | 🔲 Open | **Provider verification depth** - NPI number, license expiry date, malpractice insurance, board certification, sanctions checklist, 30/60/90-day expiry reminders, verification status history |
| 24 | 🔲 Open | **Care continuity page** - post-appointment summary: notes, prescriptions, shared files, follow-up date, message link; auto-generated when appointment → completed |
| 25 | 🔲 Open | **Pre-visit telehealth readiness check** - per-visit (not just signup): camera/mic, private space confirmation, emergency contact/location, phone fallback, consent reconfirmation; triggered 5 min before start |
| 26 | 🔲 Open | **Symptom intake → risk routing** - red-flag detection (e.g. chest pain → ER warning + block booking), urgency level, suggested specialty, "not a diagnosis" disclaimer, doctor-visible intake summary |
| 27 | 🔲 Open | **Operational analytics** - no-show rate, cancelled slot rate, payment failure rate, avg wait time, refund rate, video connection failure rate; add to `/internal/` dashboard |

### P2 - Quality & Operational

| # | Status | Item |
|---|--------|------|
| P2-1 | 🔲 Open | Add `ruff` linter/formatter + `.pre-commit-config.yaml` with `ruff` + `detect-secrets` |
| P2-2 | ✅ Done | **Argon2 password hasher** - `argon2-cffi==23.1.0` in requirements; `Argon2PasswordHasher` first in `PASSWORD_HASHERS`; PBKDF2 kept as fallback |
| P2-3 | ✅ Done | **Session hardening** - `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`; `SESSION_COOKIE_AGE` reduced 86400 → 1800 (30 min) |
| P2-4 | ✅ Done | **`.env.example` completed** - added `SENTRY_TRACES_RATE`, `DJANGO_LOG_LEVEL` (all other vars were already present) |
| P2-5 | 🔲 Open | Seed management commands - `seed_symptoms.py`, `seed_test_users.py` |
| P2-6 | 🔲 Open | File upload magic-byte validation - replace client-`content_type` trust with `python-magic` MIME check + filename sanitization |
| P2-7 | 🔲 Open | Bandit security scan in CI |
| P2-8 | 🔲 Open | Document backup/DR - `pg_dump` cron for dev; managed DB PITR + S3 versioning for prod |
| P2-9 | 🔲 Open | Accessibility pass - `aria-label` on icon buttons, `aria-live` for HTMX regions, `alt` on images |
| P2-10 | 🔲 Open | **Private-media PHI architecture** - signed short-lived URLs, per-object auth check, encrypted storage, malware scan, file hash logging, immutable access logs; replace casual `/media/` serving |
| P2-11 | 🔲 Open | **CSP / production asset hardening** - `Content-Security-Policy` headers (`django-csp`), SRI hashes for CDN scripts, no third-party tracking on health pages |

### P3 - Future Features

| Item | Notes |
|------|-------|
| **FHIR R4 export** | Phase 1: export-only JSON for Patient/Practitioner/Appointment/MedicationRequest/Condition/Encounter. Phase 2: import. Phase 3: SMART-on-FHIR. ONC Cures Act pushes this. |
| **Remote patient monitoring - lite** | Patient-entered vitals (BP, glucose, weight, O2); threshold alerts; trend charts; CSV/FHIR export. Start manual, no wearables yet. |
| **Asynchronous consults** | Text + photo async review (dermatology, lab review, second opinion). No slot required; different pricing tier. |
| **i18n translations** | `LocaleMiddleware` wired; run `makemessages`, pick 2 target languages (Spanish + French recommended) |
| **React Native / Flutter mobile app** | Consume `/api/v1/`; API now requires authentication |
| **Doctor payout via Stripe Connect** | Bank info stored but never reaches Stripe; add Express accounts + transfers |
| **Video session recording** | Hardcoded off (`consultations/services.py:50`); requires patient consent flow + encrypted storage |
| **ePrescribing integration** | Replace PDF-only prescriptions with pharmacy network (e.g. Surescripts); requires vendor onboarding |
| **Push notifications** | Web Push / FCM for mobile readiness; add after mobile app decision |
