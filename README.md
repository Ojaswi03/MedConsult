# MedConsult — Telehealth Platform

A Django 5.2 telehealth platform connecting patients with verified doctors through a slot-based appointment system. Built with a clean **Services/Selectors** architecture for maintainability and domain isolation.

---

## Features

### Authentication & Accounts
- Username **or** email login via a custom authentication backend
- Multi-step signup wizards — 5 steps for patients, 6 steps for doctors
- Camera/microphone readiness test during signup
- Profile image uploads (PNG, JPG, JPEG, max 5 MB)
- Email verification and password reset via secure tokens
- Light / Dark / System theme preference per user

### Scheduling
- Doctor self-service availability management with a visual weekly calendar
- Recurring availability windows with configurable buffer times
- Multi-type appointments per window (Video, Chat, Phone) with individual pricing
- Automatic slot generation from availability windows (nightly Celery task extends 60 days out)
- Manual / urgent slot creation
- Block / unblock individual slots
- Doctor time-off blocks — block date ranges, auto-block existing unbooked slots
- Group consultations — slots with `max_capacity > 1`, shows spots remaining to patients
- Real-time calendar updates via WebSocket (Django Channels) with HTMX polling fallback

### Patient Booking
- Browse and filter verified doctors (search, specialization, rating, price, availability)
- Live slot availability updates — no page refresh needed
- Structured symptom/injury selector (20 body parts, 95 conditions, 10 symptom categories, 54 symptoms) powered by Alpine.js
- Price display before booking
- View, cancel, and reschedule appointments
- Join/leave waitlist when a doctor has no available slots — auto-notified when a slot opens

### Reviews
- Patients rate doctors (1–5 stars) after completed appointments
- Optional comment per review
- Doctor detail pages show average rating, review count, and individual reviews

### Prescriptions
- Doctors write digital prescriptions for completed appointments
- Patients download prescriptions as PDF (ReportLab)

### Health Records
- Patients upload health documents (lab results, imaging, discharge summaries, etc.)
- Share specific records with individual doctors
- Doctors view shared records on patient history page

### Referrals
- Doctors refer patients to other specialists on the platform
- Patient receives in-app notification with link to target doctor's profile
- 30-day expiry per referral; patient sees all referrals in a dedicated page

### Notifications
- In-app notification bell in navbar (Alpine.js dropdown, HTMX-powered)
- Unread count badge; mark individual or all as read
- Triggered by: appointment booked/cancelled/rescheduled, prescription ready, doctor verified/rejected, waitlist slot available, referral received, health record shared

### Doctor Tools
- Analytics dashboard — monthly appointment volume (Chart.js), status breakdown, busiest days, type breakdown, ratings
- Patient history timeline — all past appointments, prescriptions, shared health records with a patient
- Schedule follow-up — send patient a link to book a specific future slot
- Refer patient to another specialist

### Admin Panel (`/internal/`)
- Dashboard with Chart.js analytics (user growth, appointment distribution)
- Doctor verification queue with document viewer (medical license, government ID)
- Doctor slot management — create, block, unblock, delete slots on behalf of doctors
- Patient management — view history, cancel appointments
- User management — search, filter, activate/deactivate, export to CSV
- Appointments list with filtering and CSV export
- Financial overview (revenue by doctor, appointment type usage)
- Full audit log — all admin actions and slot changes with IP addresses

### Messaging & Consultations
- In-app chat (WebSocket-powered) linked to appointments or started directly without one
- Direct messaging between any patient and verified doctor — no appointment required
- Amber disclaimer banner on direct chats (dismissible); conversations only appear in list once a real message is sent
- Per-user soft delete — each side can delete a conversation from their view; admin retains all records
- Video consultations via Daily.co

### Payments
- Stripe integration (PaymentIntent + Checkout Session)
- Refund tracking

### Notifications & Reminders
- Email reminders at 24h and 1h before appointments (Celery Beat, every 15 min)
- SMS reminders via Twilio for patients with `phone_notifications=True`
- Appointment confirmation email + SMS on booking
- Doctor rejection email with reason

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.2 |
| Database | PostgreSQL 16 |
| Cache / Channel Layer | Redis 7 |
| WebSocket | Django Channels 4 + Daphne |
| Async Tasks | Celery + django-celery-beat |
| Frontend | Tailwind CSS (CDN) + HTMX + Alpine.js |
| PDF Generation | ReportLab |
| Payments | Stripe |
| Video | Daily.co |
| SMS | Twilio |
| Container | Docker + Docker Compose |

---

## Project Structure

```
MedConsult/
├── apps/
│   ├── accounts/        # User auth, profiles, tokens, notifications
│   ├── scheduling/      # Availability, slots, appointments, reviews, symptoms,
│   │                    # prescriptions, health records, referrals, waitlist, time-off
│   ├── dashboard/       # Role-based home pages
│   ├── adminpanel/      # Admin dashboard and management
│   ├── payments/        # Stripe payments and refunds
│   ├── messaging/       # In-app chat (WebSocket)
│   ├── consultations/   # Video rooms (Daily.co)
│   └── support/         # Help, FAQ, contact
├── config/
│   ├── settings/
│   │   ├── base.py      # Shared settings (includes CELERY_BEAT_SCHEDULE)
│   │   ├── dev.py       # Development
│   │   └── prod.py      # Production
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
├── docker-compose.yml
├── init.sh              # Automated setup script
├── info.txt             # Full project context and future work (for Claude sessions)
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
└── templates/
```

---

## Quick Start

### Option 1 — Automated (recommended)

```bash
./init.sh
```

This starts Docker services, creates a virtual environment, installs dependencies, runs migrations, and seeds the admin account.

Then:

```bash
source venv/bin/activate
python manage.py runserver --settings=config.settings.dev
```

### Option 2 — Manual

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

---

## URL Reference

```
Public
/                                         Landing page
/auth/login/                              Login (email or username)
/auth/signup/                             Role selection
/auth/signup/patient/<step>/              Patient signup wizard (5 steps)
/auth/signup/doctor/<step>/               Doctor signup wizard (6 steps)
/support/help/                            Help center
/support/faq/                             FAQ
/support/contact/                         Contact

Authenticated (all roles)
/app/                                     Role-based dashboard redirect
/auth/profile/                            Profile (edit, upload image, languages)
/auth/settings/                           Account settings (theme, notifications)
/auth/notifications/                      Full notification history

Patient — /patient/
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
  symptoms/body-parts/                    Symptom selector — body parts (HTMX)
  symptoms/body-parts/<id>/conditions/    Conditions for a body part (HTMX)
  symptoms/list/                          Symptom list (HTMX)

Doctor — /doctor/
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

Admin — /internal/
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
  audit/                                  Audit logs

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
python manage.py test --settings=config.settings.dev
python manage.py test apps.scheduling --settings=config.settings.dev

# Django shell
python manage.py shell --settings=config.settings.dev

# System check
python manage.py check --settings=config.settings.dev
```

### Docker

```bash
docker-compose up -d
docker-compose down
docker-compose logs postgres
docker-compose exec postgres psql -U medconsult_user -d medconsult
docker-compose exec redis redis-cli
```

---

## Architecture

### Services / Selectors Pattern

- **`services.py`** — all write operations (create, update, delete), wrapped in `@transaction.atomic`
- **`selectors.py`** — all read operations (queries, filters)
- **`views.py`** — thin HTTP handlers; call services/selectors, return responses

### Real-Time Updates

- `ws/doctor/<id>/calendar/` — doctor's weekly calendar (Django Channels)
- `ws/patient/doctor/<id>/slots/` — patient booking view (Django Channels)
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
| `extend_slots_for_all_doctors` | Daily at 02:00 |

### Migration State

| App | Latest Migration |
|-----|-----------------|
| accounts | 0008_doctorprofile_languages |
| scheduling | 0014_availabilityexception |
| adminpanel | 0002_healthrecordaccesslog_extend_actiontypes |
| payments | (initial) |
| messaging | 0004_conversation_delete_flags |
| consultations | (initial) |
