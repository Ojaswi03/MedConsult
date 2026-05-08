# MedConsult - Telehealth Platform

A Django 4.2 LTS telehealth platform connecting patients with verified doctors through a slot-based appointment system. Built with a clean **Services/Selectors** architecture for maintainability and domain isolation.

---

## Features

### Authentication & Accounts
- Username **or** email login via a custom authentication backend
- Email verification enforced at login - unverified users blocked with resend link
- Multi-step signup wizards - 5 steps for patients, 6 steps for doctors
- Camera/microphone readiness test during signup
- Profile image uploads (PNG, JPG, JPEG, max 5 MB)
- Email verification and password reset via secure tokens
- Light / Dark / System theme preference per user
- **Two-factor authentication (2FA)** for doctors and all org staff via TOTP (django-two-factor-auth); patients may skip; all hospital staff roles require TOTP; bypassed in dev via `SKIP_2FA = True` in `dev.py`
- **Multi-tenant organization system** - hospitals/clinics register as Organizations; staff join via invite; platform owner approves each org before it goes live
- **Hospital user identity** - each `OrganizationMembership` gets a unique `hospital_user_id` in `{PREFIX}-{ROLE}-{NNNN}` format (e.g. `CGH-DOC-0007`)
- **Argon2 password hashing** (PBKDF2 kept as fallback for existing hashes)

### Roles
Two-level role system:

**Global (`User.role`):**
- `platform_owner` (PlatOwner) - full platform control
- `platform_admin` (PlatAdmin) - MedConsult internal staff
- `doctor` - verified provider
- `patient` - platform-wide, not org-scoped
- `org_user` - hospital staff (any org role)

**Org membership (`OrganizationMembership.role`):**
- `hospital_owner` (Org Owner), `hospital_admin` (Org Admin), `doctor`, `scheduler`, `billing_staff`, `compliance_officer`, `clinical_staff`

### Scheduling
- Doctor self-service availability management with a visual weekly calendar
- Recurring availability windows with configurable buffer times
- Multi-type appointments per window (Video, Chat, Phone) with individual pricing
- Automatic slot generation from availability windows (nightly Celery task extends 60 days out)
- Manual / urgent slot creation; block / unblock individual slots
- Group consultations - slots with `max_capacity > 1`, capacity enforced via `select_for_update()`
- Real-time calendar updates via WebSocket (Django Channels) with HTMX polling fallback

### Patient Booking
- Browse and filter verified doctors (search, specialization, rating, price, availability, group sessions)
- Live slot availability updates via WebSocket / HTMX polling
- Structured symptom/injury selector (20 body parts, 95 conditions, 10 symptom categories, 54 symptoms)
- Slot booking creates `held` appointment -> redirects to Stripe checkout -> webhook confirms
- Free slots confirmed immediately without payment
- View, cancel, and reschedule appointments
- Join/leave waitlist when a doctor has no available slots - auto-notified when a slot opens
- Appointment reminders via email + SMS (Celery Beat)
- **Patient data export** - download a full JSON copy of your data (profile, appointments, health records, prescriptions) at `/patient/export/`

### Reviews
- Patients rate doctors (1-5 stars) after completed appointments
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

### Payments
- Stripe Checkout integration with idempotency key on session creation
- `booking_status` state machine: `held` -> `confirmed` / `expired` / `cancelled`
- Held appointments auto-expire after 15 minutes (Celery task frees the slot)
- Payment success page verifies `payment.status` server-side before showing confirmed UI
- Admin refund button with inline modal
- Patient data export includes payment history

### Video Consultations
- Daily.co video rooms created on appointment confirmation
- "Join Call" button visible in chat when active VideoRoom exists
- Recording hardcoded off (requires explicit consent flow before enabling)

### Messaging
- Real-time chat via WebSocket (Django Channels)
- File attachments (up to 10 MB)
- Typing indicators and read receipts
- Direct messaging from doctor to patient requires prior appointment relationship
- XSS protection via `escapeHtml()` / `safeUrl()` JS helpers

### Organization Management
- Hospital self-signup at `/org/register/` - pending approval by PlatOwner
- Platform owner approves/rejects/suspends orgs at `/internal/organizations/`
- Hospital owner invites staff via token-based invites (7-day expiry)
- Org-scoped dashboards for each role (owner, admin, scheduler, etc.)
- `ProviderOrganizationProfile` - per-org doctor profile (title, department, specialization, fee, accepting patients)
- PlatOwner can enter any org's panel, view all members (active + inactive), enable/disable accounts, change roles

### PlatOwner Panel (`/internal/`)
- Full platform dashboard with metrics and Chart.js visualizations
- User management with search/filter/activate/deactivate
- Doctor verification queue with document viewer
- Doctor slot management (visual weekly calendar, block/unblock, create slots)
- Patient management with full appointment history
- Appointments list with CSV export
- Financial overview by doctor
- Audit logs (admin actions + slot change logs)
- Organization management - approve/reject/suspend orgs, drill into any org, manage all members
- Knowledge Graph - live Cytoscape.js force-directed graph of platform entities (manual refresh, position retention, diff badge)

### Security (HIPAA)
- PHI encrypted at rest with `django-cryptography` (Fernet/AES-256): medical license, bank account/routing numbers, prescription fields
- Every PHI read logged to `HealthRecordAccessLog`
- Protected health record download - ownership/share/admin check before serving
- Rate limiting: booking 10/h/user, messaging 60/m/user, DRF 30/m anon + 120/m user
- HTTPS-only in prod; `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE='Lax'`, session age 30 min
- `SECRET_KEY` guard in prod - raises `ImproperlyConfigured` if missing or insecure
- Structured logging + Sentry (when `SENTRY_DSN` set)
- XSS protection in chat; direct messaging authorization

### Developer Tooling
- `dev_gui.py` - Tkinter GUI: Docker healthcheck, server/worker/beat launcher, SQL tab, Page Health tab (tests all routes), Accounts tab with per-field edit buttons (role, username, email, password, active, verified, doctor status)
- Living Knowledge Graph at `/internal/knowledge-graph/` - manual refresh button, position retention, change diff badge

---

## Security & Compliance

| Control | Status |
|---------|--------|
| Email verification enforced at login | ✅ |
| PHI encrypted at rest (prescriptions, license #, bank details) | ✅ django-cryptography |
| 2FA for doctors and org staff (TOTP) | ✅ django-two-factor-auth |
| `SECRET_KEY` validated at startup in production | ✅ raises `ImproperlyConfigured` |
| `HealthRecordAccessLog` wired on all PHI reads/shares | ✅ |
| Patient data export (HIPAA Right of Access) | ✅ `/patient/export/` |
| Rate limiting - login (10/min), booking (10/h), messaging (60/min), API (30-120/min) | ✅ django-ratelimit + DRF throttle |
| Structured logging + optional Sentry integration | ✅ set `SENTRY_DSN` env var |
| Baseline test suite (pytest-django, 40% coverage gate) | ✅ |
| HSTS, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` in production | ✅ |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 4.2 LTS |
| Database | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| WebSockets | Django Channels 4 (Daphne) |
| Async tasks | Celery + Celery Beat |
| Payments | Stripe (Checkout + Webhooks) |
| Video | Daily.co |
| SMS | Twilio |
| Auth | django-two-factor-auth + TOTP |
| Frontend | Tailwind CSS (CDN), HTMX, Alpine.js, Chart.js, Cytoscape.js |
| PDF | ReportLab |
| Password hashing | Argon2 (PBKDF2 fallback) |
| PHI encryption | django-cryptography (Fernet) |
| Testing | pytest-django + pytest-cov (40% gate) |
| CI | GitHub Actions |

---

## Project Structure

```
MedConsult/
├── apps/
│   ├── accounts/        # User auth, profiles, roles, org models, encryption
│   ├── scheduling/      # Availability, slots, appointments, reviews, symptoms,
│   │                    # prescriptions, health records, referrals, waitlist, time-off
│   ├── organizations/   # Hospital signup, org dashboards, staff invites, org switcher
│   ├── dashboard/       # Role-based home pages
│   ├── adminpanel/      # PlatOwner panel, verification, analytics, org management
│   ├── payments/        # Stripe payments and refunds
│   ├── messaging/       # In-app chat (WebSocket)
│   ├── consultations/   # Video rooms (Daily.co)
│   ├── api/             # REST API (JWT auth, DRF)
│   ├── support/         # Help, FAQ, contact, privacy policy, terms
│   └── knowledge_graph/ # Living knowledge graph - signals, Celery task, Cytoscape UI, AI agent API
├── config/
│   ├── settings/
│   │   ├── base.py      # Shared settings (logging, Sentry, throttle, Beat schedule)
│   │   ├── dev.py       # Development (SKIP_2FA=True)
│   │   └── prod.py      # Production (SECRET_KEY guard, HSTS, SSL)
│   ├── urls.py
│   └── asgi.py          # ASGI + Django Channels routing
├── templates/
│   ├── base.html
│   ├── layouts/         # public.html, app.html, admin.html
│   ├── partials/        # navbar (with notification bell), footer, org_switcher
│   └── organizations/   # Org dashboard templates
├── static/
│   └── js/
│       ├── availability_calendar.js
│       ├── signup_wizard.js
│       ├── dropdown.js
│       └── theme_switcher.js
├── .github/workflows/django-ci.yml   # CI: check -> migrations -> pytest --cov
├── pytest.ini
├── docker-compose.yml
├── dev_gui.py           # Desktop launcher (Control / SQL / Terminal / Accounts / Page Health tabs)
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

## Default Credentials

| Role | Username | Email | Password |
|------|----------|-------|----------|
| PlatOwner | `platowner` | `platowner@medconsult.com` | `platowner123` |
| Test Doctor | `testdoctor` | `doctor@test.com` | `testpass123` |
| Test Patient | `testpatient` | `patient@test.com` | `testpass123` |

> **Note:** Doctors and org staff are redirected to TOTP 2FA setup on first login. Use an authenticator app (Google Authenticator, Authy, etc.) to scan the QR code at `/account/two_factor/setup/`. In dev, `SKIP_2FA = True` bypasses this for all users.

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

# 6. Create platform owner user
python manage.py createsuperuser --settings=config.settings.dev

# 7. Start the server
python manage.py runserver --settings=config.settings.dev
```

Visit: **http://127.0.0.1:8000**

### Local GUI Control Panel

```bash
python dev_gui.py
```

Tabs:
- **Control** - start/stop Docker, server, Celery worker, Beat; live logs
- **SQL** - write raw SQL against the dev database and see results inline
- **Terminal** - run shell commands with streaming output and command history
- **Accounts** - view seeded users, per-field edit (role, username, email, password, active, verified)
- **Page Health** - one-click check that hits every page as admin, doctor, and patient; color-codes 200 / warnings / 500 errors

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

## Development Commands

```bash
# Database
python manage.py migrate --settings=config.settings.dev

# Check for missing migrations
python manage.py makemigrations --check --dry-run --settings=config.settings.dev

# Run tests
pytest --cov=apps --cov-fail-under=40

# Knowledge graph rebuild
python manage.py export_knowledge_graph --settings=config.settings.dev
python manage.py export_knowledge_graph --quick --settings=config.settings.dev

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

> **WSL2 note:** If you see `client version 1.43 is too old`, add `export DOCKER_API_VERSION=1.44` to your `~/.bashrc`.

---

## URL Reference

```
Public
/                                         Landing page (patient + hospital CTAs, For Hospitals section)
/auth/login/                              Login (email or username)
/auth/signup/                             Role selection
/auth/signup/patient/<step>/              Patient signup wizard (5 steps)
/auth/signup/doctor/<step>/               Doctor signup wizard (6 steps)
/account/two_factor/setup/                2FA TOTP setup (doctors + org staff)
/support/help/                            Help center
/support/faq/                             FAQ
/support/contact/                         Contact
/support/privacy-policy/                  Privacy policy
/support/terms-of-service/                Terms of service
/org/register/                            Hospital/clinic self-signup (links from landing nav + For Hospitals section)
/org/register/pending/                    Post-registration pending-approval page

Authenticated (all roles)
/app/                                     Role-based dashboard redirect
/auth/profile/                            Profile (edit, upload image)
/auth/settings/                           Account settings (theme, notifications, 2FA)
/auth/switch-org/                         Org switcher (platform staff)

Patient - /patient/
  doctors/                                Browse verified doctors
  doctors/<id>/                           Doctor detail (slots, reviews, bio)
  book/<slot_id>/                         Book appointment
  appointments/                           My appointments (cancel, reschedule, download Rx)
  appointments/<id>/cancel/               Cancel appointment
  appointments/<id>/reschedule/           Reschedule appointment
  appointments/<id>/prescription/download/ Download prescription PDF
  reviews/<appointment_id>/submit/        Submit review
  referrals/                              My referrals from doctors
  health-records/                         Upload and manage health records
  health-records/<id>/download/           Protected download (auth + ownership check)
  export/                                 Download full personal data export (JSON)

Doctor - /doctor/
  availability/                           Availability management (calendar + windows)
  availability/windows/create/            Create availability window
  availability/windows/<id>/update/       Update availability window
  availability/windows/<id>/delete/       Delete availability window
  availability/slots/create/              Create manual/urgent/group slot
  availability/slots/<id>/block/          Block slot
  availability/slots/<id>/unblock/        Unblock slot
  availability/slots/<id>/delete/         Delete slot
  availability/types/                     Configure appointment types & pricing
  schedule/                               Upcoming appointments (write Rx, follow-up, refer)
  analytics/                              Analytics dashboard (Chart.js)
  appointments/<id>/prescription/write/   Write prescription
  appointments/<id>/followup/             Schedule follow-up for patient
  appointments/<id>/referral/             Refer patient to specialist
  patients/<id>/history/                  Full patient history timeline
  patients/<id>/records/                  Shared health records from patient

Organization - /org/
  register/                               Hospital self-signup
  <slug>/                                 Org dashboard (role-based)
  <slug>/staff/                           Staff list with hospital_user_id
  <slug>/staff/invite/                    Invite staff member
  <slug>/staff/<id>/                      Member detail
  <slug>/staff/<id>/provider-profile/     Edit provider org profile
  <slug>/settings/                        Org settings
  invite/<token>/                         Accept invite

PlatOwner Panel - /internal/
  (dashboard)                             Metrics, charts, activity feed
  verify/                                 Doctor verification queue
  verify/<id>/approve/                    Approve doctor
  verify/<id>/reject/                     Reject doctor with reason
  users/                                  User list (search, filter, export)
  users/<id>/toggle-active/               Activate / deactivate user
  doctors/                                Doctor list with statistics
  doctors/<id>/manage/                    Doctor slot management
  patients/<id>/manage/                   Patient appointment management
  appointments/                           Appointments list (filter, export CSV)
  appointments/<id>/refund/               Issue refund
  financial/                              Revenue and pricing overview
  audit/                                  Audit logs + health record access log
  organizations/                          All orgs (approve/reject/suspend)
  organizations/<id>/                     Org detail - all members (active + inactive)
  organizations/<id>/members/<mid>/       Org member detail
  organizations/<id>/members/<mid>/toggle-membership/  Deactivate/reactivate membership
  organizations/<id>/members/<mid>/toggle-account/     Disable/enable user account
  organizations/<id>/members/<mid>/change-role/        Change org role
  knowledge-graph/                        Interactive Cytoscape.js graph UI

Other
/payments/checkout/<slot_id>/             Payment checkout
/payments/history/                        Payment history
/messages/                                Conversations list
/messages/<id>/                           Chat window
/messages/start/<appointment_id>/         Start appointment-linked chat
/consultation/<id>/                       Video room
/api/v1/                                  REST API (JWT)
/api/v1/knowledge-graph/                  Full project knowledge graph (JSON, PlatOwner auth)
/admin/                                   Django admin
```

---

## Architecture

### Services / Selectors Pattern

- **`services.py`** - all write operations (create, update, delete), wrapped in `@transaction.atomic`
- **`selectors.py`** - all read operations (queries, filters)
- **`views.py`** - thin HTTP handlers; call services/selectors, return responses

### Multi-Tenancy Scoping Rules
- Hospital staff - queries scoped to `organization`
- Doctors - scoped to their active org membership
- Patients - scoped by `patient=request.user`, never by org
- Platform staff - unscoped access (`allow_unscoped=True`)
- `organization=None` fails closed - returns `queryset.none()` unless platform access proven

### Template Inheritance (4 layers)

```
base.html                   Tailwind CDN, meta, scripts
- layouts/public.html     Non-authenticated pages
- layouts/app.html        Authenticated pages (navbar + footer)
- layouts/admin.html      PlatOwner panel (dark sidebar)
    - page templates
        - partials/       HTMX swap targets
```

### Real-Time Updates

- `ws/doctor/<id>/calendar/` - doctor's weekly calendar (Django Channels)
- `ws/patient/doctor/<id>/slots/` - patient booking view (Django Channels)
- HTMX polling (5s interval, `X-Last-Update` header) as WebSocket fallback

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
| accounts | 0022_backfill_hospital_user_id |
| scheduling | 0017_clear_plaintext_prescription_fields |
| adminpanel | 0003_rename_healthrecordaccesslog_indexes |
| payments | (initial) |
| messaging | 0004_conversation_delete_flags |
| consultations | (initial) |
| support | 0002_seed_faqs |
| knowledge_graph | 0001_initial |

Two default orgs seeded by data migration:
- **MedConsult Platform** (`platform`) - PlatOwner + PlatAdmin memberships
- **MedConsult Demo Clinic** (`clinic`) - test doctors and clinical data

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes (prod) | Django secret key - startup raises `ImproperlyConfigured` if missing or insecure in production |
| `DB_*` | Yes | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| `REDIS_HOST` / `REDIS_URL` | Yes | Redis connection |
| `SENTRY_DSN` | Optional | Sentry error tracking - disabled if not set |
| `SENTRY_TRACES_RATE` | Optional | Sample rate for performance tracing (default `0.1`) |
| `DJANGO_LOG_LEVEL` | Optional | Django log level (default `INFO`) |
| `STRIPE_PUBLISHABLE_KEY` | Optional | Stripe public key |
| `STRIPE_SECRET_KEY` | Optional | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Optional | Stripe webhook signing secret |
| `DAILY_API_KEY` | Optional | Daily.co video rooms - raises `ImproperlyConfigured` in prod if missing |
| `TWILIO_ACCOUNT_SID` | Optional | Twilio SMS |
| `TWILIO_AUTH_TOKEN` | Optional | Twilio SMS |
| `TWILIO_FROM_NUMBER` | Optional | Twilio SMS sender |
| `EMAIL_HOST` / `EMAIL_PORT` | Optional | SMTP config for prod email |
| `DEFAULT_FROM_EMAIL` | Optional | Sender address |

See `.env.example` for all variables.

---

## Running Tests

```bash
# Run full test suite with coverage
pytest --cov=apps --cov-fail-under=40

# Run specific app
pytest apps/accounts/
pytest apps/scheduling/

# Coverage report
pytest --cov=apps --cov-report=term-missing
```

CI enforces **40% coverage minimum** on every push.

---

## Backlog

> Items ordered by impact. P0 = security/HIPAA compliance; P1 = functional gaps; P2 = quality/ops; P3 = future features.

### P0 - Security & HIPAA Compliance

| # | Status | Item |
|---|--------|------|
| 1 | ✅ Done | **PHI encrypted at rest** - `medical_license_number`, `account_number`, `routing_number`, prescription fields encrypted with `django-cryptography` |
| 2 | ✅ Done | **2FA for doctors + org staff** - TOTP via `django-two-factor-auth`; `EnforceTwoFactorMiddleware` enforces for all elevated roles |
| 3 | ✅ Done | **Email verification enforced at login** - unverified users blocked, resend link shown |
| 4 | ✅ Done | **`SECRET_KEY` insecure fallback removed** - `prod.py` raises `ImproperlyConfigured` if key is missing or starts with `django-insecure-` |
| 5 | ✅ Done | **`HealthRecordAccessLog` wired** - logged on all doctor views and patient share actions |
| 6 | ✅ Done | **Patient data export** - `/patient/export/` returns JSON with profile, appointments, health records, prescriptions |
| 7 | ✅ Done | **Baseline test suite** - `pytest-django`, 40% coverage gate enforced in CI and locally |
| 8 | ✅ Done | **Rate limiting** - booking `10/h/user`, messaging `60/m/user`, API `30/m anon` + `120/m user` via DRF throttle |
| 9 | ✅ Done | **Structured logging + Sentry** - `LOGGING` dict in `base.py`; Sentry auto-initialised when `SENTRY_DSN` is set |
| 10 | ✅ Done | **Chat XSS protection** - `escapeHtml()` / `safeUrl()` JS helpers; all user content rendered via DOM API |
| 11 | ✅ Done | **Direct messaging auth** - doctors blocked from opening chats with patients they have no prior appointment with |
| 12 | ✅ Done | **PHI file download auth** - `health_record_download` checks ownership/share/admin before serving; every download logged |

### P1 - Functional Gaps

| # | Status | Item |
|---|--------|------|
| 13 | ✅ Done | **Real contact form + FAQ model** - persists to DB, emails admin via Celery; 8 default FAQs seeded |
| 14 | ✅ Done | **Stripe refund (admin side)** - refund button in appointments table, inline modal, posts to `/internal/appointments/<id>/refund/` |
| 15 | 🔲 Open | **Stripe refund (patient side)** - patient refund request UI not yet wired |
| 16 | ✅ Done | **Daily.co: fix silent demo fallback** - raises `ImproperlyConfigured` in prod; logs warning in dev |
| 17 | ✅ Done | **Message file attachments UI** - file input in chat, 10 MB max, extension allowlist, download links rendered |
| 18 | ✅ Done | **"Join video call" from chat** - green "Join Call" button in chat header when active VideoRoom exists |
| 19 | ✅ Done | **Group consultation browse filter** - "Group Sessions Available" checkbox in doctor search sidebar |
| 20 | ✅ Done | **Welcome email task** - called from `verify_email_token` after email confirmation |
| 21 | ✅ Done | **Doctor catalog API auth** - `DoctorListAPIView` + `DoctorSlotsAPIView` now require `IsAuthenticated` |
| 22 | ✅ Done | **Living Knowledge Graph** - Cytoscape.js UI at `/internal/knowledge-graph/`; manual refresh with position retention + diff badge; AI agent JSON at `/api/v1/knowledge-graph/` |
| 23 | ✅ Done | **Multi-tenant org system** - hospital signup, invite-based staff onboarding, role-scoped dashboards, PlatOwner approval flow |
| 24 | ✅ Done | **Hospital user identity** - `hospital_user_id` per membership; `ProviderOrganizationProfile` for org-scoped doctor profiles |
| 25 | ✅ Done | **PlatOwner org management** - drill into any org, view all members (active + inactive), enable/disable accounts, change roles |
| 26 | ✅ Done | **Booking state machine** - `booking_status` (held/confirmed/expired/cancelled); Celery expires held after 15 min |
| 27 | 🔲 Open | **Symptom risk routing** - emergency red flag detection (chest pain, stroke signs, etc.) should block booking and show ER warning |
| 28 | 🔲 Open | **Doctor location/geographic search** - add `city`, `state`, `country` to `DoctorProfile`; wire into search filter |
| 29 | 🔲 Open | **Pre-visit telehealth readiness check** - per-visit camera/mic test, private space confirmation, phone fallback |
| 30 | 🔲 Open | **Superbill / insurance transparency** - PDF superbill after completed appointment; insurance fields on doctor profile |
| 31 | 🔲 Open | **Care continuity page** - summary card after each appointment (notes, prescriptions, follow-up date, billing link) |
| 32 | 🔲 Open | **Privacy Cockpit** - patient sees who accessed their records, consent history, device log; can revoke doctor access |

### P2 - Quality & Operational

| # | Status | Item |
|---|--------|------|
| 33 | 🔲 Open | Add `ruff` linter/formatter + `.pre-commit-config.yaml` with `ruff` + `detect-secrets` |
| 34 | ✅ Done | Switch to Argon2 password hasher (`argon2-cffi`); HIPAA-ready, memory-hard |
| 35 | ✅ Done | Strengthen session security - `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE='Lax'`, `SESSION_COOKIE_AGE` 30 min |
| 36 | ✅ Done | Complete `.env.example` - `SENTRY_TRACES_RATE`, `DJANGO_LOG_LEVEL` added |
| 37 | 🔲 Open | File upload magic-byte validation - replace client `content_type` trust with `python-magic` MIME check + filename sanitization |
| 38 | 🔲 Open | Bandit security scan in CI |
| 39 | 🔲 Open | Private media PHI file architecture - signed short-lived URLs, per-object auth check, immutable access logs |
| 40 | 🔲 Open | Content-Security-Policy headers (`django-csp`); SRI hashes for CDN scripts |
| 41 | 🔲 Open | Accessibility pass - `aria-label` on icon buttons, `aria-live` for HTMX regions, `alt` on images |
| 42 | 🔲 Open | Operational analytics dashboard - no-show rate, cancellation rate, payment failure rate, avg wait time |

### P3 - Future Features

| Item | Notes |
|------|-------|
| **i18n translations** | `LocaleMiddleware` wired; run `makemessages`, pick 2 target languages |
| **React Native / Flutter mobile app** | Consume `/api/v1/`; API now requires authentication |
| **Doctor payout via Stripe Connect** | Bank info stored but never reaches Stripe; add Express accounts + transfers |
| **Video session recording** | Hardcoded off; requires patient consent flow + encrypted storage |
| **ePrescribing integration** | Replace PDF-only prescriptions with pharmacy network (e.g. Surescripts) |
| **FHIR R4 export** | Phase 1: export-only for Patient, Practitioner, Appointment, MedicationRequest |
| **Remote patient monitoring (lite)** | Patient-entered vitals (BP, glucose, weight); threshold alerts; trend charts |
| **Push notifications** | Web Push / FCM; register service worker now, defer until mobile app decision |
| **Asynchronous consults** | Patient submits text + photos; doctor responds on their own time; different pricing tier |

---

## Known Limitations

- **Stripe payments** - end-to-end flow configured; patient-side refund UI not yet wired.
- **Daily.co video** - API integration present; raises `ImproperlyConfigured` in prod if `DAILY_API_KEY` is missing (safe fail).
- **Twilio SMS** - configured in `.env`; not verified with real credentials.
- **Email sending** - uses Django console backend in dev (no real emails sent).
- **Doctor location/geographic search** - `DoctorProfile` has no city/state/country fields; no location filter on doctor search.
- **i18n** - `LocaleMiddleware` and `LANGUAGES` configured; zero translated `.po` files exist. UI is English-only.
