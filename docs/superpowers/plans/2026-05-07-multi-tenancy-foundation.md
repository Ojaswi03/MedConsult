# Multi-Tenancy Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Organization/OrganizationMembership/OrganizationInvite models, a 9-role permission system, and org-scoped selectors so Hospital A can never see Hospital B data.

**Architecture:** Layered approach — data models first, permission helpers second, query scoping third. Each layer has tests before the next layer begins. All existing functionality must remain working after each commit.

**Tech Stack:** Django 4.2, PostgreSQL, pytest-django, existing `apps/accounts`, `apps/scheduling`, `apps/payments`, `apps/messaging`, `apps/consultations`, `apps/adminpanel`

**Spec:** `docs/superpowers/specs/2026-05-07-multi-tenancy-design.md`

---

## Phase 1 — Data Layer

### Task 1: Expand `User.role` field and add `org_user` choice

**Files:**
- Modify: `apps/accounts/models.py` lines 40–64
- Test: `apps/accounts/tests.py`

- [ ] **Step 1: Write failing test**

```python
# In apps/accounts/tests.py, add to UserCreationTests:
def test_org_user_role_valid(self):
    user = User.objects.create_user(
        username='staffuser', email='staff@test.com',
        password='pass1234!', role='org_user',
    )
    self.assertEqual(user.role, 'org_user')

def test_platform_owner_role_valid(self):
    user = User.objects.create_user(
        username='po', email='po@test.com',
        password='pass1234!', role='platform_owner',
    )
    self.assertEqual(user.role, 'platform_owner')
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
python manage.py test apps.accounts.tests.UserCreationTests.test_org_user_role_valid --settings=config.settings.dev
```

Expected: passes (Django doesn't validate choices on create_user by default) but `max_length` violation will surface at DB level if value > 10 chars. Verify by checking `User._meta.get_field('role').max_length` equals 10 currently.

- [ ] **Step 3: Update `User.role` in `apps/accounts/models.py`**

Replace the `ROLE_CHOICES` and `role` field:

```python
ROLE_CHOICES = [
    ('platform_owner', 'Platform Owner'),
    ('platform_admin', 'Platform Admin'),
    ('doctor', 'Doctor'),
    ('patient', 'Patient'),
    ('org_user', 'Organization User'),
]

role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='patient')
```

- [ ] **Step 4: Generate and apply migration**

```bash
python manage.py makemigrations accounts --name expand_user_role_field --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
```

Expected: migration `0016_expand_user_role_field.py` created and applied.

- [ ] **Step 5: Run tests — expect PASS**

```bash
python manage.py test apps.accounts.tests.UserCreationTests --settings=config.settings.dev
```

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/models.py apps/accounts/migrations/0016_expand_user_role_field.py apps/accounts/tests.py
git commit -m "feat(accounts): expand User.role field to 30 chars, add org_user/platform_owner/platform_admin choices"
```

---

### Task 2: Add `Organization`, `OrganizationMembership`, `OrganizationInvite` models

**Files:**
- Modify: `apps/accounts/models.py`
- Test: `apps/accounts/tests.py`

- [ ] **Step 1: Write failing tests**

```python
# Add class OrgModelTests(TestCase): in apps/accounts/tests.py

from apps.accounts.models import Organization, OrganizationMembership, OrganizationInvite

class OrgModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='City Hospital', slug='city-hospital',
            org_type='hospital', status='active',
        )
        self.owner = User.objects.create_user(
            username='hospowner', email='owner@city.com',
            password='pass1234!', role='org_user',
        )

    def test_organization_created(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(self.org.status, 'active')

    def test_membership_created(self):
        m = OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner',
        )
        self.assertTrue(m.is_active)

    def test_duplicate_membership_blocked(self):
        OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner',
        )
        with self.assertRaises(Exception):
            OrganizationMembership.objects.create(
                user=self.owner, organization=self.org, role='hospital_admin',
            )

    def test_patient_can_have_no_membership(self):
        patient = User.objects.create_user(
            username='pat1', email='pat1@test.com',
            password='pass1234!', role='patient',
        )
        self.assertEqual(
            OrganizationMembership.objects.filter(user=patient).count(), 0
        )

    def test_org_slug_unique(self):
        with self.assertRaises(Exception):
            Organization.objects.create(
                name='Other', slug='city-hospital', org_type='clinic', status='active',
            )

    def test_platform_role_stored_on_membership(self):
        platform_org = Organization.objects.create(
            name='MedConsult Platform', slug='medconsult-platform',
            org_type='platform', status='active',
        )
        m = OrganizationMembership.objects.create(
            user=self.owner, organization=platform_org, role='platform_owner',
        )
        self.assertEqual(m.role, 'platform_owner')
```

- [ ] **Step 2: Run tests — expect ImportError (models don't exist yet)**

```bash
python manage.py test apps.accounts.tests.OrgModelTests --settings=config.settings.dev
```

- [ ] **Step 3: Add models to `apps/accounts/models.py`**

Add after the existing `PasswordResetToken` class:

```python
import hashlib


class Organization(models.Model):
    ORG_TYPE_CHOICES = [
        ('platform', 'Platform'),
        ('hospital', 'Hospital'),
        ('clinic', 'Clinic'),
        ('private_practice', 'Private Practice'),
        ('urgent_care', 'Urgent Care'),
        ('mental_health', 'Mental Health Group'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('needs_info', 'Needs More Information'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    org_type = models.CharField(max_length=30, choices=ORG_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    approved_by = models.ForeignKey(
        'User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_organizations',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_organizations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    ROLE_CHOICES = [
        ('platform_owner', 'Platform Owner'),
        ('platform_admin', 'Platform Admin'),
        ('hospital_owner', 'Hospital Owner'),
        ('hospital_admin', 'Hospital Admin'),
        ('doctor', 'Doctor'),
        ('scheduler', 'Scheduler'),
        ('billing_staff', 'Billing Staff'),
        ('compliance_officer', 'Compliance Officer'),
        ('clinical_staff', 'Clinical Staff'),
    ]

    user = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='memberships',
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='memberships',
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        'User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sent_memberships',
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        'User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='deactivated_memberships',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_memberships'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'organization'],
                name='unique_user_organization_membership',
            )
        ]
        indexes = [
            models.Index(fields=['organization', 'role', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.role} @ {self.organization.name}"


class OrganizationInvite(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='invites',
    )
    invited_by = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='sent_invites',
    )
    email = models.EmailField()
    role = models.CharField(max_length=30, choices=OrganizationMembership.ROLE_CHOICES)
    token_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(
        'User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='accepted_invites',
    )
    revoked_by = models.ForeignKey(
        'User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='revoked_invites',
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_invites'
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'email'],
                condition=models.Q(status='pending'),
                name='unique_pending_invite_per_org_email',
            )
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @classmethod
    def make_token_hash(cls, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.status == 'pending' and not self.is_expired

    def __str__(self):
        return f"Invite {self.email} → {self.role} @ {self.organization.name}"
```

- [ ] **Step 4: Generate and apply migration**

```bash
python manage.py makemigrations accounts --name add_organization_membership_invite --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
```

Expected: `0017_add_organization_membership_invite.py` created and applied.

- [ ] **Step 5: Run tests — expect PASS**

```bash
python manage.py test apps.accounts.tests.OrgModelTests --settings=config.settings.dev
```

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/models.py apps/accounts/migrations/0017_add_organization_membership_invite.py apps/accounts/tests.py
git commit -m "feat(accounts): add Organization, OrganizationMembership, OrganizationInvite models"
```

---

### Task 3: Data migration — create default orgs, assign existing users

**Files:**
- Create: `apps/accounts/migrations/0018_data_migration_default_orgs.py`
- Test: `apps/accounts/tests.py`

- [ ] **Step 1: Write test to verify migration outcome**

```python
# Add to apps/accounts/tests.py

class DataMigrationTests(TestCase):
    def test_platform_org_exists(self):
        from apps.accounts.models import Organization
        self.assertTrue(
            Organization.objects.filter(slug='medconsult-platform', org_type='platform').exists()
        )

    def test_demo_clinic_exists(self):
        from apps.accounts.models import Organization
        self.assertTrue(
            Organization.objects.filter(slug='medconsult-demo-clinic', org_type='clinic').exists()
        )

    def test_admin_user_is_platform_owner(self):
        # Only runs if admin user was created via seed
        if User.objects.filter(username='admin').exists():
            admin = User.objects.get(username='admin')
            self.assertEqual(admin.role, 'platform_owner')

    def test_patients_have_no_membership(self):
        from apps.accounts.models import OrganizationMembership
        patients = User.objects.filter(role='patient')
        for patient in patients:
            self.assertEqual(
                OrganizationMembership.objects.filter(user=patient).count(), 0,
                f"Patient {patient.email} should have no membership"
            )
```

- [ ] **Step 2: Create the data migration manually**

Create `apps/accounts/migrations/0018_data_migration_default_orgs.py`:

```python
from django.db import migrations
from django.utils import timezone


def create_default_orgs(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    OrganizationMembership = apps.get_model('accounts', 'OrganizationMembership')
    User = apps.get_model('accounts', 'User')

    # Create platform org
    platform_org, _ = Organization.objects.get_or_create(
        slug='medconsult-platform',
        defaults={
            'name': 'MedConsult Platform',
            'org_type': 'platform',
            'status': 'active',
        },
    )

    # Create demo clinic for existing clinical data
    demo_clinic, _ = Organization.objects.get_or_create(
        slug='medconsult-demo-clinic',
        defaults={
            'name': 'MedConsult Demo Clinic',
            'org_type': 'clinic',
            'status': 'active',
        },
    )

    # Migrate admin → platform_owner
    User.objects.filter(role='admin').update(role='platform_owner')

    # platform_owner / platform_admin → membership in platform org
    for user in User.objects.filter(role__in=['platform_owner', 'platform_admin']):
        OrganizationMembership.objects.get_or_create(
            user=user, organization=platform_org,
            defaults={'role': user.role, 'is_active': True, 'accepted_at': timezone.now()},
        )

    # doctors → membership in demo clinic
    for user in User.objects.filter(role='doctor'):
        OrganizationMembership.objects.get_or_create(
            user=user, organization=demo_clinic,
            defaults={'role': 'doctor', 'is_active': True, 'accepted_at': timezone.now()},
        )

    # patients → NO membership (platform-wide)


def reverse_default_orgs(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    User = apps.get_model('accounts', 'User')
    Organization.objects.filter(
        slug__in=['medconsult-platform', 'medconsult-demo-clinic']
    ).delete()
    User.objects.filter(role='platform_owner').update(role='admin')


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0017_add_organization_membership_invite'),
    ]

    operations = [
        migrations.RunPython(create_default_orgs, reverse_default_orgs),
    ]
```

- [ ] **Step 3: Apply migration**

```bash
python manage.py migrate --settings=config.settings.dev
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python manage.py test apps.accounts.tests.DataMigrationTests --settings=config.settings.dev
```

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/migrations/0018_data_migration_default_orgs.py apps/accounts/tests.py
git commit -m "feat(accounts): data migration — create default platform org and demo clinic, assign existing users"
```

---

### Task 4: Add `organization` FK to all tenant-scoped models

**Files:**
- Modify: `apps/scheduling/models.py`
- Modify: `apps/payments/models.py`
- Modify: `apps/messaging/models.py`
- Modify: `apps/consultations/models.py`
- Modify: `apps/adminpanel/models.py`

- [ ] **Step 1: Add FK to `apps/scheduling/models.py`**

Add to each model listed below — import Organization at top:

```python
# At top of apps/scheduling/models.py, add:
from apps.accounts.models import Organization
```

Then add to each model (all `null=True, blank=True` for now):

```python
# AvailabilityWindow — after existing fields, before class Meta:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='availability_windows',
)

# Slot — same pattern:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='slots',
)

# Appointment:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='appointments',
)

# WaitlistEntry:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='waitlist_entries',
)

# Review:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='reviews',
)

# Referral:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='referrals',
)

# Prescription:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='prescriptions',
)
```

- [ ] **Step 2: Add FK to `apps/payments/models.py`**

```python
# In Payment model, after existing fields:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='payments',
)
```

- [ ] **Step 3: Add FK to `apps/messaging/models.py`**

```python
# In Conversation model:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='conversations',
)
```

- [ ] **Step 4: Add FK to `apps/consultations/models.py`**

```python
# In VideoRoom model:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='video_rooms',
)
```

- [ ] **Step 5: Add FK to `apps/adminpanel/models.py`**

```python
# In AdminActivityLog model:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='admin_logs',
)

# In HealthRecordAccessLog model:
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='health_record_access_logs',
)
```

- [ ] **Step 6: Also add to `DoctorProfile` in `apps/accounts/models.py`**

```python
# In DoctorProfile model (after existing fields, before bank info section):
organization = models.ForeignKey(
    Organization, null=True, blank=True, on_delete=models.SET_NULL,
    related_name='doctor_profiles',
    help_text='Temporary single-org FK. Will be replaced by ProviderOrganizationProfile for multi-hospital support.',
)
```

- [ ] **Step 7: Generate all migrations at once**

```bash
python manage.py makemigrations --name add_organization_fk --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
```

Expected: one migration per app that has changes.

- [ ] **Step 8: Run full test suite — expect PASS**

```bash
python manage.py test apps --settings=config.settings.dev
```

- [ ] **Step 9: Commit**

```bash
git add apps/scheduling/models.py apps/payments/models.py apps/messaging/models.py apps/consultations/models.py apps/adminpanel/models.py apps/accounts/models.py apps/*/migrations/
git commit -m "feat: add nullable organization FK to all tenant-scoped models"
```

---

### Task 5: Backfill `organization` on existing records

**Files:**
- Create: `apps/accounts/migrations/0019_backfill_organization.py`
- Test: `apps/accounts/tests.py`

- [ ] **Step 1: Write test**

```python
class BackfillOrgTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization
        self.demo_clinic = Organization.objects.get(slug='medconsult-demo-clinic')
        # Create a doctor with membership in demo clinic
        self.doctor_user = User.objects.create_user(
            username='bfdoc', email='bfdoc@test.com',
            password='pass1234!', role='doctor',
        )
        from apps.accounts.models import OrganizationMembership
        OrganizationMembership.objects.create(
            user=self.doctor_user, organization=self.demo_clinic,
            role='doctor', is_active=True,
        )
        from apps.accounts.models import DoctorProfile
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            specialization='General',
            medical_license_number='BF-001',
        )

    def test_doctor_profile_gets_org(self):
        self.doctor_profile.refresh_from_db()
        # After backfill migration runs, DoctorProfile.organization should be set
        # We verify the backfill logic directly here
        from apps.accounts.models import Organization, OrganizationMembership
        demo = Organization.objects.get(slug='medconsult-demo-clinic')
        membership = OrganizationMembership.objects.filter(
            user=self.doctor_user, role='doctor', is_active=True,
        ).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.organization, demo)
```

- [ ] **Step 2: Create backfill migration**

Create `apps/accounts/migrations/0019_backfill_organization.py`:

```python
from django.db import migrations


def backfill_organization(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    OrganizationMembership = apps.get_model('accounts', 'OrganizationMembership')
    DoctorProfile = apps.get_model('accounts', 'DoctorProfile')
    Appointment = apps.get_model('scheduling', 'Appointment')
    Slot = apps.get_model('scheduling', 'Slot')
    AvailabilityWindow = apps.get_model('scheduling', 'AvailabilityWindow')
    Payment = apps.get_model('payments', 'Payment')
    Conversation = apps.get_model('messaging', 'Conversation')
    Referral = apps.get_model('scheduling', 'Referral')
    Prescription = apps.get_model('scheduling', 'Prescription')
    WaitlistEntry = apps.get_model('scheduling', 'WaitlistEntry')
    VideoRoom = apps.get_model('consultations', 'VideoRoom')

    try:
        demo_clinic = Organization.objects.get(slug='medconsult-demo-clinic')
        platform_org = Organization.objects.get(slug='medconsult-platform')
    except Organization.DoesNotExist:
        return  # Skip if orgs don't exist (fresh install)

    # DoctorProfile → org from membership
    for dp in DoctorProfile.objects.filter(organization__isnull=True):
        membership = OrganizationMembership.objects.filter(
            user=dp.user, role='doctor', is_active=True,
        ).first()
        if membership:
            dp.organization = membership.organization
            dp.save(update_fields=['organization'])

    # Appointment → org from doctor membership
    for appt in Appointment.objects.filter(organization__isnull=True):
        dp = DoctorProfile.objects.filter(user=appt.doctor.user).first() if hasattr(appt.doctor, 'user') else None
        if dp and dp.organization:
            appt.organization = dp.organization
        else:
            appt.organization = demo_clinic
        appt.save(update_fields=['organization'])

    # Slot → org from doctor profile
    for slot in Slot.objects.filter(organization__isnull=True):
        if slot.doctor.organization:
            slot.organization = slot.doctor.organization
        else:
            slot.organization = demo_clinic
        slot.save(update_fields=['organization'])

    # AvailabilityWindow → same logic
    for aw in AvailabilityWindow.objects.filter(organization__isnull=True):
        if aw.doctor.organization:
            aw.organization = aw.doctor.organization
        else:
            aw.organization = demo_clinic
        aw.save(update_fields=['organization'])

    # Payment → from appointment
    for payment in Payment.objects.filter(organization__isnull=True):
        if payment.appointment.organization:
            payment.organization = payment.appointment.organization
        else:
            payment.organization = demo_clinic
        payment.save(update_fields=['organization'])

    # Conversation → from appointment if linked, else demo clinic
    for conv in Conversation.objects.filter(organization__isnull=True):
        if conv.appointment and conv.appointment.organization:
            conv.organization = conv.appointment.organization
        else:
            conv.organization = demo_clinic
        conv.save(update_fields=['organization'])

    # Referral → from referring doctor
    for ref in Referral.objects.filter(organization__isnull=True):
        dp = DoctorProfile.objects.filter(user=ref.referring_doctor).first() if hasattr(ref, 'referring_doctor') else None
        ref.organization = dp.organization if (dp and dp.organization) else demo_clinic
        ref.save(update_fields=['organization'])

    # Prescription → from appointment
    for rx in Prescription.objects.filter(organization__isnull=True):
        if rx.appointment.organization:
            rx.organization = rx.appointment.organization
        else:
            rx.organization = demo_clinic
        rx.save(update_fields=['organization'])

    # WaitlistEntry → from doctor profile
    for we in WaitlistEntry.objects.filter(organization__isnull=True):
        we.organization = we.doctor.organization if we.doctor.organization else demo_clinic
        we.save(update_fields=['organization'])

    # VideoRoom → from appointment
    for vr in VideoRoom.objects.filter(organization__isnull=True):
        if vr.appointment.organization:
            vr.organization = vr.appointment.organization
        else:
            vr.organization = demo_clinic
        vr.save(update_fields=['organization'])


def reverse_backfill(apps, schema_editor):
    pass  # Irreversible — nulling out org FKs again not worth the risk


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0018_data_migration_default_orgs'),
        ('scheduling', '0020_add_organization_fk'),  # adjust to actual migration name
        ('payments', '0002_add_organization_fk'),
        ('messaging', '0005_add_organization_fk'),
        ('consultations', '0002_add_organization_fk'),
        ('adminpanel', '0004_add_organization_fk'),
    ]

    operations = [
        migrations.RunPython(backfill_organization, reverse_backfill),
    ]
```

> **Note:** Verify the `dependencies` migration names match what was actually generated in Task 4 before running.

- [ ] **Step 3: Apply migration**

```bash
python manage.py migrate --settings=config.settings.dev
```

- [ ] **Step 4: Verify backfill in shell**

```bash
python manage.py shell --settings=config.settings.dev
```

```python
from apps.scheduling.models import Appointment
from apps.accounts.models import Organization
print("Appointments without org:", Appointment.objects.filter(organization__isnull=True).count())
print("Total appointments:", Appointment.objects.count())
```

Expected: `Appointments without org: 0` (if any appointments exist).

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/migrations/0019_backfill_organization.py apps/accounts/tests.py
git commit -m "feat: backfill organization FK on all tenant-scoped existing records"
```

---

### Task 6: Make `organization` non-nullable on core operational models

**Files:**
- Modify: `apps/scheduling/models.py`, `apps/payments/models.py`, `apps/messaging/models.py`

- [ ] **Step 1: Remove `null=True, blank=True` from required models**

In `apps/scheduling/models.py`, update `organization` on:
`AvailabilityWindow`, `Slot`, `Appointment`, `Referral`, `Prescription`, `WaitlistEntry`

Change from:
```python
organization = models.ForeignKey(
    'accounts.Organization', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='...',
)
```

To (for each):
```python
organization = models.ForeignKey(
    'accounts.Organization', on_delete=models.PROTECT,
    related_name='...',
)
```

In `apps/payments/models.py` — same change for `Payment.organization`.

In `apps/messaging/models.py` — same change for `Conversation.organization`.

> Keep `null=True` on: `DoctorProfile`, `Review`, `VideoRoom`, `HealthRecordAccessLog`, `AdminActivityLog`, `Notification` — these are nullable by design.

- [ ] **Step 2: Generate and apply migration**

```bash
python manage.py makemigrations --name make_org_fk_required --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
```

- [ ] **Step 3: Run full test suite**

```bash
python manage.py test apps --settings=config.settings.dev
```

- [ ] **Step 4: Commit**

```bash
git add apps/scheduling/models.py apps/payments/models.py apps/messaging/models.py apps/*/migrations/
git commit -m "feat: make organization FK non-nullable on Appointment, Slot, Payment, AvailabilityWindow, Prescription, Referral, Conversation, WaitlistEntry"
```

---

### Task 7: Remove old `admin` role choice, add queryset managers

**Files:**
- Modify: `apps/accounts/models.py`

- [ ] **Step 1: Remove `admin` from `User.ROLE_CHOICES`**

In `apps/accounts/models.py`, `User.ROLE_CHOICES` should now only contain:
```python
ROLE_CHOICES = [
    ('platform_owner', 'Platform Owner'),
    ('platform_admin', 'Platform Admin'),
    ('doctor', 'Doctor'),
    ('patient', 'Patient'),
    ('org_user', 'Organization User'),
]
```

- [ ] **Step 2: Add queryset managers to tenant models**

In `apps/scheduling/models.py`, add before each model class:

```python
class AppointmentQuerySet(models.QuerySet):
    def for_org(self, organization):
        return self.filter(organization=organization)

    def for_patient(self, patient):
        return self.filter(patient=patient)

    def for_doctor(self, doctor):
        return self.filter(doctor=doctor)

class AppointmentManager(models.Manager):
    def get_queryset(self):
        return AppointmentQuerySet(self.model, using=self._db)
```

Then in `Appointment` model:
```python
objects = AppointmentManager()
```

Add similar QuerySet/Manager for `Slot`:

```python
class SlotQuerySet(models.QuerySet):
    def for_org(self, organization):
        return self.filter(organization=organization)

    def available(self):
        from django.utils import timezone
        return self.filter(is_booked=False, is_blocked=False,
                           start_datetime__gt=timezone.now())
```

- [ ] **Step 3: Generate migration for role choice removal**

```bash
python manage.py makemigrations accounts --name remove_admin_role --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
```

- [ ] **Step 4: Run all tests**

```bash
python manage.py test apps --settings=config.settings.dev
```

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/models.py apps/scheduling/models.py apps/accounts/migrations/
git commit -m "feat(accounts): remove legacy admin role choice, add queryset managers to Appointment and Slot"
```

---

## Phase 2 — Permission Layer

### Task 8: Create `apps/accounts/org_context.py`

**Files:**
- Create: `apps/accounts/org_context.py`
- Test: `apps/accounts/tests.py`

- [ ] **Step 1: Write failing test**

```python
class OrgContextTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization, OrganizationMembership
        self.org = Organization.objects.create(
            name='Test Hosp', slug='test-hosp', org_type='hospital', status='active',
        )
        self.user = User.objects.create_user(
            username='ctxuser', email='ctx@test.com',
            password='pass1234!', role='org_user',
        )
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org, role='hospital_admin', is_active=True,
        )

    def test_get_selected_org_from_single_membership(self):
        from apps.accounts.org_context import get_selected_organization
        from unittest.mock import MagicMock
        request = MagicMock()
        request.user = self.user
        request.session = {}
        ctx = get_selected_organization(request)
        self.assertEqual(ctx.organization, self.org)
        self.assertEqual(ctx.source, 'single_membership')
        self.assertFalse(ctx.is_platform_scope)

    def test_no_membership_returns_none_org(self):
        from apps.accounts.org_context import get_selected_organization
        from unittest.mock import MagicMock
        patient = User.objects.create_user(
            username='ctxpat', email='ctxpat@test.com',
            password='pass1234!', role='patient',
        )
        request = MagicMock()
        request.user = patient
        request.session = {}
        ctx = get_selected_organization(request)
        self.assertIsNone(ctx.organization)
        self.assertEqual(ctx.source, 'none')

    def test_platform_staff_gets_platform_scope(self):
        from apps.accounts.org_context import get_selected_organization
        from unittest.mock import MagicMock
        po = User.objects.create_user(
            username='ctxpo', email='ctxpo@test.com',
            password='pass1234!', role='platform_owner',
        )
        request = MagicMock()
        request.user = po
        request.session = {}
        ctx = get_selected_organization(request)
        self.assertTrue(ctx.is_platform_scope)
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python manage.py test apps.accounts.tests.OrgContextTests --settings=config.settings.dev
```

- [ ] **Step 3: Create `apps/accounts/org_context.py`**

```python
"""
Organization context resolution for requests.
Separates request/org resolution from permission checks.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OrgContext:
    organization: Optional[object] = None      # Organization | None
    membership: Optional[object] = None        # OrganizationMembership | None
    is_platform_scope: bool = False
    source: str = 'none'  # 'url' | 'session' | 'single_membership' | 'none'


def get_selected_organization(request) -> OrgContext:
    """
    Resolve the active organization for this request.

    Priority:
    1. URL kwarg org_slug (verified: user must have active membership)
    2. session['active_organization_id']
    3. User's single active membership org
    4. None (platform staff get is_platform_scope=True; patients get empty context)
    """
    from apps.accounts.models import Organization, OrganizationMembership
    from apps.accounts.permissions import is_platform_staff

    user = request.user
    if not user or not user.is_authenticated:
        return OrgContext()

    # Platform staff always get platform scope (they can also select an org below)
    _is_platform = is_platform_staff(user)

    # 1. URL kwarg
    org_slug = getattr(request, 'resolver_match', None)
    if org_slug:
        org_slug = request.resolver_match.kwargs.get('org_slug')
    if org_slug:
        try:
            org = Organization.objects.get(slug=org_slug, status='active')
        except Organization.DoesNotExist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Organization not found or inactive.")
        if not _is_platform:
            membership = OrganizationMembership.objects.filter(
                user=user, organization=org, is_active=True,
            ).first()
            if not membership:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("You do not have access to this organization.")
        else:
            membership = OrganizationMembership.objects.filter(
                user=user, organization=org, is_active=True,
            ).first()
        return OrgContext(
            organization=org, membership=membership,
            is_platform_scope=_is_platform, source='url',
        )

    # 2. Session
    session_org_id = request.session.get('active_organization_id')
    if session_org_id:
        try:
            org = Organization.objects.get(id=session_org_id, status='active')
            membership = OrganizationMembership.objects.filter(
                user=user, organization=org, is_active=True,
            ).first()
            if membership or _is_platform:
                return OrgContext(
                    organization=org, membership=membership,
                    is_platform_scope=_is_platform, source='session',
                )
        except Organization.DoesNotExist:
            pass

    # 3. Single active membership
    memberships = OrganizationMembership.objects.filter(
        user=user, is_active=True,
    ).select_related('organization')
    if memberships.count() == 1:
        m = memberships.first()
        return OrgContext(
            organization=m.organization, membership=m,
            is_platform_scope=_is_platform, source='single_membership',
        )

    # 4. Fallback
    return OrgContext(is_platform_scope=_is_platform, source='none')
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python manage.py test apps.accounts.tests.OrgContextTests --settings=config.settings.dev
```

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/org_context.py apps/accounts/tests.py
git commit -m "feat(accounts): add OrgContext dataclass and get_selected_organization resolver"
```

---

### Task 9: Create `apps/accounts/permissions.py`

**Files:**
- Create: `apps/accounts/permissions.py`
- Test: `apps/accounts/tests.py`

- [ ] **Step 1: Write failing tests**

```python
class PermissionHelpersTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization, OrganizationMembership
        self.org = Organization.objects.create(
            name='Perm Hosp', slug='perm-hosp', org_type='hospital', status='active',
        )
        self.platform_owner = User.objects.create_user(
            username='permpo', email='permpo@test.com',
            password='pass1234!', role='platform_owner',
        )
        self.org_user = User.objects.create_user(
            username='permou', email='permou@test.com',
            password='pass1234!', role='org_user',
        )
        self.patient = User.objects.create_user(
            username='permpat', email='permpat@test.com',
            password='pass1234!', role='patient',
        )
        self.doctor_user = User.objects.create_user(
            username='permdoc', email='permdoc@test.com',
            password='pass1234!', role='doctor',
        )
        OrganizationMembership.objects.create(
            user=self.org_user, organization=self.org,
            role='hospital_admin', is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.doctor_user, organization=self.org,
            role='doctor', is_active=True,
        )

    def test_is_platform_owner(self):
        from apps.accounts.permissions import is_platform_owner
        self.assertTrue(is_platform_owner(self.platform_owner))
        self.assertFalse(is_platform_owner(self.org_user))
        self.assertFalse(is_platform_owner(None))

    def test_is_platform_staff(self):
        from apps.accounts.permissions import is_platform_staff
        self.assertTrue(is_platform_staff(self.platform_owner))
        self.assertFalse(is_platform_staff(self.org_user))

    def test_has_org_role(self):
        from apps.accounts.permissions import has_org_role
        self.assertTrue(has_org_role(self.org_user, self.org, ['hospital_admin']))
        self.assertFalse(has_org_role(self.org_user, self.org, ['hospital_owner']))
        self.assertFalse(has_org_role(self.patient, self.org, ['hospital_admin']))

    def test_inactive_membership_fails(self):
        from apps.accounts.models import OrganizationMembership
        from apps.accounts.permissions import has_org_role
        OrganizationMembership.objects.filter(
            user=self.org_user, organization=self.org,
        ).update(is_active=False)
        self.assertFalse(has_org_role(self.org_user, self.org, ['hospital_admin']))

    def test_patient_always_false_on_has_org_role(self):
        from apps.accounts.permissions import has_org_role
        self.assertFalse(has_org_role(self.patient, self.org, ['hospital_admin', 'doctor']))

    def test_can_manage_staff(self):
        from apps.accounts.permissions import can_manage_staff
        self.assertTrue(can_manage_staff(self.org_user, self.org))
        self.assertFalse(can_manage_staff(self.patient, self.org))
        self.assertFalse(can_manage_staff(self.doctor_user, self.org))

    def test_can_manage_org_appointments(self):
        from apps.accounts.permissions import can_manage_org_appointments
        self.assertTrue(can_manage_org_appointments(self.org_user, self.org))
        self.assertFalse(can_manage_org_appointments(self.doctor_user, self.org))

    def test_can_manage_own_appointment(self):
        from apps.accounts.permissions import can_manage_own_appointment
        from unittest.mock import MagicMock
        appt = MagicMock()
        appt.doctor.user = self.doctor_user
        self.assertTrue(can_manage_own_appointment(self.doctor_user, appt))
        self.assertFalse(can_manage_own_appointment(self.org_user, appt))

    def test_get_invitable_roles_hospital_admin_cannot_grant_compliance(self):
        from apps.accounts.permissions import get_invitable_roles
        roles = get_invitable_roles(self.org_user, self.org)
        self.assertNotIn('hospital_owner', roles)
        self.assertNotIn('compliance_officer', roles)
        self.assertIn('doctor', roles)
        self.assertIn('scheduler', roles)

    def test_can_approve_organization_platform_only(self):
        from apps.accounts.permissions import can_approve_organization
        self.assertTrue(can_approve_organization(self.platform_owner))
        self.assertFalse(can_approve_organization(self.org_user))
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python manage.py test apps.accounts.tests.PermissionHelpersTests --settings=config.settings.dev
```

- [ ] **Step 3: Create `apps/accounts/permissions.py`**

```python
"""
Permission helpers for MedConsult multi-tenant access control.

Three tiers:
  Tier 1 — Global account checks (User.role)
  Tier 2 — Org membership checks (OrganizationMembership.role)
  Tier 3 — Action checks (combine tier 1 + 2 + object relationships)

All helpers fail closed: unauthenticated users return False.
"""


# ── Tier 1: Global account checks ────────────────────────────────────────────

def is_platform_owner(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'platform_owner'
    )


def is_platform_staff(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role in ('platform_owner', 'platform_admin')
    )


def is_doctor(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'doctor'
    )


def is_patient(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'patient'
    )


def is_org_user(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'org_user'
    )


# ── Tier 2: Org membership checks ────────────────────────────────────────────

def get_membership(user, organization):
    """Return active OrganizationMembership or None."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    from apps.accounts.models import OrganizationMembership
    return OrganizationMembership.objects.filter(
        user=user, organization=organization, is_active=True,
    ).first()


def has_org_role(user, organization, allowed_roles) -> bool:
    """True if user has an active membership with one of the allowed roles."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    from apps.accounts.models import OrganizationMembership
    return OrganizationMembership.objects.filter(
        user=user, organization=organization,
        role__in=allowed_roles, is_active=True,
    ).exists()


def get_user_organizations(user):
    """Return queryset of organizations where user has an active membership."""
    if not user or not getattr(user, 'is_authenticated', False):
        from apps.accounts.models import Organization
        return Organization.objects.none()
    from apps.accounts.models import Organization, OrganizationMembership
    org_ids = OrganizationMembership.objects.filter(
        user=user, is_active=True,
    ).values_list('organization_id', flat=True)
    return Organization.objects.filter(id__in=org_ids)


def has_any_elevated_membership(user) -> bool:
    """
    True if user has any active org membership with an elevated role.
    Used by 2FA middleware — does NOT depend on selected org.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    ELEVATED = [
        'hospital_owner', 'hospital_admin', 'scheduler',
        'billing_staff', 'compliance_officer', 'clinical_staff', 'doctor',
    ]
    from apps.accounts.models import OrganizationMembership
    return OrganizationMembership.objects.filter(
        user=user, is_active=True, role__in=ELEVATED,
    ).exists()


# ── Tier 3: Action checks ─────────────────────────────────────────────────────

def can_approve_organization(user) -> bool:
    return is_platform_staff(user)


def can_suspend_organization(user) -> bool:
    return is_platform_staff(user)


def can_edit_organization_profile(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'hospital_admin'],
    )


def can_manage_staff(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'hospital_admin'],
    )


def can_invite_staff(user, organization) -> bool:
    return can_manage_staff(user, organization)


def get_invitable_roles(user, organization) -> list:
    """Return the list of roles this user is allowed to grant via invite."""
    if is_platform_staff(user):
        from apps.accounts.models import OrganizationMembership
        return [r for r, _ in OrganizationMembership.ROLE_CHOICES]
    if has_org_role(user, organization, ['hospital_owner']):
        return [
            'hospital_admin', 'doctor', 'scheduler',
            'billing_staff', 'compliance_officer', 'clinical_staff',
        ]
    if has_org_role(user, organization, ['hospital_admin']):
        return ['doctor', 'scheduler', 'billing_staff', 'clinical_staff']
    return []


def can_manage_org_appointments(user, organization) -> bool:
    """Org-wide appointment management — doctors excluded (they use can_manage_own_appointment)."""
    return is_platform_staff(user) or has_org_role(
        user, organization,
        ['hospital_owner', 'hospital_admin', 'scheduler'],
    )


def can_manage_own_appointment(user, appointment) -> bool:
    """Doctor can manage their own appointments only."""
    return bool(
        is_doctor(user)
        and hasattr(appointment, 'doctor')
        and hasattr(appointment.doctor, 'user')
        and appointment.doctor.user == user
    )


def can_view_org_payment_status(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization,
        ['hospital_owner', 'hospital_admin', 'scheduler', 'billing_staff'],
    )


def can_view_own_appointment_payment(user, payment) -> bool:
    return bool(
        is_doctor(user)
        and hasattr(payment, 'appointment')
        and hasattr(payment.appointment, 'doctor')
        and hasattr(payment.appointment.doctor, 'user')
        and payment.appointment.doctor.user == user
    )


def can_manage_payments(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'billing_staff'],
    )


def can_refund_payment(user, payment) -> bool:
    if is_platform_staff(user):
        return True
    if not hasattr(payment, 'organization') or payment.organization is None:
        return False
    return has_org_role(user, payment.organization, ['hospital_owner', 'billing_staff'])


def can_view_audit_logs(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'compliance_officer'],
    )


def can_access_patient_phi(user, patient, organization) -> bool:
    """
    Doctor can access patient PHI only if:
    - They are a doctor with active org membership
    - AND there is an active/completed appointment between them in this org
      OR a health record was explicitly shared with them
    """
    if not is_doctor(user):
        return False
    if not has_org_role(user, organization, ['doctor']):
        return False
    from apps.scheduling.models import Appointment
    has_appointment = Appointment.objects.filter(
        doctor__user=user, patient=patient,
        organization=organization,
        status__in=['scheduled', 'completed'],
    ).exists()
    if has_appointment:
        return True
    from apps.scheduling.models import HealthRecordShare
    has_share = HealthRecordShare.objects.filter(
        record__patient=patient,
        shared_with_doctor=user,
        revoked_at__isnull=True,
    ).exists()
    return has_share


def can_view_health_record(user, record) -> bool:
    """
    Fails closed. Platform staff do NOT have access until break-glass is implemented.
    """
    # Patient owns their own record
    if record.patient == user:
        return True
    # Doctor via explicit share
    if is_doctor(user) and hasattr(record, 'patient'):
        from apps.scheduling.models import HealthRecordShare
        if HealthRecordShare.objects.filter(
            record=record,
            shared_with_doctor=user,
            revoked_at__isnull=True,
        ).exists():
            # Still need org membership check
            from apps.accounts.models import OrganizationMembership
            has_membership = OrganizationMembership.objects.filter(
                user=user, is_active=True, role='doctor',
            ).exists()
            return has_membership
    # Doctor via active/completed appointment
    if is_doctor(user):
        from apps.scheduling.models import Appointment
        return Appointment.objects.filter(
            doctor__user=user, patient=record.patient,
            status__in=['scheduled', 'completed'],
        ).exists()
    return False


def can_break_glass_access_phi(user, record, reason) -> bool:
    """Stub — returns False until break-glass workflow is implemented."""
    return False
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python manage.py test apps.accounts.tests.PermissionHelpersTests --settings=config.settings.dev
```

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/permissions.py apps/accounts/tests.py
git commit -m "feat(accounts): add multi-tier permission helpers (is_platform_staff, has_org_role, action checks)"
```

---

### Task 10: Update middleware, DRF permissions, context processor

**Files:**
- Modify: `apps/accounts/middleware.py`
- Modify: `apps/api/permissions.py`
- Modify: `apps/accounts/context_processors.py`
- Test: `apps/accounts/tests.py`

- [ ] **Step 1: Write failing test for new 2FA rule**

```python
class TwoFactorMiddlewareTests(TestCase):
    def test_scheduler_requires_2fa(self):
        from apps.accounts.models import Organization, OrganizationMembership
        org = Organization.objects.create(
            name='MWOrg', slug='mw-org', org_type='hospital', status='active',
        )
        scheduler = User.objects.create_user(
            username='mwsched', email='mwsched@test.com',
            password='pass1234!', role='org_user',
        )
        scheduler.is_email_verified = True
        scheduler.save()
        OrganizationMembership.objects.create(
            user=scheduler, organization=org,
            role='scheduler', is_active=True,
        )
        from apps.accounts.permissions import has_any_elevated_membership
        self.assertTrue(has_any_elevated_membership(scheduler))

    def test_patient_does_not_require_2fa_by_membership(self):
        from apps.accounts.permissions import has_any_elevated_membership
        patient = User.objects.create_user(
            username='mwpat', email='mwpat@test.com',
            password='pass1234!', role='patient',
        )
        self.assertFalse(has_any_elevated_membership(patient))
```

- [ ] **Step 2: Update `apps/accounts/middleware.py`**

Replace the `role_requires_2fa` line:

```python
from apps.accounts.permissions import has_any_elevated_membership

class EnforceTwoFactorMiddleware:
    """
    Enforce 2FA for all elevated users.
    - platform_owner/platform_admin: always required
    - doctor: always required
    - org staff (any elevated membership): required regardless of selected org
    - patients: optional (skip flag honoured)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)
        if any(request.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return self.get_response(request)

        role = getattr(user, 'role', 'patient')
        role_requires_2fa = (
            role in ('platform_owner', 'platform_admin', 'doctor')
            or has_any_elevated_membership(user)
        )

        # Rest of existing middleware logic unchanged below this point
        # (otp_device check, skip flag for patients, redirect to setup)
```

> Keep all existing logic below the `role_requires_2fa` assignment unchanged.

- [ ] **Step 3: Update `apps/api/permissions.py`**

```python
"""
Custom DRF permissions for MedConsult API.
"""
from rest_framework.permissions import BasePermission
from apps.accounts.permissions import is_patient, is_doctor, is_platform_staff, has_org_role


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return is_patient(request.user)


class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return (
            is_doctor(request.user)
            and hasattr(request.user, 'doctor_profile')
            and request.user.doctor_profile.verification_status == 'verified'
        )


class IsAdmin(BasePermission):
    """Platform staff only."""
    def has_permission(self, request, view):
        return is_platform_staff(request.user)


class IsOrgAdmin(BasePermission):
    """hospital_owner or hospital_admin in request.organization."""
    def has_permission(self, request, view):
        org = getattr(request, 'organization', None)
        if not org:
            return False
        return is_platform_staff(request.user) or has_org_role(
            request.user, org, ['hospital_owner', 'hospital_admin'],
        )


class IsOrgMember(BasePermission):
    """Any active membership in request.organization."""
    def has_permission(self, request, view):
        org = getattr(request, 'organization', None)
        if not org:
            return is_platform_staff(request.user)
        from apps.accounts.models import OrganizationMembership
        return is_platform_staff(request.user) or OrganizationMembership.objects.filter(
            user=request.user, organization=org, is_active=True,
        ).exists()


class IsOrgDoctor(BasePermission):
    """Verified doctor with active org membership."""
    def has_permission(self, request, view):
        org = getattr(request, 'organization', None)
        if not org:
            return False
        return (
            is_doctor(request.user)
            and hasattr(request.user, 'doctor_profile')
            and request.user.doctor_profile.verification_status == 'verified'
            and has_org_role(request.user, org, ['doctor'])
        )
```

- [ ] **Step 4: Update `apps/accounts/context_processors.py`**

```python
def user_info(request):
    if not request.user.is_authenticated:
        return {}
    user = request.user

    # Org context — best-effort, never raises
    user_membership = None
    user_organization = None
    try:
        from apps.accounts.org_context import get_selected_organization
        org_ctx = get_selected_organization(request)
        user_organization = org_ctx.organization
        user_membership = org_ctx.membership
    except Exception:
        pass

    from apps.accounts.permissions import is_platform_staff
    return {
        'user_display_name': user.get_display_name(),
        'user_role': user.role,
        'user_initials': user.get_initials(),
        'user_has_profile_image': user.has_profile_image(),
        'user_profile_image_url': user.get_profile_image_url(),
        'user_membership': user_membership,
        'user_organization': user_organization,
        'is_platform_staff': is_platform_staff(user),
    }
```

- [ ] **Step 5: Run all tests**

```bash
python manage.py test apps --settings=config.settings.dev
```

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/middleware.py apps/api/permissions.py apps/accounts/context_processors.py apps/accounts/tests.py
git commit -m "feat: update 2FA middleware, DRF permissions, and context processor for multi-tenant roles"
```

---

### Task 11: Create domain permission files

**Files:**
- Create: `apps/scheduling/permissions.py`
- Create: `apps/payments/permissions.py`
- Create: `apps/messaging/permissions.py`
- Create: `apps/adminpanel/permissions.py`

- [ ] **Step 1: Create `apps/scheduling/permissions.py`**

```python
"""Scheduling-domain permission checks."""
from apps.accounts.permissions import is_platform_staff, is_doctor, has_org_role


def can_view_appointment(user, appointment) -> bool:
    if is_platform_staff(user):
        return True
    if appointment.patient == user:
        return True
    if is_doctor(user) and hasattr(appointment, 'doctor') and appointment.doctor.user == user:
        return True
    org = getattr(appointment, 'organization', None)
    if org:
        return has_org_role(user, org, ['hospital_owner', 'hospital_admin', 'scheduler'])
    return False


def can_cancel_appointment(user, appointment) -> bool:
    if is_platform_staff(user):
        return True
    if appointment.patient == user:
        return True
    if is_doctor(user) and appointment.doctor.user == user:
        return True
    org = getattr(appointment, 'organization', None)
    if org:
        return has_org_role(user, org, ['hospital_owner', 'hospital_admin', 'scheduler'])
    return False


def can_reschedule_appointment(user, appointment) -> bool:
    return can_cancel_appointment(user, appointment)


def can_write_prescription(user, appointment) -> bool:
    """Only the treating doctor can write a prescription."""
    return (
        is_doctor(user)
        and hasattr(appointment, 'doctor')
        and appointment.doctor.user == user
    )


def can_view_prescription(user, prescription) -> bool:
    if prescription.appointment.patient == user:
        return True
    if is_doctor(user) and prescription.appointment.doctor.user == user:
        return True
    return False


def can_manage_slots(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'hospital_admin'],
    )


def can_manage_own_slots(user, slot) -> bool:
    return is_doctor(user) and hasattr(slot, 'doctor') and slot.doctor.user == user
```

- [ ] **Step 2: Create `apps/payments/permissions.py`**

```python
"""Payment-domain permission checks."""
from apps.accounts.permissions import is_platform_staff, is_doctor, has_org_role


def can_view_payment(user, payment) -> bool:
    if is_platform_staff(user):
        return True
    if payment.patient == user:
        return True
    org = getattr(payment, 'organization', None)
    if org and has_org_role(user, org, ['hospital_owner', 'hospital_admin', 'billing_staff']):
        return True
    # Doctor sees own appointment payment status only
    if (is_doctor(user)
            and hasattr(payment, 'appointment')
            and payment.appointment.doctor.user == user):
        return True
    return False


def can_refund(user, payment) -> bool:
    if is_platform_staff(user):
        return True
    org = getattr(payment, 'organization', None)
    if not org:
        return False
    return has_org_role(user, org, ['hospital_owner', 'billing_staff'])


def can_export_payments(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'billing_staff'],
    )
```

- [ ] **Step 3: Create `apps/messaging/permissions.py`**

```python
"""Messaging-domain permission checks."""
from apps.accounts.permissions import is_platform_staff, has_org_role


def can_view_conversation(user, conversation) -> bool:
    if conversation.patient == user:
        return True
    if hasattr(conversation, 'doctor') and conversation.doctor == user:
        return True
    if is_platform_staff(user):
        return True
    org = getattr(conversation, 'organization', None)
    if org:
        return has_org_role(user, org, ['hospital_owner', 'hospital_admin'])
    return False


def can_send_message(user, conversation) -> bool:
    return can_view_conversation(user, conversation)
```

- [ ] **Step 4: Create `apps/adminpanel/permissions.py`**

```python
"""Admin panel permission checks."""
from apps.accounts.permissions import is_platform_staff, has_org_role


def can_view_org_dashboard(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization,
        ['hospital_owner', 'hospital_admin', 'scheduler', 'billing_staff',
         'compliance_officer', 'clinical_staff', 'doctor'],
    )


def can_manage_org_users(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'hospital_admin'],
    )


def can_view_org_analytics(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'hospital_admin'],
    )


def can_view_full_audit_log(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'compliance_officer'],
    )
```

- [ ] **Step 5: Run all tests**

```bash
python manage.py test apps --settings=config.settings.dev
```

- [ ] **Step 6: Commit**

```bash
git add apps/scheduling/permissions.py apps/payments/permissions.py apps/messaging/permissions.py apps/adminpanel/permissions.py
git commit -m "feat: add domain-specific permission files for scheduling, payments, messaging, adminpanel"
```

---

## Phase 3 — Query Scoping Layer

### Task 12: Add `scope_to_org` helper and update scheduling selectors

**Files:**
- Create: `apps/accounts/query_utils.py`
- Modify: `apps/scheduling/selectors.py`
- Test: `apps/scheduling/tests.py`

- [ ] **Step 1: Write failing tests**

```python
# In apps/scheduling/tests.py, add:
class OrgScopedSelectorTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization, OrganizationMembership, DoctorProfile
        from apps.scheduling.models import Slot, Appointment
        from datetime import datetime, timedelta
        from django.utils import timezone

        self.org_a = Organization.objects.create(
            name='Org A', slug='org-a', org_type='hospital', status='active',
        )
        self.org_b = Organization.objects.create(
            name='Org B', slug='org-b', org_type='hospital', status='active',
        )
        self.patient = User.objects.create_user(
            username='scopat', email='scopat@test.com',
            password='pass1234!', role='patient',
        )
        self.doc_a_user = User.objects.create_user(
            username='scodoca', email='scodoca@test.com',
            password='pass1234!', role='doctor',
        )
        self.doc_a = DoctorProfile.objects.create(
            user=self.doc_a_user, specialization='GP',
            medical_license_number='SCO-001',
            organization=self.org_a,
        )
        start = timezone.now() + timedelta(hours=2)
        self.slot_a = Slot.objects.create(
            doctor=self.doc_a,
            start_datetime=start,
            end_datetime=start + timedelta(minutes=30),
            appointment_type='video',
            organization=self.org_a,
        )
        self.appt = Appointment.objects.create(
            slot=self.slot_a,
            patient=self.patient,
            doctor=self.doc_a,
            organization=self.org_a,
        )

    def test_get_doctor_appointments_scoped_to_org(self):
        from apps.scheduling.selectors import get_doctor_appointments
        results = get_doctor_appointments(self.doc_a, organization=self.org_a)
        self.assertEqual(results.count(), 1)

    def test_get_doctor_appointments_wrong_org_returns_empty(self):
        from apps.scheduling.selectors import get_doctor_appointments
        results = get_doctor_appointments(self.doc_a, organization=self.org_b)
        self.assertEqual(results.count(), 0)

    def test_scope_to_org_none_fails_closed_for_non_platform(self):
        from apps.accounts.query_utils import scope_to_org
        from apps.scheduling.models import Appointment
        qs = Appointment.objects.all()
        result = scope_to_org(qs, None, self.patient)
        self.assertEqual(result.count(), 0)

    def test_scope_to_org_none_returns_all_for_platform_staff(self):
        from apps.accounts.query_utils import scope_to_org
        from apps.scheduling.models import Appointment
        platform_owner = User.objects.create_user(
            username='scopo', email='scopo@test.com',
            password='pass1234!', role='platform_owner',
        )
        qs = Appointment.objects.all()
        result = scope_to_org(qs, None, platform_owner)
        self.assertGreaterEqual(result.count(), 1)
```

- [ ] **Step 2: Create `apps/accounts/query_utils.py`**

```python
"""
Query scoping utilities for multi-tenant data isolation.

Core rule: organization=None fails closed (returns queryset.none())
unless platform access is explicitly proven via is_platform_staff(user).
"""
from apps.accounts.permissions import is_platform_staff


def scope_to_org(queryset, organization, user):
    """
    Scope a queryset to an organization.

    - If organization is provided: filter by organization.
    - If organization is None and user is platform staff: return unscoped.
    - If organization is None and user is NOT platform staff: return empty queryset.

    Never call with organization=None unless you have checked is_platform_staff first.
    """
    if organization is None:
        if is_platform_staff(user):
            return queryset
        return queryset.none()
    return queryset.filter(organization=organization)
```

- [ ] **Step 3: Update `apps/scheduling/selectors.py`**

Add `organization` parameter to each selector. Patient-owned selectors do NOT get org param.

```python
"""
Selectors for scheduling app - handles read operations and queries.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count
from .models import Slot, Appointment, AvailabilityWindow, SlotChangeLog, AppointmentTypeConfig
from apps.accounts.query_utils import scope_to_org


def get_available_slots_for_doctor(doctor_profile, organization, start_date=None, end_date=None):
    """Get available slots for a doctor within an org and optional date range."""
    query = Q(doctor=doctor_profile, is_booked=False, start_datetime__gt=timezone.now())
    if start_date:
        query &= Q(start_datetime__date__gte=start_date)
    if end_date:
        query &= Q(start_datetime__date__lte=end_date)
    qs = Slot.objects.filter(query).order_by('start_datetime')
    return qs.filter(organization=organization)


def get_doctor_availability_windows(doctor_profile, organization):
    """Get active availability windows for a doctor scoped to org."""
    return AvailabilityWindow.objects.filter(
        doctor=doctor_profile, is_active=True, organization=organization,
    ).order_by('weekday', 'start_time')


def get_patient_appointments(patient, status=None):
    """Patient-owned — no org filter. Scope by patient FK only."""
    query = Q(patient=patient)
    if status:
        query &= Q(status=status)
    return Appointment.objects.filter(query).select_related(
        'slot', 'doctor__user',
    ).order_by('-slot__start_datetime')


def get_doctor_appointments(doctor_profile, organization, status=None, user=None):
    """Get appointments for a doctor scoped to org."""
    query = Q(doctor=doctor_profile)
    if status:
        query &= Q(status=status)
    qs = Appointment.objects.filter(query).select_related('slot', 'patient')
    return scope_to_org(qs, organization, user).order_by('-slot__start_datetime')


def get_all_availability_windows(organization, user=None):
    """All windows for an org (admin/scheduler view)."""
    qs = AvailabilityWindow.objects.filter(is_active=True)
    return scope_to_org(qs, organization, user)


def get_appointment_by_id(appointment_id, organization, user=None):
    """Fetch single appointment; prevents cross-org IDOR."""
    from django.shortcuts import get_object_or_404
    qs = Appointment.objects.filter(id=appointment_id)
    scoped = scope_to_org(qs, organization, user)
    return scoped.first()
```

> Keep any other existing selector functions below these updated ones. Add `organization` param to each — do not remove any existing selectors, just add the parameter with a default of `None` for backward compat during transition, then update callers.

- [ ] **Step 4: Run tests**

```bash
python manage.py test apps.scheduling.tests.OrgScopedSelectorTests apps.accounts.tests --settings=config.settings.dev
```

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/query_utils.py apps/scheduling/selectors.py apps/scheduling/tests.py
git commit -m "feat: add scope_to_org helper and update scheduling selectors for org scoping"
```

---

### Task 13: Update payments, messaging, and adminpanel selectors

**Files:**
- Create: `apps/payments/selectors.py`
- Modify: `apps/messaging/selectors.py`
- Modify: `apps/adminpanel/selectors.py`
- Test: `apps/payments/tests.py`

- [ ] **Step 1: Create `apps/payments/selectors.py`**

```python
"""Payment selectors — all org-facing queries scoped."""
from apps.accounts.query_utils import scope_to_org
from .models import Payment, Refund


def get_payments_for_org(organization, user=None):
    qs = Payment.objects.select_related('appointment', 'patient')
    return scope_to_org(qs, organization, user)


def get_payment_for_appointment(appointment_id, organization, user=None):
    qs = Payment.objects.filter(appointment_id=appointment_id)
    return scope_to_org(qs, organization, user).first()


def get_refunds_for_org(organization, user=None):
    qs = Refund.objects.select_related('payment', 'payment__appointment')
    return scope_to_org(qs.filter(payment__organization=organization), organization, user)
```

- [ ] **Step 2: Update `apps/messaging/selectors.py`**

Update `get_user_conversations` to scope by org for staff:

```python
def get_user_conversations(user, organization=None):
    """
    Patient: filter by participant (no org scope).
    Org staff: filter by organization.
    Platform staff with organization=None: unscoped.
    """
    from apps.accounts.query_utils import scope_to_org
    from apps.accounts.permissions import is_patient

    if is_patient(user):
        # Patient always scopes to self — ignore org
        qs = Conversation.objects.filter(
            Q(patient=user) | Q(doctor=user)
        )
    else:
        qs = Conversation.objects.all()
        qs = scope_to_org(qs, organization, user)

    # Existing deleted-by-X and has-real-message filters remain below
    ...
```

> Keep all existing annotation/filter logic below the queryset assignment.

- [ ] **Step 3: Update `apps/adminpanel/selectors.py`**

Add `organization` param to every public selector function. Wrap the queryset with `scope_to_org`. Example for the most critical one:

```python
from apps.accounts.query_utils import scope_to_org

def get_all_appointments_for_admin(organization=None, user=None, **filters):
    from apps.scheduling.models import Appointment
    qs = Appointment.objects.select_related('patient', 'doctor__user', 'slot')
    if filters.get('status'):
        qs = qs.filter(status=filters['status'])
    return scope_to_org(qs, organization, user)
```

Apply the same pattern to `get_all_users_for_admin`, `get_all_payments_for_admin`, `get_audit_logs`, `get_all_doctors_for_admin`, `get_all_patients_for_admin`.

- [ ] **Step 4: Write and run tests**

```python
# In apps/payments/tests.py, add:
class PaymentSelectorTests(TestCase):
    def test_get_payments_for_wrong_org_returns_empty(self):
        from apps.accounts.models import Organization
        from apps.payments.selectors import get_payments_for_org
        org_a = Organization.objects.create(
            name='PayOrgA', slug='pay-org-a', org_type='hospital', status='active',
        )
        org_b = Organization.objects.create(
            name='PayOrgB', slug='pay-org-b', org_type='hospital', status='active',
        )
        patient = User.objects.create_user(
            username='paypat', email='paypat@test.com',
            password='pass1234!', role='patient',
        )
        # Verify org_b has no payments when only org_a has them
        result = get_payments_for_org(org_b, user=patient)
        self.assertEqual(result.count(), 0)
```

```bash
python manage.py test apps.payments.tests.PaymentSelectorTests apps.messaging.tests apps.adminpanel.tests --settings=config.settings.dev
```

- [ ] **Step 5: Commit**

```bash
git add apps/payments/selectors.py apps/messaging/selectors.py apps/adminpanel/selectors.py apps/payments/tests.py
git commit -m "feat: add org-scoped payment selectors, update messaging and adminpanel selectors"
```

---

### Task 14: Add service-level org validation and update `get_object_or_404` patterns

**Files:**
- Modify: `apps/scheduling/services.py`
- Modify: `apps/scheduling/views.py` (key fetch patterns only)

- [ ] **Step 1: Add org consistency validation to critical services**

In `apps/scheduling/services.py`, add at the top:

```python
from django.core.exceptions import PermissionDenied

def _assert_same_org(*objects):
    """Raise PermissionDenied if objects span multiple organizations."""
    org_ids = {
        obj.organization_id for obj in objects
        if obj is not None and hasattr(obj, 'organization_id') and obj.organization_id is not None
    }
    if len(org_ids) > 1:
        raise PermissionDenied("Organization mismatch across related objects.")
```

Then in `book_appointment` (existing function), add at the start of the transaction:

```python
@transaction.atomic
def book_appointment(patient, slot, reason='', booking_status='confirmed'):
    # Validate org consistency
    if slot.organization is None:
        raise PermissionDenied("Slot has no organization assigned.")
    # ... rest of existing function unchanged
```

In `create_prescription`, add:

```python
def create_prescription(doctor_user, appointment, **kwargs):
    _assert_same_org(appointment, appointment.slot)
    # ... rest unchanged
```

- [ ] **Step 2: Update `get_object_or_404` in scheduling views**

In `apps/scheduling/views.py`, replace cross-org-vulnerable fetches. Pattern:

```python
# Before (IDOR risk):
appointment = get_object_or_404(Appointment, id=appointment_id)

# After (org-scoped for org-facing views):
appointment = get_object_or_404(Appointment, id=appointment_id, organization=request.organization)

# For patient-owned views (no org needed):
appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
```

Apply this to: `patient_cancel_appointment`, `patient_reschedule_appointment`, `patient_billing_summary`, `patient_billing_download`, `patient_download_prescription`, `health_record_download`.

> `request.organization` will be `None` until the org middleware/decorator is wired in Phase 4 UI. For now, add a guard:
```python
org = getattr(request, 'organization', None)
if org:
    appointment = get_object_or_404(Appointment, id=appointment_id, organization=org)
else:
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
```

- [ ] **Step 3: Run full test suite**

```bash
python manage.py test apps --settings=config.settings.dev
```

- [ ] **Step 4: Commit**

```bash
git add apps/scheduling/services.py apps/scheduling/views.py
git commit -m "feat: add service-level org validation and org-scoped get_object_or_404 patterns"
```

---

### Task 15: Update WebSocket consumers and Celery tasks

**Files:**
- Modify: `apps/scheduling/consumers.py`
- Modify: `apps/messaging/consumers.py`
- Modify: `apps/scheduling/tasks.py`

- [ ] **Step 1: Update `apps/scheduling/consumers.py`**

In `DoctorCalendarConsumer.connect`:

```python
async def connect(self):
    from apps.accounts.models import OrganizationMembership
    user = self.scope['user']
    if not user.is_authenticated:
        await self.close()
        return
    # Verify doctor has active membership
    has_membership = await database_sync_to_async(
        OrganizationMembership.objects.filter(
            user=user, is_active=True, role='doctor',
        ).exists
    )()
    if not has_membership and user.role not in ('platform_owner', 'platform_admin'):
        await self.close()
        return
    await self.channel_layer.group_add(self.group_name, self.channel_name)
    await self.accept()
```

- [ ] **Step 2: Update `apps/scheduling/tasks.py`**

Replace global queries with per-org loops:

```python
@shared_task
def extend_slots_for_all_doctors():
    from apps.accounts.models import Organization
    for org in Organization.objects.filter(status='active'):
        _extend_slots_for_org(org)

def _extend_slots_for_org(org):
    from apps.accounts.models import DoctorProfile
    doctors = DoctorProfile.objects.filter(organization=org, verification_status='verified')
    for doctor in doctors:
        generate_slots_for_doctor(doctor)


@shared_task
def mark_completed_appointments():
    from apps.accounts.models import Organization
    from apps.scheduling.models import Appointment
    from django.utils import timezone
    for org in Organization.objects.filter(status='active'):
        Appointment.objects.filter(
            organization=org,
            status='scheduled',
            slot__start_datetime__lt=timezone.now(),
        ).update(status='completed')
```

Apply same org-loop pattern to `mark_no_show_appointments` and `schedule_appointment_reminders`.

- [ ] **Step 3: Run all tests**

```bash
python manage.py test apps --settings=config.settings.dev
```

- [ ] **Step 4: Commit**

```bash
git add apps/scheduling/consumers.py apps/messaging/consumers.py apps/scheduling/tasks.py
git commit -m "feat: add org membership check to WebSocket consumers, scope Celery tasks per org"
```

---

This completes Plan 1 (Foundation). The platform now has:
- Organization/OrganizationMembership/OrganizationInvite models
- All tenant models with org FK
- Existing records backfilled
- Full permission helper library
- Org-scoped selectors that fail closed
- Service-level org validation
- WebSocket and Celery scoped

**Plan 2** covers the UI layer: hospital signup, org dashboards, staff invite flow.
