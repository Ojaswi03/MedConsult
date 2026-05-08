# MedConsult Multi-Tenancy Design Spec

**Date:** 2026-05-07  
**Status:** ✅ Complete — fully implemented as of 2026-05-08  
**Author:** Ojaswi Sinha  

---

## Overview

MedConsult transitions from a single-tenant telehealth marketplace to a **multi-tenant hospital SaaS platform with optional marketplace discovery later**.

Hospitals get isolated workspaces. Doctors belong to one hospital at a time. Patients are platform-wide and connect to hospitals through care relationships, not membership. You (platform_owner) approve each hospital before it goes live.

---

## Strategic Direction

```
Multi-tenant SaaS first. Marketplace discovery later.
```

Each hospital organization gets isolated:
- Staff (hospital_owner, hospital_admin, scheduler, billing_staff, compliance_officer, clinical_staff)
- Doctors (scoped to one org at a time in this sprint)
- Appointments, slots, payments, prescriptions, conversations, referrals, availability windows

Patients are **not** org-scoped. They are platform-wide accounts that connect to hospitals through booked appointments, record shares, and conversations.

---

## Role System

### `User.role` — global account type only

Answers: *what kind of account is this platform-wide?*

| Value | Who |
|-------|-----|
| `platform_owner` | You — full platform control |
| `platform_admin` | Future MedConsult internal staff |
| `doctor` | Any verified provider |
| `patient` | Any patient |
| `org_user` | Any hospital staff (owner, admin, scheduler, etc.) |

`User.role` is **not** a permission source for hospital actions. It is a global classification only.

`max_length` widened from 10 → 30.

### `OrganizationMembership.role` — org-specific role

Answers: *what can this user do inside this organization?*

| Value | Purpose |
|-------|---------|
| `platform_owner` | Valid only in platform org |
| `platform_admin` | Valid only in platform org |
| `hospital_owner` | CEO/director — manages the institution |
| `hospital_admin` | Operations/admin staff |
| `doctor` | Provider scoped to this org |
| `scheduler` | Receptionist/front desk |
| `billing_staff` | Payments, refunds, superbills — UI deferred |
| `compliance_officer` | Audit/privacy investigations — UI deferred |
| `clinical_staff` | Nurses, care coordinators — UI deferred |

**Rule enforced in permission helpers:**
- `platform_*` roles are only valid when `organization.org_type == 'platform'`
- `hospital_*` and clinical roles are only valid when `organization.org_type != 'platform'`

### Patients

Patients have no `OrganizationMembership`. They connect to hospitals through:
- `Appointment.patient` + `Appointment.organization`
- `HealthRecordShare`
- `Conversation`
- `Payment`

---

## Data Layer

### `Organization` model

```python
ORG_TYPES:  platform, hospital, clinic, private_practice, urgent_care, mental_health
STATUS:     pending, active, needs_info, rejected, suspended

fields:
  name (max 255), slug (unique), org_type, status
  address, phone, website, logo (ImageField)
  approved_by (FK User null), approved_at
  rejected_reason (TextField blank)
  created_by (FK User null), created_at, updated_at

indexes: slug, status
```

**Status meanings:**
- `pending` — submitted, awaiting platform review
- `active` — approved, fully operational
- `needs_info` — platform owner requested more information from org
- `rejected` — never approved (different from suspended)
- `suspended` — was active, then disabled

### `OrganizationMembership` model

```python
fields:
  user (FK User), organization (FK Organization)
  role (choices=ROLES)
  is_active (default True)
  invited_by (FK User null), invited_at, accepted_at
  deactivated_at (null), deactivated_by (FK User null)
  created_at, updated_at

constraints:
  UniqueConstraint(fields=['user', 'organization'],
                   name='unique_user_organization_membership')

indexes:
  [organization, role, is_active]
  [user, is_active]
```

One membership record per user per organization. Memberships are **deactivated, never deleted**. To re-add a user, reactivate and update their existing record.

### `OrganizationInvite` model

```python
fields:
  organization (FK), invited_by (FK User)
  email (EmailField, lowercased on save)
  role (choices=OrganizationMembership.ROLES)
  token_hash (CharField — hash stored, raw token emailed)
  status: pending, accepted, expired, revoked
  expires_at (7 days from creation)
  accepted_by (FK User null)
  revoked_by (FK User null), revoked_at
  created_at, updated_at

constraints:
  UniqueConstraint(
    fields=['organization', 'email'],
    condition=Q(status='pending'),
    name='unique_pending_invite_per_org_email'
  )
```

Raw token is never stored. Hash is stored. Email contains raw token. Acceptance hashes the submitted token and compares.

### Models receiving `organization` FK

Added as `null=True` initially, then `null=False` after backfill (see migration plan):

**Must be `null=False` after backfill:**
`Appointment`, `Slot`, `Payment`, `AvailabilityWindow`, `Prescription`, `Referral`, `Conversation`, `WaitlistEntry`, `VideoRoom`

`WaitlistEntry` and `VideoRoom` are org-facing operational objects — scoping them via relationship chains is fragile. Backfill from `slot.organization` / `appointment.organization` respectively, then make non-null.

**Stays `null=True` (nullable — reason noted):**
- `DoctorProfile` — null until doctor accepts an org invite
- `HealthRecordShare` — scoped from appointment relationship
- `Review` — scoped from appointment
- `Notification` — null for platform-wide / patient notifications
- `HealthRecordAccessLog` — null for patient self-access
- `AdminActivityLog` — null for platform-level actions

### `DoctorProfile.organization`

Temporary single-org FK. Will be replaced or supplemented by `ProviderOrganizationProfile` when multi-hospital doctor support is added. Set when doctor accepts an org invite.

### Model queryset helpers

Each tenant-scoped model gets a custom QuerySet:

```python
class AppointmentQuerySet(models.QuerySet):
    def for_org(self, organization):
        return self.filter(organization=organization)
    def for_patient(self, patient):
        return self.filter(patient=patient)
    def for_doctor(self, doctor):
        return self.filter(doctor=doctor)
```

### Migration plan (7 migrations)

```
Migration 1:  Expand User.role max_length 10 → 30.
              Add org_user, platform_admin, platform_owner to choices.
              Keep old 'admin' temporarily.

Migration 2:  Add Organization, OrganizationMembership, OrganizationInvite models.

Migration 3:  Data migration:
              - Create Organization(name="MedConsult Platform", org_type="platform", status="active")
              - Create Organization(name="MedConsult Demo Clinic", org_type="clinic", status="active")
              - admin user → User.role='platform_owner'
              - platform_owner/platform_admin → membership in MedConsult Platform
              - existing doctors → User.role stays 'doctor', membership in MedConsult Demo Clinic
              - patients → no membership created

Migration 4:  Add nullable organization FK to all tenant-scoped models listed above.

Migration 5:  Backfill organization on all above models:
              - Doctor-related records → MedConsult Demo Clinic
              - Platform/admin logs → MedConsult Platform where appropriate
              - Patient-owned records: HealthRecord stays patient-owned;
                shares get org from appointment/doctor relationship

Migration 6:  Alter organization to null=False on:
              Appointment, Slot, Payment, AvailabilityWindow, Prescription,
              Referral, Conversation

Migration 7:  Remove old 'admin' from User.role choices.
              Update any remaining 'admin' rows to 'platform_owner'.
```

---

## Permission Layer

### File structure

```
apps/accounts/permissions.py       global + org membership checks
apps/scheduling/permissions.py     appointment, slot, prescription checks
apps/payments/permissions.py       payment, refund checks
apps/messaging/permissions.py      conversation, message checks
apps/adminpanel/permissions.py     audit log, org management checks
```

Domain-split avoids circular imports and monster files.

### `OrgContext` dataclass — lives in `apps/accounts/org_context.py`

```python
@dataclass
class OrgContext:
    organization: Organization | None
    membership: OrganizationMembership | None
    is_platform_scope: bool = False
    source: str = "none"   # "url" | "session" | "single_membership" | "none"
```

`None` is not ambiguous. It means something specific depending on `source` and `is_platform_scope`.

`get_selected_organization(request)` lives in `apps/accounts/org_context.py`, **not** in `permissions.py`. Permission checks stay in `permissions.py`; request/org resolution stays in `org_context.py`. This avoids circular imports.

### `apps/accounts/permissions.py`

**Tier 1 — Global account checks**

Every helper guards against unauthenticated users:

```python
def is_platform_owner(user):
    return bool(user and user.is_authenticated and user.role == 'platform_owner')

def is_platform_staff(user):
    return bool(user and user.is_authenticated
                and user.role in ('platform_owner', 'platform_admin'))

def is_doctor(user):
    return bool(user and user.is_authenticated and user.role == 'doctor')

def is_patient(user):
    return bool(user and user.is_authenticated and user.role == 'patient')

def is_org_user(user):
    return bool(user and user.is_authenticated and user.role == 'org_user')
```

**Tier 2 — Org membership checks**

```python
def get_membership(user, organization) -> OrganizationMembership | None
def has_org_role(user, organization, allowed_roles) -> bool
def get_user_organizations(user) -> QuerySet[Organization]
def get_selected_organization(request) -> OrgContext
```

`get_selected_organization` priority:
1. URL kwarg `org_slug` — verified: user must have active membership or be platform staff
2. `session['active_organization_id']`
3. User's single active membership
4. Returns `OrgContext(organization=None, is_platform_scope=is_platform_staff(user))`

If URL `org_slug` is provided and user has no membership, raises `PermissionDenied` (not 404 — avoids org enumeration).

**Tier 3 — Action checks**

```python
# Organization management
def can_approve_organization(user)          → platform_owner/platform_admin only
def can_edit_organization_profile(user, org) → platform_staff OR hospital_owner/admin
def can_suspend_organization(user)          → platform_owner/platform_admin only
def can_manage_org_billing_settings(user, org) → platform_staff OR hospital_owner

# Staff management
def can_manage_staff(user, org)             → platform_staff OR hospital_owner/admin
def can_invite_staff(user, org)             → same as can_manage_staff
def get_invitable_roles(user, org) -> list  → enforces grant matrix (see below)

# Appointments (split — doctors do not manage all org appointments)
def can_manage_org_appointments(user, org)  → platform_staff, hospital_owner/admin, scheduler
def can_manage_own_appointment(user, appointment) → appointment.doctor.user == user

# Payments (split by sensitivity)
def can_view_org_payment_status(user, org)
    → hospital_owner, hospital_admin, scheduler, billing_staff
      (org-wide view — doctors excluded)

def can_view_own_appointment_payment(user, payment)
    → is_doctor(user) AND payment.appointment.doctor.user == user
      (doctors see paid/unpaid for their own appointments only)

def can_manage_payments(user, org)          → platform_staff, hospital_owner, billing_staff
def can_refund_payment(user, payment)       → platform_staff, hospital_owner, billing_staff
# compliance_officer → payments visible only through audit/compliance view
# clinical_staff     → no payment access

# PHI — object-level, never org-role alone
def can_access_patient_phi(user, patient, org)
    → is_doctor(user)
      AND has_org_role(user, org, ['doctor'])
      AND (active/completed appointment exists OR health record shared)

def can_view_health_record(user, record)
    → record.patient == user
      OR (
           is_doctor(user)
           AND has_org_role(user, org, ['doctor'])
           AND HealthRecordShare(record, shared_with_doctor=user, revoked_at=None) exists
         )
      OR (
           is_doctor(user)
           AND has_org_role(user, org, ['doctor'])
           AND active/completed Appointment(doctor__user=user, patient=record.patient) exists
         )
# Explicitly doctor-only — no other role reaches PHI via relationship chain

# Audit
def can_view_audit_logs(user, org)          → platform_staff OR hospital_owner/compliance_officer

# Break-glass — not implemented this sprint; returns False always
def can_break_glass_access_phi(user, record, reason) → False (stub)
```

### Invite grant matrix

```
platform_owner/platform_admin → any role
hospital_owner                → hospital_admin, doctor, scheduler, billing_staff,
                                 compliance_officer, clinical_staff
hospital_admin                → doctor, scheduler, billing_staff, clinical_staff
                                 (cannot grant hospital_owner or compliance_officer)
scheduler/doctor/etc.         → cannot invite anyone
```

`compliance_officer` restricted to `hospital_owner` grant only.

### 2FA requirement

Required for all staff roles — not just doctors:

```
doctor, platform_owner, platform_admin,
hospital_owner, hospital_admin, scheduler,
billing_staff, compliance_officer, clinical_staff
```

Patients: optional 2FA (current skip-flag behaviour preserved).

Updated in `EnforceTwoFactorMiddleware` — checks **any** active elevated membership, not the currently-selected org. 2FA enforcement must not depend on dashboard context:

```python
ELEVATED_MEMBERSHIP_ROLES = [
    'hospital_owner', 'hospital_admin', 'scheduler',
    'billing_staff', 'compliance_officer', 'clinical_staff', 'doctor',
]

role_requires_2fa = (
    user.role in ('platform_owner', 'platform_admin', 'doctor')
    or OrganizationMembership.objects.filter(
           user=user,
           is_active=True,
           role__in=ELEVATED_MEMBERSHIP_ROLES,
       ).exists()
)
```

This ensures a hospital_owner who hasn't selected an org yet is still blocked until they complete 2FA.

### `require_org_role` decorator

1. Resolve `OrgContext` from URL/session/membership
2. Verify user has active membership AND role is in `allowed_roles`, OR user is platform staff
3. Attach `request.organization` and `request.org_membership`
4. Return 403 if not allowed
5. Never trust `organization_id` from POST body — only from URL or session

### DRF permission classes (`apps/api/permissions.py`)

```python
IsPatient   → is_patient(user)
IsDoctor    → is_doctor(user) AND verified DoctorProfile exists
IsAdmin     → is_platform_staff(user)            # was role=='admin'
IsOrgAdmin  → has_org_role(hospital_owner, hospital_admin)
IsOrgMember → active membership in request.organization
IsOrgDoctor → is_doctor(user) AND verified profile AND org membership with role='doctor'
```

---

## Query Scoping Layer

### Core rule

```
No org-facing selector returns unscoped data unless platform access is explicitly proven.
organization=None returns queryset.none() for non-platform users.
```

### `scope_to_org` helper

```python
def scope_to_org(queryset, organization, user):
    if organization is None:
        if is_platform_staff(user):
            return queryset
        return queryset.none()   # fail closed
    return queryset.filter(organization=organization)
```

Never: `if organization is None: return queryset` without the platform check.

### View → Selector contract

Views resolve `OrgContext`, pass `organization` and `user` explicitly into selectors. Selectors never read from `request`.

```python
# View
org_ctx = get_selected_organization(request)
appointments = get_doctor_appointments(request.user, organization=org_ctx.organization)

# Selector
def get_doctor_appointments(user, organization):
    qs = Appointment.objects.filter(doctor__user=user)
    return scope_to_org(qs, organization, user)
```

### `get_object_or_404` pattern

```python
# Org-scoped objects
appointment = get_object_or_404(Appointment, id=appointment_id, organization=request.organization)

# Patient-owned objects
appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
```

### Service-level org validation

Services are the deadbolt. Views are the first lock. Critical write services validate org consistency:

```python
def book_slot(patient, slot, organization):
    if slot.organization_id != organization.id:
        raise PermissionDenied("Organization mismatch")

def create_prescription(doctor, appointment, organization):
    if appointment.organization_id != organization.id:
        raise PermissionDenied("Organization mismatch")
```

Services that validate org consistency:
`book_appointment`, `create_payment`, `refund_payment`, `create_prescription`,
`share_health_record`, `create_conversation`, `create_referral`,
`create_availability_window`, `create_slot`

### Organisation consistency helper

```python
def assert_same_org(*objects):
    org_ids = {obj.organization_id for obj in objects if obj is not None}
    if len(org_ids) > 1:
        raise ValidationError("Organization mismatch across related objects.")
```

### Selector changes by app

`apps/scheduling/selectors.py`
```
get_available_slots_for_doctor(doctor, organization)
get_doctor_appointments(user, organization)
get_doctor_availability_windows(doctor, organization)
get_all_availability_windows(organization)
get_appointment_by_id(id, organization)       ← prevents cross-org IDOR
get_patient_appointments(patient)             ← patient-scoped, no org filter
```

`apps/payments/selectors.py` (new)
```
get_payments_for_org(organization, user)
get_payment_for_appointment(appointment_id, organization)
get_refunds_for_org(organization, user)
```

`apps/messaging/selectors.py`
```
get_conversations(user, organization=None)
  → patient: filter by participant
  → org staff: filter by organization
```

`apps/adminpanel/selectors.py`
```
All selectors gain organization param.
platform_staff pass organization=None → unscoped via scope_to_org.
Hospital staff always pass organization.
Includes: CSV exports, Chart.js dashboard queries, financial overview,
          audit log search, doctor verification queue.
```

### WebSocket consumers

Consumers resolve org context before accepting connection:

```
Doctor calendar socket  → doctor must have active membership in org
Patient slot socket     → public doctor slot data; slot.organization verified
Chat socket             → user must be conversation participant;
                          staff user.organization must match conversation.organization
```

### Celery tasks

Tasks loop by organization instead of global queries:

```python
# Instead of:
Appointment.objects.filter(status='scheduled')

# Use:
for org in Organization.objects.filter(status='active'):
    appointments = Appointment.objects.filter(
        organization=org, status='scheduled'
    )
```

Affected tasks: appointment reminders, slot generation, mark completed/no-show,
payment reports, knowledge graph export (per-org view for hospital staff).

### Knowledge graph scoping

```
platform_staff → global graph
hospital_staff → org-scoped graph (their org's nodes only)
patients       → no access
```

---

## UI Layer

### New URLs

```
/org/register/                          hospital self-service signup
/org/<slug>/                            org dashboard (role-determined view)
/org/<slug>/settings/                   edit org profile
/org/<slug>/staff/                      staff list
/org/<slug>/staff/invite/               send invite
/org/<slug>/staff/<member_id>/          member detail / deactivate
/invite/<token>/                        accept org invite
/internal/organizations/                platform org list
/internal/organizations/<id>/           org detail + review checklist
/internal/organizations/<id>/approve/   approve org
/internal/organizations/<id>/reject/    reject org with reason
/internal/organizations/<id>/needs-info/ request more information
/internal/organizations/<id>/suspend/   suspend active org
/internal/organizations/<id>/reactivate/ reactivate suspended org
```

### Hospital self-service signup — `/org/register/`

Two steps. Public, no login required.

**Step 1 — Account:**  name, email, password
**Step 2 — Organization:** org name, type, address, phone, website, logo

On submit:
- `User` created with `role='org_user'` (email unverified)
- `Organization` created with `status='pending'`
- `OrganizationMembership` created with `role='hospital_owner'`
- Email verification sent to owner
- platform_owner receives email + in-app notification

Pending owner sees a holding page: *"Your organization is under review."*

### Platform owner — organization approval

`/internal/organizations/` — table with columns:
`Name | Type | Status | Owner | Doctors | Created | Actions`
Filter by status. Pending rows show amber badge.

`/internal/organizations/<id>/` — review checklist before any action:
```
☐ Organization name verified
☐ Website/domain checked
☐ Phone/address checked
☐ Owner email verified
☐ Business document reviewed (if uploaded)
   Notes field
```

Actions:
- **Approve** → `status='active'`, email to hospital_owner
- **Reject (with reason)** → `status='rejected'`, reason stored + emailed
- **Request more info** → `status='needs_info'`, message to hospital_owner
- **Suspend** → `status='suspended'` (active orgs only)
- **Reactivate** → `status='active'` (suspended orgs only)

`rejected ≠ suspended`. Do not flatten these.

### Hospital owner dashboard — `/org/<slug>/`

```
Stats:    Active Doctors | Today's Appointments | Pending Invites | Monthly Revenue
Sections:
  Staff management (invite, deactivate, role list, pending invite lifecycle)
  Org profile settings
  Doctor verification queue (own org's pending doctors)
  Basic appointment overview
  Analytics placeholder card (built next sprint)
```

### Hospital admin dashboard — `/org/<slug>/`

Same URL, scoped-down view:

```
Stats:    Today's Appointments | Active Doctors | Pending Staff
Sections:
  Appointment management (all org appointments, filter by doctor/date/status)
  Staff list (view only for hospital_owner; manage roles below hospital_owner)
  Send invites (role dropdown scoped to grant matrix)
  Doctor list for org
```

hospital_admin **cannot**: approve/suspend org, edit billing settings, invite hospital_owner or compliance_officer.

### Scheduler dashboard — `/org/<slug>/`

Most constrained view:

```
Sections:
  Today's schedule (all org doctors, by time)
  Book appointment on behalf of patient:
    - search existing patient by email/phone
    - create patient shell account if none (sends claim-account email)
    - record booked_by and source (phone/walk-in/admin call)
    - payment: patient-pay link or front-desk payment status
  Reschedule / cancel appointment
  Doctor availability overview (read-only)
  Patient contact info only (name, phone, email — no clinical data)
```

Scheduler cannot impersonate patients. They assist, not become.

### Doctor dashboard (org-aware)

Existing doctor home updated:
```
Org badge in navbar: "Dr. Smith — City General Hospital"
Org selection logic:
  - 1 active membership → auto-select silently
  - 0 memberships → show "No organization assigned. Waiting for invite."
  - >1 memberships → require org switcher (deferred; shown as placeholder)
Availability, slots, appointments: all scoped to selected org
```

### Staff invite lifecycle

Invite list shows per invite:
`Email | Role | Status | Invited By | Sent | Expires | Actions`

Actions: **Resend** (resets expiry), **Revoke** (status='revoked')

Badges: pending (amber), accepted (green), expired (gray), revoked (red)

### Invite acceptance — `/invite/<token>/`

1. Hash submitted token, look up by hash. Verify `status='pending'` and `expires_at > now`.
2. If email has no account → inline mini-registration (name + password, email pre-filled)
3. If email has account → login prompt → redirect back here
4. **Email lock:** verify `request.user.email == invite.email` (case-insensitive). If mismatch → block with clear message: "This invite was sent to a different email address."
5. On accept → wrapped in `select_for_update()` transaction: re-verify invite still `pending`, create `OrganizationMembership`, set invite `status='accepted'`. Prevents double-acceptance race.

**Post-acceptance routing by role:**

```
hospital_owner   → /org/<slug>/
hospital_admin   → /org/<slug>/
doctor           → /auth/profile/ (complete DoctorProfile if missing)
                   then /org/<slug>/
scheduler        → /org/<slug>/
billing_staff    → /org/<slug>/ with "dashboard coming soon" card
compliance_officer → /org/<slug>/ with "dashboard coming soon" card
clinical_staff   → /org/<slug>/ with "dashboard coming soon" card
```

No role lands on a broken half-UI.

### Organization switcher

Platform staff only in this sprint (stored in `session['active_organization_id']`):

```
Viewing as: [Org Name ▾]  → all active orgs + "Platform View"
```

Hospital staff switcher hidden during single-org phase. Multi-org staff/provider support deferred to future sprint.

---

## Deferred to Next Sprint

```
billing_staff dashboard UI
compliance_officer audit UI
clinical_staff view
Department model + department-scoped staff
ProviderOrganizationProfile (multi-hospital doctor support)
Analytics charts in hospital_owner dashboard
Break-glass PHI access workflow (can_break_glass_access_phi)
Multi-org org switcher for non-platform users
```

---

## Test Coverage Required

### Data layer
```
Organization slug is unique
Membership unique constraint blocks duplicate user/org row
No patient OrganizationMembership created by migration
Admin user migrated to platform_owner
Doctors migrated to Demo Clinic membership
platform_* roles rejected for non-platform org (and vice versa)
Invite token is stored as hash, not raw
Duplicate pending invite for same org+email is blocked
```

### Permission layer
```
is_platform_owner returns False for unauthenticated user
is_platform_owner returns False for hospital_admin user
has_org_role returns False for inactive membership
Doctor cannot manage all org appointments (can_manage_org_appointments fails for doctor role)
Doctor can manage own appointment (can_manage_own_appointment passes)
Patient always returns False on has_org_role
can_view_health_record: shared record = True, unshared = False, different patient = False
can_break_glass_access_phi returns False (stub)
2FA middleware blocks hospital_owner without TOTP
DRF IsOrgDoctor rejects doctor not in org
get_invitable_roles: hospital_admin cannot grant hospital_owner or compliance_officer
```

### Query scoping layer
```
scope_to_org(qs, None, non-platform-user) returns empty queryset
scope_to_org(qs, None, platform_staff) returns full queryset
Hospital A selector returns 0 results from Hospital B
Doctor A sees only own appointments, not Doctor B's
Patient sees all own appointments regardless of org
get_object_or_404 with wrong org returns 404
Invalid org_slug returns 403
WebSocket connection rejected for wrong org membership
Celery slot task does not create slots in wrong org
CSV export for Hospital A excludes Hospital B data
Knowledge graph for Hospital A excludes Hospital B nodes
```

### UI layer
```
Pending hospital owner sees holding page, not dashboard
Suspended org blocks dashboard access with clear message
Platform owner can approve org
hospital_admin cannot approve org
hospital_admin cannot invite hospital_owner
scheduler cannot access staff invite page
scheduler cannot see health record or prescription links
Expired invite cannot be accepted
Revoked invite cannot be accepted
Accepted invite cannot be reused
Doctor invite redirects to profile completion if DoctorProfile missing
Organization switcher hidden for hospital staff
Wrong org slug returns 403/404
```

---

## Architecture Principles

```
User.role   → who are you globally?
Membership  → which building are you allowed to enter?
Relationship → which room can you open?

None should fail closed unless platform access is explicitly proven.
Memberships are deactivated, never deleted.
Platform staff do not access PHI until break-glass is implemented.
Org role alone never grants PHI access — patient relationship required.
Services are the deadbolt. Views are the first lock.
```

---

## Files Created / Modified Summary

**New files:**
```
apps/accounts/permissions.py
apps/accounts/org_context.py
apps/scheduling/permissions.py
apps/payments/permissions.py
apps/messaging/permissions.py
apps/adminpanel/permissions.py
apps/accounts/migrations/0016_expand_user_role_field.py
apps/accounts/migrations/0017_organization_membership_invite.py
apps/accounts/migrations/0018_data_migration_default_orgs.py
apps/accounts/migrations/0019_add_org_fk_to_tenant_models.py
apps/accounts/migrations/0020_backfill_organization.py
apps/accounts/migrations/0021_alter_org_fk_null_false.py
apps/accounts/migrations/0022_remove_old_admin_role.py
templates/accounts/org_register.html
templates/accounts/org_pending.html
templates/accounts/invite_accept.html
templates/org/dashboard_hospital_owner.html
templates/org/dashboard_hospital_admin.html
templates/org/dashboard_scheduler.html
templates/org/settings.html
templates/org/staff_list.html
templates/org/staff_invite.html
templates/org/staff_member.html
templates/org/coming_soon.html
templates/adminpanel/organizations_list.html
templates/adminpanel/organization_detail.html
apps/accounts/org_urls.py
```

**Modified files:**
```
apps/accounts/models.py               User.role field + 3 new models + queryset helpers
apps/accounts/middleware.py           2FA role check expansion
apps/accounts/context_processors.py  add OrgContext
apps/api/permissions.py               new DRF classes
apps/scheduling/selectors.py          add organization param to all selectors
apps/adminpanel/selectors.py          add organization param + scope_to_org
apps/messaging/selectors.py           add organization param
apps/scheduling/consumers.py          org membership check before connect
apps/messaging/consumers.py           org membership check before connect
apps/scheduling/tasks.py              loop by org
config/urls.py                        new /org/ and /invite/ routes
config/settings/base.py               no changes needed
README.md
CLAUDE.md
```
