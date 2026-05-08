# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MedConsult is a Django 4.2 LTS telehealth platform connecting patients with verified doctors through a slot-based appointment system. It uses PostgreSQL 16, Redis 7, Django Channels for WebSocket support, Celery for async tasks, and Tailwind CSS (CDN) with dark mode support.

## Completed Work (Session Log)

### P0 — Security & HIPAA (all done)
- PHI encrypted at rest: `medical_license_number`, `account_number`, `routing_number` (DoctorProfile), `diagnosis`, `medications`, `instructions`, `notes` (Prescription) — `django-cryptography`
- 2FA for doctors + all org staff: `django-two-factor-auth` + `EnforceTwoFactorMiddleware` in `apps/accounts/middleware.py` (patients may skip; all staff roles require TOTP)
- Email verification enforced at login: `apps/accounts/views.py` login_view blocks unverified users
- `SECRET_KEY` guard: `config/settings/prod.py` raises `ImproperlyConfigured` if key missing or starts with `django-insecure-`
- `HealthRecordAccessLog` wired: `apps/scheduling/views.py` logs on all PHI reads/shares
- Patient data export: `GET /patient/export/` — JSON with profile, appointments, health records, prescriptions
- Baseline test suite: `pytest-django` + `pytest-cov`, 40% coverage gate in `pytest.ini` and CI
- Rate limiting: booking `10/h/user`, messaging `60/m/user`, DRF throttle `30/m anon` + `120/m user`
- Structured logging + Sentry: `LOGGING` dict in `base.py`; Sentry init when `SENTRY_DSN` set

### P1 — Functional Gaps (done items)
- Real contact form + FAQ: `apps/support/models.py` (FAQ, ContactMessage), Celery email on submit, 8 seeded FAQs
- Daily.co fallback: `apps/consultations/services.py` raises `ImproperlyConfigured` in prod if `DAILY_API_KEY` missing
- Message attachments: file input in `chat.html`, `send_message_view` + WebSocket consumer handle uploads, 10 MB max
- "Join Call" in chat: button shown when active VideoRoom exists for the appointment
- Group consultation filter: checkbox in doctor search sidebar (`?group_only=1`)
- Welcome email: `send_welcome_email_task` called from `verify_email_token` after confirmation
- Doctor API auth: `DoctorListAPIView` + `DoctorSlotsAPIView` require `IsAuthenticated`

### Living Knowledge Graph (done)
- `apps/knowledge_graph/` — GraphSnapshot model, graph_builder.py, Celery task, Django signals (debounced 10s), git post-commit hook
- Cytoscape.js UI at `/internal/knowledge-graph/`; REST JSON at `/api/v1/knowledge-graph/` (IsAdmin, 60s Redis cache)
- 147 nodes, 136 edges in current snapshot; `--quick` mode for git hook (12 nodes, git + stats only)
- Navbar: chain-link icon + "Graph" text link in admin desktop nav; admin sidebar link

### 2FA Settings UI (done)
- `settings_view` passes `two_fa_enabled`, `backup_codes_remaining`, `two_fa_setup_url`, `two_fa_backup_url`, `two_fa_disable_url` to template
- `regenerate_backup_codes` POST view at `/auth/settings/regenerate-backup-codes/` — deletes old StaticDevice, creates 10 fresh StaticTokens
- Settings page shows: enabled/disabled badge, "Set Up 2FA" or "Re-configure" button, backup code count, View/Regenerate/Disable controls
- Doctor/admin Disable row shows amber "Required for your role" warning

### Encryption data migration fix (done)
- Encrypted fields (`medical_license_number`, `account_number`, `routing_number`, prescription fields) previously NOT NULL — pre-encryption plaintext rows caused `BadSignature` on every page that touched DoctorProfile or Prescription
- Fix: added `null=True, blank=True` to all encrypted fields + data migrations `0014_clear_plaintext_encrypted_fields` and `0017_clear_plaintext_prescription_fields` that NULL out any rows whose bytes don't start with Fernet prefix `gAAAAA`
- Template fix: `settings.html` had wrong URL name `patient_export_data` → corrected to `patient:patient_data_export`

### Dev tooling
- `dev_gui.py`: Docker healthcheck fixed (`-d medconsult`), SQL tab layout fixed (sash, rowheight, column auto-sizing), `run_migrations` TCP-probes port 5433 before running
- `dev_gui.py`: **Page Health tab** — "Run All Tests" button runs Django test client against all 35 pages as admin/doctor/patient (2FA middleware bypassed for test), color-codes green=200 / yellow=warn / red=500, shows error count summary

### Frontend Redesign (in progress)
- Landing page, login page, signup role-select page redesigned with animations + new color palette
- Public navbar updated to match: `bg-blue-50/90 backdrop-blur-sm border-b border-blue-100/60`
- Admin layout dark mode fixed: outer wrapper + header + main + footer all have `dark:` variants
- **Signup wizard redesigned**: animated gradient background + frosted glass card in `signup_wizard.html`; all wizard partials (`_progress.html`, `_form_field.html`, `_camera_mic_test.html`) updated with full dark mode; `INPUT_CLASS`/`CHECKBOX_CLASS`/`FILE_INPUT_CLASS` in `forms.py` updated to include `dark:` variants
- **Help page rebuilt**: was missing all dark mode (`bg-white` everywhere); now has blue/emerald icon badges per section, hover-lift quick-link cards to FAQ and Contact
- **FAQ page rebuilt**: accordion interaction with animated chevron (`toggleFaq` JS), dark mode throughout
- **Privacy Policy** created: `apps/support/templates/support/privacy_policy.html` — 8 sections covering HIPAA compliance (AES-256/Fernet encryption, TLS, audit logs, §164.308), data collection, data sharing (Stripe/Daily.co/Twilio), patient rights, retention, and contact
- **Terms of Service** created: `apps/support/templates/support/terms_of_service.html` — 13 sections covering eligibility, payment/cancellation/refund policy, prohibited conduct, liability limits, Delaware governing law + JAMS arbitration
- Footer links updated: `templates/partials/footer.html` `href="#"` stubs replaced with `{% url 'support:privacy_policy' %}` and `{% url 'support:terms_of_service' %}`
- Chrome DevTools `/.well-known/` 404 warning suppressed via `CallbackFilter` in `config/settings/base.py` `LOGGING`
- Remaining pages will be redesigned one by one — always follow the design system below

### Pages Redesigned

| Template | Notes |
|----------|-------|
| `apps/accounts/templates/accounts/landing.html` | Hero + stats + features + CTA |
| `apps/accounts/templates/accounts/login.html` | Split layout, password toggle, staggered form |
| `apps/accounts/templates/accounts/signup_role_select.html` | Split layout, patient/doctor cards |
| `apps/accounts/templates/accounts/signup_wizard.html` + partials | Animated gradient, frosted glass card, full dark mode |
| `templates/layouts/public.html` | Blue-50 glass navbar |
| `templates/layouts/admin.html` | Dark mode variants added to wrapper/header/footer |
| `apps/support/templates/support/help.html` | Dark mode fixed, icon badges, hover cards |
| `apps/support/templates/support/faq.html` | Accordion + dark mode |
| `apps/support/templates/support/privacy_policy.html` | New HIPAA-aware privacy policy |
| `apps/support/templates/support/terms_of_service.html` | New telehealth terms of service |
| `apps/accounts/templates/accounts/forgot_password.html` | Split layout, animated lock icon, floating security cards |
| `apps/accounts/templates/accounts/reset_password.html` | Split layout, shield icon, password strength meter, show/hide toggles, real-time match indicator |

### P2 Security (done this session)
- **Argon2 password hasher**: `argon2-cffi==23.1.0` in requirements; `Argon2PasswordHasher` first in `PASSWORD_HASHERS`; PBKDF2 kept as fallback for existing hashes
- **Session hardening**: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`; `SESSION_COOKIE_AGE` reduced 86400 → 1800 (30 min); `SESSION_SAVE_EVERY_REQUEST=True`
- **`.env.example`**: added `SENTRY_TRACES_RATE`, `DJANGO_LOG_LEVEL`
- **Admin refund button**: amber "Refund" button in appointments table partial → inline modal → posts to `/internal/appointments/<id>/refund/`

### Confirmed Bugs (discovered, not yet fixed)

| Bug | Description | Files |
|-----|-------------|-------|
| B1 | `Appointment.slot` is `OneToOneField` — group booking capacity > 1 impossible | `apps/scheduling/models.py` |
| B2 | No booking/payment state machine — ghost appointments on Stripe abandon | `apps/payments/models.py`, `apps/scheduling/services.py` |
| B3 | Patient data export serializes wrong field paths | `apps/accounts/services.py` export logic |
| B4 | "Join Call" URL in chat template hits wrong namespace | `apps/messaging/templates/messaging/chat.html` |
| B5 | Admin decorator redirects to possibly non-existent `accounts:login` namespace | `apps/accounts/urls.py` |
| B6 | 2FA policy: docs say doctors/admins required but session flag allows bypass | `apps/accounts/middleware.py` |
| B7 | CI declares `pytest` but never runs it; coverage gate not enforced | `.github/workflows/django-ci.yml` |
| B8 | No `select_for_update()` on slot booking — race condition on concurrent booking | `apps/scheduling/services.py` |

---

## Frontend Design System

**This section is the single source of truth for all page redesigns. Read it before touching any template.**

### Core Rules

1. **Animations live in each template's inline `<style>` block** — never in `custom.css` or `base.html`. This keeps every page self-contained.
2. **Dark mode = Tailwind `dark:` variants only** — never CSS custom properties (`var(--color)`) or global `.dark .bg-white` overrides in `custom.css`. Those break button styles.
3. **Match the palette exactly** — don't introduce new colors. If in doubt, use the blue/indigo/slate family documented below.
4. **Auth pages bypass `layouts/public.html`** — extend `base.html` directly and override `{% block body %}` for full-screen split layouts.
5. **Never redesign admin pages** (`layouts/admin.html`) or authenticated app pages (`layouts/app.html`) unless the user explicitly asks.

### Color Palette

| Role | Value / Class |
|------|---------------|
| Landing hero gradient (light) | `linear-gradient(135deg, #eff6ff 0%, #eef2ff 50%, #faf5ff 100%)` — class `.hero-gradient` |
| Landing hero gradient (dark) | `linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)` — `.dark .hero-gradient` |
| Auth split left panel | `linear-gradient(145deg, #1e3a8a 0%, #312e81 45%, #1e1b4b 100%)` — class `.hero-panel` (always dark, ignores theme) |
| Public navbar | `bg-blue-50/90 dark:bg-gray-950/90 backdrop-blur-sm border-b border-blue-100/60 dark:border-gray-800` |
| Primary button | `bg-blue-600 hover:bg-blue-700 text-white` |
| Doctor / success accent | `bg-emerald-500`, `text-emerald-600 dark:text-emerald-400` |
| Glass card (on dark panel) | `bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl` |
| Form input | `.input-field` — defined inline per template; `border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700` with blue focus ring |
| Page bg (authenticated) | `bg-gray-50 dark:bg-gray-900` |
| Card surface | `bg-white dark:bg-gray-800` |

### Animation Keyframes (copy exactly into each template's `<style>` block)

```css
@keyframes fadeUp    { from { opacity:0; transform:translateY(24px); } to { opacity:1; transform:translateY(0); } }
@keyframes fadeIn    { from { opacity:0; } to { opacity:1; } }
@keyframes floatY    { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-12px); } }
@keyframes floatSlow { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-8px); } }
@keyframes gradShift { 0%,100% { background-position:0% 50%; } 50% { background-position:100% 50%; } }
@keyframes blobPulse { 0%,100% { transform:scale(1) translate(0,0); } 33% { transform:scale(1.05) translate(8px,-8px); } 66% { transform:scale(.96) translate(-6px,6px); } }

.animate-fade-up    { animation: fadeUp .65s cubic-bezier(.16,1,.3,1) both; }
.animate-float      { animation: floatY 3.8s ease-in-out infinite; }
.animate-float-slow { animation: floatSlow 5.5s ease-in-out infinite; }
/* delay utilities: .delay-50 through .delay-600 in 50ms steps */
.delay-50  { animation-delay:.05s; } .delay-100 { animation-delay:.1s; }
.delay-150 { animation-delay:.15s; } .delay-200 { animation-delay:.2s; }
.delay-300 { animation-delay:.3s;  } .delay-400 { animation-delay:.4s; }
.delay-500 { animation-delay:.5s;  } .delay-600 { animation-delay:.6s; }
```

Stagger rule: first visible element uses `.delay-50`, next `.delay-100`, next `.delay-150`, etc. Max cascade ~6 items.

### Layout Patterns

**Auth pages (login, forgot-password, reset-password, signup steps)**
- `{% extends "base.html" %}` + `{% block body %}` override
- `<div class="min-h-screen flex">` outer wrapper
- Left `hidden lg:flex lg:w-[48%] hero-panel`: logo + headline + floating glass cards + trust stats
- Right `flex-1 bg-white dark:bg-gray-900`: form with staggered `.animate-fade-up` entries
- Background decorative blobs: `border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; filter: blur(52px); animation: blobPulse 9s`
- Floating cards: `animate-float` / `animate-float-slow` with `animation-delay` offsets of `0s`, `1.2s`, `2.4s`

**Landing page** — extends `layouts/public.html`, full-width sections with `.hero-gradient` hero.

### Django Template Filter Warning

**`|split` is not a built-in Django filter.** Never use `"string"|split:" "` in templates — it throws `TemplateSyntaxError`. Hardcode repeated elements instead.

---

## Development Commands

```bash
# Start services (PostgreSQL + Redis)
docker-compose up -d

# Run development server (standard)
python manage.py runserver --settings=config.settings.dev

# Run development server with WebSocket support (Daphne)
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Run Celery worker (for async tasks like emails)
celery -A config worker -l info

# Run Celery Beat scheduler (periodic tasks: reminders, slot extension, completion marking)
celery -A config beat -l info

# Local dev GUI (Tkinter) — manages Docker, server, worker, beat, migrations, user accounts
python dev_gui.py

# Run all tests
python manage.py test --settings=config.settings.dev

# Run tests for specific app
python manage.py test apps.scheduling --settings=config.settings.dev

# Database migrations
python manage.py makemigrations --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev

# Check for missing migrations (used in CI)
python manage.py makemigrations --check --dry-run --settings=config.settings.dev

# Knowledge graph
python manage.py export_knowledge_graph --settings=config.settings.dev         # full rebuild → knowledge_graph.json
python manage.py export_knowledge_graph --quick --settings=config.settings.dev # git/stats nodes only (used by git hook)
```

## Multi-Tenancy Architecture

**Status: Plans written, implementation ready.**  
Full spec: `docs/superpowers/specs/2026-05-07-multi-tenancy-design.md`  
Plan 1 (data + permissions + query scoping): `docs/superpowers/plans/2026-05-07-multi-tenancy-foundation.md`  
Plan 2 (UI layer — signup, dashboards, invites, switcher): `docs/superpowers/plans/2026-05-08-multi-tenancy-ui.md`

MedConsult is a multi-tenant hospital SaaS. Each hospital/clinic is an `Organization`. Staff belong to orgs via `OrganizationMembership`. Patients are platform-wide.

### Key models (to be added in migrations 0016–0022)

- **`Organization`** — hospital, clinic, private_practice, urgent_care, mental_health, or platform. Has status: pending → active / needs_info / rejected / suspended.
- **`OrganizationMembership`** — links a user to an org with a role. One record per user/org. Deactivated, never deleted.
- **`OrganizationInvite`** — token-based invite (hash stored, raw token emailed). 7-day expiry. Lifecycle: pending → accepted / expired / revoked.

### Two default orgs (seeded by data migration)

| Org | Type | Purpose |
|-----|------|---------|
| MedConsult Platform | platform | platform_owner + platform_admin memberships |
| MedConsult Demo Clinic | clinic | existing test doctors + their clinical data |

### Tenant scoping rules

- **Hospital staff** — all queries scoped to `organization`
- **Doctors** — scoped to their one active org membership
- **Patients** — scoped by `patient=request.user`, never by org membership
- **Platform staff** — unscoped access (explicit `allow_unscoped=True` flag required)
- **`organization=None` fails closed** — returns `queryset.none()` unless platform access is proven

### Permission file locations

```
apps/accounts/permissions.py      global + org membership checks
apps/scheduling/permissions.py    appointment, slot, prescription
apps/payments/permissions.py      payment, refund
apps/messaging/permissions.py     conversation, message
apps/adminpanel/permissions.py    audit log, org management
apps/accounts/org_context.py      OrgContext dataclass + get_selected_organization()
```

### Hospital onboarding flow

1. Hospital owner self-registers at `/org/register/`
2. Org created with `status='pending'`
3. Platform owner reviews + approves at `/internal/organizations/`
4. Hospital owner can then invite doctors and staff via `/org/<slug>/staff/invite/`
5. Invitees accept via `/org/invite/<token>/`

## Architecture

### Services/Selectors Pattern

Business logic is separated from views using a clean architecture approach:

- **Services** (`services.py`): Write operations (create, update, delete). All database mutations go here.
- **Selectors** (`selectors.py`): Read operations (queries, filters). Complex queries and data retrieval go here.

Views are thin controllers that call services/selectors and handle HTTP concerns.

### Django Apps (Domain Isolation)

| App | Purpose | Key Models |
|-----|---------|------------|
| `accounts` | Authentication, user profiles, roles | User, PatientProfile, DoctorProfile, EmailVerificationToken, PasswordResetToken |
| `scheduling` | Appointments, availability, slots, reviews | AvailabilityWindow, AvailabilityWindowTypeConfig, Slot, Appointment, AppointmentTypeConfig, SlotChangeLog, Review, BodyPart, Condition, SymptomCategory, Symptom |
| `dashboard` | Role-based home pages | None (views only) |
| `adminpanel` | Admin dashboard, verification, analytics, management | AdminActivityLog |
| `payments` | Payment processing (Stripe) | Payment, Refund |
| `messaging` | In-app chat/messaging | Conversation, Message |
| `consultations` | Video consultations (Daily.co) | VideoRoom |
| `support` | Help center, FAQ, contact | FAQ, ContactMessage |
| `api` | REST API with JWT auth | None (views/serializers only) |
| `knowledge_graph` | Living project knowledge graph | GraphSnapshot |
| `organizations` | Hospital signup, org dashboards, staff invites, org switcher | (views/forms/services only — models live in `accounts`) |

### User Roles

MedConsult is a **multi-tenant hospital SaaS**. Roles operate at two levels:

**`User.role` — global account type (answers: what kind of account is this?)**

| Value | Who |
|-------|-----|
| `platform_owner` | You — full platform control (migrated from `admin`) |
| `platform_admin` | Future MedConsult internal staff |
| `doctor` | Any verified provider |
| `patient` | Any patient (platform-wide, not org-scoped) |
| `org_user` | Any hospital staff (owner, admin, scheduler, etc.) |

**`OrganizationMembership.role` — org-specific role (answers: what can they do inside an org?)**

`hospital_owner`, `hospital_admin`, `doctor`, `scheduler`, `billing_staff`, `compliance_officer`, `clinical_staff`

Platform roles (`platform_owner`, `platform_admin`) are also valid membership roles but only inside the `org_type='platform'` organization.

**Multi-tenancy spec:** `docs/superpowers/specs/2026-05-07-multi-tenancy-design.md`

### Default Credentials

**Platform Owner (you):**
- Username: `admin`
- Email: `admin@medconsult.com`
- Password: `admin123`
- Role after migration: `platform_owner`, membership in *MedConsult Platform* org

**Test Doctor:**
- Username: `testdoctor`
- Email: `doctor@test.com`
- Password: `testpass123`
- Membership: *MedConsult Demo Clinic* org

**Test Patient:**
- Username: `testpatient`
- Email: `patient@test.com`
- Password: `testpass123`
- No org membership (patients are platform-wide)

### Authentication Flow

- **Platform owner creation**: `python manage.py createsuperuser` with username, email, password
- **Hospital signup**: Self-service at `/org/register/` → pending approval by platform_owner
- **Login**: Single form accepting username OR email + password
- **Patient Signup**: 5-step wizard (Account → Personal → Health → Insurance → Terms)
- **Doctor Signup**: 6-step wizard (Account → Personal → Credentials → Bank → ID Verification → Terms)
- **Staff onboarding**: Hospital owner/admin sends invite → staff accepts via `/invite/<token>/`

Signup wizards include:
- Camera/microphone testing for telehealth readiness
- Gender selection with "Other" text input option
- Document uploads (medical license, government ID)
- HIPAA compliance acknowledgment (doctors)

### Profile Images

Users can upload profile images (PNG, JPG, JPEG, max 5MB):
- Upload/remove via profile page (`/auth/profile/`)
- Displayed in navbar, doctor cards, patient/doctor dashboards
- Stored in `media/profile_images/`
- Helper methods: `user.get_profile_image_url()`, `user.has_profile_image()`

### Appointment Workflow

1. Doctor creates `AvailabilityWindow` via self-service UI with multi-type support (e.g., "Monday 9-5, Video+Chat, individual pricing")
2. System generates `Slot` objects from windows (with buffer times and separate slots per appointment type)
3. Doctor can create manual/urgent slots, block/unblock individual slots, edit availability windows
4. Patient views available slots with real-time updates (HTMX polling + WebSocket)
5. Patient books a `Slot` → creates `Appointment` (sees price and can enter reason for visit)
6. Slot marked as booked, `SlotChangeLog` created, WebSocket broadcasts update to doctor calendar
7. After appointment completion, patient can submit a review (1-5 stars + comment)

### Doctor Reviews

Patients can rate and review doctors after completed appointments:
- **Review model**: Links to Appointment, stores rating (1-5) and optional comment
- **Submit review**: Available on patient appointments list for completed appointments
- **Doctor detail page**: Shows average rating, review count, and individual reviews
- **DoctorProfile properties**: `average_rating`, `review_count` for quick access

### Multi-Type Availability Pricing

Each `AvailabilityWindow` can have multiple appointment types with individual pricing via `AvailabilityWindowTypeConfig`:
- Video consultation: $X
- Chat consultation: $Y
- Phone consultation: $Z

Separate slots are generated for each enabled type, allowing independent booking and pricing.

### Dark Mode

The platform supports light/dark/auto theme modes:
- User preference stored in `User.theme_preference` field
- Toggle available in settings page (`/auth/settings/`)
- JavaScript in `theme_switcher.js` handles instant switching and localStorage sync
- All templates use Tailwind's `dark:` variant classes

### Admin Panel

The admin panel (`/internal/`) provides comprehensive platform management:

**Dashboard** (`/internal/`):
- Real-time metrics (users, appointments, completion rates)
- Chart.js visualizations (user growth, appointment distribution)
- Activity feeds (pending verifications, recent appointments, admin actions)

**User Management** (`/internal/users/`):
- Search/filter by role, status, keywords
- Activate/deactivate users with audit logging
- User detail modals with profile and appointment history
- CSV export functionality
- Quick "Manage" links to doctor/patient management pages

**Doctor Management** (`/internal/doctors/`):
- Doctor statistics (slots, appointments, revenue)
- Document viewer for license and ID verification
- Enhanced verification queue with rejection reasons

**Doctor Slot Management** (`/internal/doctors/<id>/manage/`):
- Visual weekly calendar with all doctor slots
- Create new slots (date, time, type, urgent flag)
- Block/unblock individual slots
- Delete unbooked slots
- View availability windows and appointment stats

**Patient Management** (`/internal/patients/<id>/manage/`):
- Patient profile and statistics
- Full appointment history with doctor info
- Cancel appointments on behalf of patients
- Activate/deactivate patient accounts

**Appointments** (`/internal/appointments/`):
- Filter by status, type, search terms
- CSV export functionality

**Financial Overview** (`/internal/financial/`):
- Revenue tracking by doctor
- Appointment type usage statistics
- Pricing overview across doctors

**Audit Logs** (`/internal/audit/`):
- Admin action logs (verifications, exports, user changes)
- Slot change logs (blocks, cancellations)

All admin actions are logged to `AdminActivityLog` for compliance.

### HTMX Integration

The platform uses HTMX for dynamic updates without full page reloads:
- **Doctor availability calendar**: Partial updates for slot management, arrow key navigation
- **Patient slot view**: 5-second polling with smart change detection (only notifies on actual changes)
- **Admin panel**: HTMX-powered filtering and modal interactions
- **Form submissions**: HTMX-powered modals for creating/editing windows and slots
- Base template includes HTMX CDN and CSRF token header configuration

### WebSocket Support (Django Channels)

Real-time updates via WebSocket for instant synchronization:
- **Configuration**: `config/asgi.py` with ProtocolTypeRouter combining both routing modules
- **Doctor Calendar Consumer** (`ws/doctor/<id>/calendar/`): Receives slot/window updates — `apps/scheduling/consumers.py`
- **Patient Slots Consumer** (`ws/patient/doctor/<id>/slots/`): Receives availability changes — `apps/scheduling/consumers.py`
- **Chat Consumer** (`ws/chat/<conversation_id>/`): Real-time messaging with typing indicators and read receipts — `apps/messaging/consumers.py`
- **Broadcast helpers**: `sync_broadcast_to_doctor_calendar()`, `sync_broadcast_to_patient_slots()`
- **Fallback**: HTMX polling works if WebSocket connection fails

### Template System (4-Layer Inheritance)

```
base.html                    # Root: Tailwind CDN, meta, scripts
└── layouts/public.html      # Public pages (non-authenticated)
└── layouts/app.html         # Authenticated pages with navbar
└── layouts/admin.html       # Admin panel with dark sidebar
    └── app-specific/*.html  # Page content
        └── components/*.html # Reusable UI pieces
```

### Settings Configuration

Environment-based settings in `config/settings/`:
- `base.py` - Common settings for all environments
- `dev.py` - Development (DEBUG=True, PostgreSQL, Redis)
- `prod.py` - Production (DEBUG=False, security headers, HTTPS)

Always specify settings: `--settings=config.settings.dev` or `--settings=config.settings.prod`

### URL Structure

- `/auth/*` - Authentication (login, signup, profile, password reset, switch-org)
- `/app/*` - Dashboard (role-based home)
- `/patient/*` - Patient appointment flows (includes HTMX slot updates, reviews)
- `/doctor/*` - Doctor availability management (calendar, windows, slots, types)
- `/org/*` - Organization management (register, dashboards, staff, settings, invite acceptance)
- `/internal/*` - Admin panel (dashboard, users, doctors, doctor/patient management, appointments, financial, audit, org review)
- `/payments/*` - Payment processing (checkout, history)
- `/messages/*` - In-app messaging
- `/consultation/*` - Video consultations
- `/support/*` - Help center

### Symptom/Injury Selector

Patient booking includes a structured symptom/injury selector:
- **BodyPart**: 20 body parts across 5 categories (head_neck, torso, organs, limbs, systems)
- **Condition**: 95 conditions linked to body parts (e.g., Migraine under Head & Brain)
- **SymptomCategory**: 10 symptom categories (Pain-Related, Respiratory, etc.)
- **Symptom**: 54 symptoms grouped by category

UI Flow:
1. Patient chooses: "Injury/Condition" or "Symptoms" tab
2. If Injury: Select body part → See conditions for that part → Multi-select
3. If Symptoms: Browse categorized list → Multi-select
4. Selected items appear as removable tags and auto-populate the reason field

Uses Alpine.js for reactive state management and HTMX for loading body parts/conditions/symptoms.

### Scheduling Models

Key models in `apps/scheduling/models.py`:

- **AvailabilityWindow**: Recurring time ranges with buffer times and appointment types
- **AvailabilityWindowTypeConfig**: Per-window pricing for each appointment type (video/chat/phone)
- **Slot**: Individual bookable time slots with status (available/booked/blocked/urgent), has `get_price()` method
- **Appointment**: Booked appointments linking patients to slots
- **AppointmentTypeConfig**: Per-doctor default pricing for video/chat/phone consultations
- **SlotChangeLog**: Tracks slot changes for real-time patient updates
- **Review**: Patient reviews for completed appointments (1-5 rating + comment)
- **BodyPart**: Body parts for injury/condition selection (20 parts across 5 categories)
- **Condition**: Medical conditions linked to body parts (95 conditions)
- **SymptomCategory**: Categories for grouping symptoms (10 categories)
- **Symptom**: Individual symptoms for selection (54 symptoms)

Appointment types: `video`, `chat`, `phone` with customizable duration and pricing per availability window.

Key files for WebSocket:
- `apps/scheduling/consumers.py`: WebSocket consumers (DoctorCalendarConsumer, PatientSlotsConsumer)
- `apps/scheduling/routing.py`: WebSocket URL patterns

### Celery Configuration

Async task processing for emails and background jobs:
- **Config**: `config/celery.py` with Redis broker
- **Run worker**: `celery -A config worker -l info`
- **Run Beat**: `celery -A config beat -l info`

**Account tasks** (`apps/accounts/tasks.py`, max_retries=3):
- `send_verification_email_task` — 24h verification link
- `send_password_reset_email_task` — 1h reset link

**Scheduling tasks** (`apps/scheduling/tasks.py`) — Beat schedule defined in `config/settings/base.py`:
- `schedule_appointment_reminders` — every 15 min (24h + 1h reminder windows)
- `extend_slots_for_all_doctors` — daily 02:00 UTC (extends slots 60 days out)
- `mark_completed_appointments` — every 5 min
- `mark_no_show_appointments` — every 10 min (30+ min past start → no_show)

### Admin Panel Models

Key models in `apps/adminpanel/models.py`:

- **AdminActivityLog**: Audit trail for admin actions (verifications, exports, user changes)

### REST API (`/api/v1/`)

JWT-authenticated REST API using DRF + `djangorestframework-simplejwt`. Custom permission classes in `apps/api/permissions.py`: `IsPatient`, `IsDoctor` (requires verified status), `IsAdmin`.

| Method | Endpoint | Auth |
|--------|----------|------|
| POST | `/api/v1/auth/token/` | None |
| POST | `/api/v1/auth/token/refresh/` | None |
| GET | `/api/v1/doctors/` | IsAuthenticated |
| GET | `/api/v1/doctors/<id>/slots/` | IsAuthenticated |
| POST | `/api/v1/slots/<id>/book/` | IsPatient |
| GET | `/api/v1/appointments/` | IsPatient |
| GET | `/api/v1/notifications/` | IsAuthenticated |
| POST | `/api/v1/notifications/<id>/read/` | IsAuthenticated |
| GET | `/api/v1/knowledge-graph/` | IsAdmin |

### External Integrations

- **Stripe** (`stripe` 7.x) — payments in `apps/payments/`
- **Daily.co** — video rooms in `apps/consultations/`; requires `DAILY_API_KEY` env var
- **Twilio** — SMS reminders in scheduling tasks; requires Twilio env vars
- **ReportLab** — PDF prescription generation in `apps/scheduling/`

### Context Processors

- `apps.accounts.context_processors.user_info`: User display info for navbar
- `apps.adminpanel.context_processors.admin_context`: Pending verification count for admin badge

---

## Knowledge Graph

A living network graph of the entire project state. Lives in `apps/knowledge_graph/`.

### File layout
```
apps/knowledge_graph/
├── models.py            # GraphSnapshot — stores latest JSON snapshot with timestamp
├── graph_builder.py     # Queries ORM + git log → builds nodes + edges dicts
├── signals.py           # post_save/post_delete handlers → debounced Celery rebuild (max 1/10s)
├── tasks.py             # rebuild_knowledge_graph Celery task (also on Beat: every 5 min)
├── views.py             # UI view (Cytoscape.js) + API view (JSON)
├── urls.py
└── management/commands/
    └── export_knowledge_graph.py  # --quick flag for git hook
templates/knowledge_graph/
└── graph.html           # Cytoscape.js force-directed graph UI
```

### Node types

| Type | Updated when | Key fields (no PHI) |
|------|-------------|---------------------|
| `project` | Any commit | git HEAD, branch, last commit message |
| `app` | Code change | app name, model count, view count |
| `user` | Created / deleted / role changed | ID, role, is_verified, joined date |
| `appointment` | Booked / cancelled / completed | status, type, datetime |
| `slot` | Created / blocked / booked | status, type, datetime, doctor ref |
| `conversation` | New chat | participant roles, message count |
| `payment` | Charged / refunded | status, amount |
| `system_health` | Celery every 5 min | pending verifications, active slots, queue depth |
| `git_commit` | post-commit hook | hash, message, files changed |

### API response shape (`/api/v1/knowledge-graph/`)
```json
{
  "metadata": { "git_head": "...", "generated_at": "...", "django_version": "5.2" },
  "summary":  { "patients": 42, "doctors": 8, "pending_verifications": 3, "active_slots": 145 },
  "recent_changes": [ { "hash": "...", "message": "...", "date": "..." } ],
  "app_structure": { "accounts": { "models": [...], "view_count": 15 }, ... },
  "nodes": [...],
  "edges": [...]
}
```

Requires `IsAdmin`. Redis-cached 60s. AI agents can consume this endpoint directly to get full project context without reading source files.

### Update pipeline
```
Django signal (User/Appointment/Slot save/delete)
    └──► debounce 10s
         └──► Celery task: rebuild_knowledge_graph
              └──► graph_builder.build_graph()
                   ├──► GraphSnapshot.objects.update_or_create()
                   ├──► Redis cache invalidate
                   └──► knowledge_graph.json overwritten

Celery Beat every 5 min ──► same task (catch-all)
git post-commit hook     ──► manage.py export_knowledge_graph --quick
```

### REST API endpoint
| Method | Endpoint | Auth |
|--------|----------|------|
| GET | `/api/v1/knowledge-graph/` | IsAdmin |

### URL structure
- `/internal/knowledge-graph/` — interactive Cytoscape.js UI (admin only)
- `/api/v1/knowledge-graph/` — machine-readable JSON (admin JWT)
