# Hospital-Specific User Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every hospital its own internal user roster — each `OrganizationMembership` gets a unique `hospital_user_id` (e.g. `CGH-DOC-0007`), doctors get an org-scoped `ProviderOrganizationProfile`, and both hospital staff and platform admins get drill-down UI: Organization → Members → Member Detail → Provider Profile → Appointments.

**Architecture:** Three layers — (1) model/migration, (2) service layer that centralises membership creation and wires ID generation + profile creation, (3) two UI paths (org-facing at `/org/<slug>/staff/<id>/` and platform-admin-facing at `/internal/organizations/<id>/members/<id>/`). No new app is created; models stay in `accounts`, services stay in `organizations`.

**Tech Stack:** Django 4.2, PostgreSQL, pytest-django, existing `apps/accounts`, `apps/organizations`, `apps/adminpanel`

---

## File Map

| Action | File |
|--------|------|
| Modify | `apps/accounts/models.py` — add fields to `OrganizationMembership`, add `ProviderOrganizationProfile` |
| Create | `apps/accounts/migrations/0021_membership_hospital_user_id.py` |
| Create | `apps/accounts/migrations/0022_provider_organization_profile.py` |
| Create | `apps/accounts/migrations/0023_backfill_hospital_user_id.py` |
| Modify | `apps/organizations/services.py` — add `generate_hospital_user_id`, `create_membership` |
| Modify | `apps/organizations/views.py` — use `create_membership` in `accept_invite`; add `member_detail` view |
| Modify | `apps/organizations/urls.py` — add `staff/<int:member_id>/` route |
| Create | `templates/organizations/member_detail.html` |
| Modify | `templates/organizations/staff_list.html` — link rows to member detail |
| Modify | `apps/adminpanel/views.py` — add `org_member_detail` view |
| Modify | `apps/adminpanel/urls.py` — add `organizations/<int:org_id>/members/<int:membership_id>/` route |
| Create | `apps/adminpanel/templates/adminpanel/organizations/member_detail.html` |
| Modify | `apps/adminpanel/templates/adminpanel/organizations/detail.html` — link member rows |
| Modify | `apps/accounts/tests.py` — membership ID + ProviderOrganizationProfile tests |
| Modify | `apps/organizations/tests.py` — member detail view tests |

---

## Task 1: Extend OrganizationMembership + Add ProviderOrganizationProfile

**Files:**
- Modify: `apps/accounts/models.py`
- Create: `apps/accounts/migrations/0021_membership_hospital_user_id.py`
- Create: `apps/accounts/migrations/0022_provider_organization_profile.py`

- [ ] **Step 1: Add fields to OrganizationMembership**

Open `apps/accounts/models.py`. Find the `OrganizationMembership` class (line ~441). After the `updated_at` field and before the `class Meta` block, add two new fields:

```python
    hospital_user_id = models.CharField(max_length=50, blank=True, default='')
    display_name = models.CharField(max_length=150, blank=True, default='')
```

Also add a `UniqueConstraint` for `hospital_user_id` per org. The existing `Meta` block looks like:

```python
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
```

Replace it with:

```python
    class Meta:
        db_table = 'organization_memberships'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'organization'],
                name='unique_user_organization_membership',
            ),
            models.UniqueConstraint(
                fields=['organization', 'hospital_user_id'],
                condition=models.Q(hospital_user_id__gt=''),
                name='unique_hospital_user_id_per_org',
            ),
        ]
        indexes = [
            models.Index(fields=['organization', 'role', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
```

- [ ] **Step 2: Add ProviderOrganizationProfile model**

In `apps/accounts/models.py`, after the `OrganizationInvite` class, add:

```python
class ProviderOrganizationProfile(models.Model):
    """Org-scoped doctor profile. One per doctor per organization."""
    doctor = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='provider_org_profiles',
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='provider_profiles',
    )
    membership = models.OneToOneField(
        OrganizationMembership, on_delete=models.CASCADE,
        related_name='provider_profile',
    )
    provider_id = models.CharField(max_length=50, blank=True, default='')
    title = models.CharField(max_length=100, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    specialization = models.CharField(max_length=100, blank=True, default='')
    consultation_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
    )
    is_accepting_patients = models.BooleanField(default=True)
    is_verified_for_org = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        'User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='org_verified_providers',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'provider_organization_profiles'
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'organization'],
                name='unique_provider_per_org',
            ),
            models.UniqueConstraint(
                fields=['organization', 'provider_id'],
                condition=models.Q(provider_id__gt=''),
                name='unique_provider_id_per_org',
            ),
        ]

    def __str__(self):
        return f"Dr. {self.doctor.get_display_name()} @ {self.organization.name}"
```

- [ ] **Step 3: Generate migrations**

```bash
python manage.py makemigrations accounts --name membership_hospital_user_id --settings=config.settings.dev
python manage.py makemigrations accounts --name provider_organization_profile --settings=config.settings.dev
```

Expected: two new migration files created in `apps/accounts/migrations/`.

- [ ] **Step 4: Apply migrations**

```bash
python manage.py migrate --settings=config.settings.dev
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/models.py apps/accounts/migrations/
git commit -m "feat(identity): add hospital_user_id + ProviderOrganizationProfile models"
```

---

## Task 2: Generate hospital_user_id + Backfill Existing Memberships

**Files:**
- Modify: `apps/organizations/services.py` — add `generate_hospital_user_id` and `create_membership`
- Create: `apps/accounts/migrations/0023_backfill_hospital_user_id.py` (data migration)

- [ ] **Step 1: Write failing test for ID generation**

In `apps/accounts/tests.py`, add:

```python
from apps.organizations.services import generate_hospital_user_id

class HospitalUserIdTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='City General',
            slug='city-general',
            org_type='hospital',
            status='active',
        )
        self.user = User.objects.create_user(
            username='doc1', email='doc1@test.com',
            password='pass', role='doctor',
        )

    def test_generate_creates_prefixed_id(self):
        hid = generate_hospital_user_id(self.org, 'doctor')
        self.assertRegex(hid, r'^CIT-DOC-\d{4}$')

    def test_generate_different_roles(self):
        hid_owner = generate_hospital_user_id(self.org, 'hospital_owner')
        self.assertIn('-OWN-', hid_owner)
        hid_sched = generate_hospital_user_id(self.org, 'scheduler')
        self.assertIn('-SCH-', hid_sched)

    def test_sequence_increments(self):
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org,
            role='doctor', hospital_user_id='CIT-DOC-0001',
        )
        user2 = User.objects.create_user(
            username='doc2', email='doc2@test.com',
            password='pass', role='doctor',
        )
        hid = generate_hospital_user_id(self.org, 'doctor')
        self.assertEqual(hid, 'CIT-DOC-0002')
```

Run: `python manage.py test apps.accounts.tests.HospitalUserIdTest --settings=config.settings.dev`
Expected: FAIL — `ImportError: cannot import name 'generate_hospital_user_id'`

- [ ] **Step 2: Implement generate_hospital_user_id and create_membership**

In `apps/organizations/services.py`, add after the imports and before `register_organization`:

```python
_ROLE_CODE = {
    'hospital_owner': 'OWN',
    'hospital_admin': 'ADM',
    'doctor': 'DOC',
    'scheduler': 'SCH',
    'billing_staff': 'BIL',
    'compliance_officer': 'CMP',
    'clinical_staff': 'CLN',
    'platform_owner': 'PLT',
    'platform_admin': 'PLA',
}


def generate_hospital_user_id(organization, role: str) -> str:
    """
    Returns a unique ID like CIT-DOC-0007 scoped to the given organization.
    Prefix = first 3 chars of slug (uppercased, no hyphens).
    Sequence = existing membership count in org + 1.
    """
    from apps.accounts.models import OrganizationMembership
    prefix = organization.slug.replace('-', '')[:3].upper()
    role_code = _ROLE_CODE.get(role, 'USR')
    count = OrganizationMembership.objects.filter(organization=organization).count() + 1
    return f"{prefix}-{role_code}-{count:04d}"


@transaction.atomic
def create_membership(user, organization, role: str, invited_by=None, accepted_at=None) -> 'OrganizationMembership':
    """
    Create (or reactivate) a membership with auto-generated hospital_user_id.
    Also creates ProviderOrganizationProfile if role == 'doctor'.
    """
    from apps.accounts.models import OrganizationMembership, ProviderOrganizationProfile
    from django.utils import timezone

    existing = OrganizationMembership.objects.filter(
        user=user, organization=organization,
    ).first()

    if existing:
        existing.role = role
        existing.is_active = True
        if not existing.hospital_user_id:
            existing.hospital_user_id = generate_hospital_user_id(organization, role)
        existing.save(update_fields=['role', 'is_active', 'hospital_user_id'])
        membership = existing
    else:
        hospital_user_id = generate_hospital_user_id(organization, role)
        membership = OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=role,
            is_active=True,
            hospital_user_id=hospital_user_id,
            invited_by=invited_by,
            invited_at=timezone.now() if invited_by else None,
            accepted_at=accepted_at,
        )

    if role == 'doctor':
        ProviderOrganizationProfile.objects.get_or_create(
            doctor=user,
            organization=organization,
            defaults={
                'membership': membership,
                'provider_id': membership.hospital_user_id,
                'specialization': getattr(
                    getattr(user, 'doctorprofile', None), 'specialization', ''
                ) or '',
            },
        )

    return membership
```

- [ ] **Step 3: Update register_organization to use create_membership**

In `apps/organizations/services.py`, replace the `OrganizationMembership.objects.create(...)` call inside `register_organization`:

**Before:**
```python
    OrganizationMembership.objects.create(
        user=user,
        organization=org,
        role='hospital_owner',
        is_active=True,
    )
```

**After:**
```python
    create_membership(user=user, organization=org, role='hospital_owner')
```

- [ ] **Step 4: Update accept_invite to use create_membership**

In `apps/organizations/views.py`, inside the `accept_invite` view, replace the `OrganizationMembership.objects.create` + `except IntegrityError` block:

**Before:**
```python
        from apps.accounts.models import OrganizationMembership
        from django.db import IntegrityError
        try:
            OrganizationMembership.objects.create(
                user=request.user,
                organization=invite.organization,
                role=invite.role,
                is_active=True,
            )
        except IntegrityError:
            # Already a member — update role
            OrganizationMembership.objects.filter(
                user=request.user, organization=invite.organization,
            ).update(role=invite.role, is_active=True)
```

**After:**
```python
        from apps.organizations.services import create_membership
        from django.utils import timezone
        create_membership(
            user=request.user,
            organization=invite.organization,
            role=invite.role,
            invited_by=invite.invited_by,
            accepted_at=timezone.now(),
        )
```

- [ ] **Step 5: Run the ID generation tests**

```bash
python manage.py test apps.accounts.tests.HospitalUserIdTest --settings=config.settings.dev
```

Expected: PASS (3 tests).

- [ ] **Step 6: Write the data migration to backfill existing memberships**

Create `apps/accounts/migrations/0023_backfill_hospital_user_id.py` manually (the migration number may differ — use the next number after whatever `makemigrations` created in Task 1):

```python
from django.db import migrations


def _role_code(role):
    return {
        'hospital_owner': 'OWN', 'hospital_admin': 'ADM', 'doctor': 'DOC',
        'scheduler': 'SCH', 'billing_staff': 'BIL', 'compliance_officer': 'CMP',
        'clinical_staff': 'CLN', 'platform_owner': 'PLT', 'platform_admin': 'PLA',
    }.get(role, 'USR')


def backfill_hospital_user_ids(apps, schema_editor):
    OrganizationMembership = apps.get_model('accounts', 'OrganizationMembership')
    Organization = apps.get_model('accounts', 'Organization')

    for org in Organization.objects.all():
        memberships = OrganizationMembership.objects.filter(
            organization=org, hospital_user_id='',
        ).order_by('created_at')
        prefix = org.slug.replace('-', '')[:3].upper()
        # Start sequence after any already-assigned IDs
        count = OrganizationMembership.objects.filter(
            organization=org,
        ).exclude(hospital_user_id='').count()
        for m in memberships:
            count += 1
            m.hospital_user_id = f"{prefix}-{_role_code(m.role)}-{count:04d}"
            m.save(update_fields=['hospital_user_id'])


class Migration(migrations.Migration):
    dependencies = [
        # Replace 0022_provider_organization_profile with the actual last migration name
        ('accounts', '0022_provider_organization_profile'),
    ]

    operations = [
        migrations.RunPython(
            backfill_hospital_user_ids,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
```

> **Note:** Check the actual migration filenames created in Task 1 (`ls apps/accounts/migrations/` sorted) and make the dependency point to the correct last migration.

- [ ] **Step 7: Apply the data migration**

```bash
python manage.py migrate --settings=config.settings.dev
```

Expected: no errors. Verify in Django shell:

```bash
python manage.py shell --settings=config.settings.dev -c "
from apps.accounts.models import OrganizationMembership
for m in OrganizationMembership.objects.all():
    print(m.hospital_user_id, m.user.email, m.organization.name)
"
```

Expected: every membership prints a non-empty `hospital_user_id`.

- [ ] **Step 8: Commit**

```bash
git add apps/organizations/services.py apps/organizations/views.py \
        apps/accounts/migrations/ apps/accounts/tests.py
git commit -m "feat(identity): generate hospital_user_id on membership creation, backfill existing"
```

---

## Task 3: Hospital-Facing Member Detail View

**Files:**
- Modify: `apps/organizations/urls.py`
- Modify: `apps/organizations/views.py` — add `member_detail`
- Create: `templates/organizations/member_detail.html`
- Modify: `templates/organizations/staff_list.html` — link rows

- [ ] **Step 1: Write failing test**

In `apps/organizations/tests.py`, add:

```python
from apps.accounts.models import User, Organization, OrganizationMembership, ProviderOrganizationProfile
from django.test import TestCase, Client
from django.urls import reverse


class MemberDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(
            name='City General', slug='city-general',
            org_type='hospital', status='active',
        )
        self.owner = User.objects.create_user(
            username='owner1', email='owner@test.com',
            password='pass', role='org_user',
        )
        self.membership = OrganizationMembership.objects.create(
            user=self.owner, organization=self.org,
            role='hospital_owner', is_active=True,
            hospital_user_id='CIT-OWN-0001',
        )
        self.client.force_login(self.owner)

    def test_member_detail_loads(self):
        url = reverse('organizations:member_detail', kwargs={
            'org_slug': self.org.slug,
            'member_id': self.membership.id,
        })
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CIT-OWN-0001')

    def test_outsider_gets_403(self):
        outsider = User.objects.create_user(
            username='out1', email='out@test.com',
            password='pass', role='patient',
        )
        self.client.force_login(outsider)
        url = reverse('organizations:member_detail', kwargs={
            'org_slug': self.org.slug,
            'member_id': self.membership.id,
        })
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
```

Run: `python manage.py test apps.organizations.tests.MemberDetailViewTest --settings=config.settings.dev`
Expected: FAIL — `NoReverseMatch`

- [ ] **Step 2: Add URL**

In `apps/organizations/urls.py`, add after the `staff/<int:member_id>/deactivate/` line:

```python
    path('<slug:org_slug>/staff/<int:member_id>/', views.member_detail, name='member_detail'),
```

- [ ] **Step 3: Add member_detail view**

In `apps/organizations/views.py`, add after the `deactivate_member` function:

```python
@login_required
def member_detail(request, org_slug, member_id):
    from apps.accounts.models import Organization, OrganizationMembership, ProviderOrganizationProfile
    from apps.accounts.permissions import is_platform_staff, get_membership
    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        raise Http404

    # Allow platform staff or active members of this org
    if not is_platform_staff(request.user):
        viewer_membership = get_membership(request.user, org)
        if not viewer_membership or not viewer_membership.is_active:
            raise PermissionDenied

    try:
        membership = OrganizationMembership.objects.select_related(
            'user', 'organization', 'invited_by',
        ).get(id=member_id, organization=org)
    except OrganizationMembership.DoesNotExist:
        raise Http404

    provider_profile = None
    if membership.role == 'doctor':
        provider_profile = ProviderOrganizationProfile.objects.filter(
            membership=membership,
        ).first()

    return render(request, 'organizations/member_detail.html', {
        'org': org,
        'membership': membership,
        'member': membership.user,
        'provider_profile': provider_profile,
    })
```

- [ ] **Step 4: Create member_detail.html template**

Create `templates/organizations/member_detail.html`:

```html
{% extends "layouts/app.html" %}
{% block title %}{{ member.get_display_name }} — {{ org.name }}{% endblock %}
{% block content %}
<div class="max-w-3xl mx-auto px-4 py-8">
  <div class="mb-6">
    <a href="{% url 'organizations:staff_list' org.slug %}"
       class="text-blue-600 hover:underline text-sm">← Staff List</a>
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mt-2">
      {{ member.get_display_name }}
    </h1>
    <p class="text-sm text-gray-500">{{ org.name }}</p>
  </div>

  <!-- Identity Card -->
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6 mb-6">
    <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Identity</h2>
    <dl class="grid grid-cols-2 gap-4">
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Hospital User ID</dt>
        <dd class="mt-1 text-gray-900 dark:text-white font-mono font-medium">
          {{ membership.hospital_user_id|default:"—" }}
        </dd>
      </div>
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Role</dt>
        <dd class="mt-1">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
            bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
            {{ membership.get_role_display }}
          </span>
        </dd>
      </div>
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Email</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">{{ member.email }}</dd>
      </div>
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Status</dt>
        <dd class="mt-1">
          {% if membership.is_active %}
          <span class="text-emerald-600 dark:text-emerald-400 text-sm font-medium">Active</span>
          {% else %}
          <span class="text-red-600 dark:text-red-400 text-sm font-medium">Inactive</span>
          {% endif %}
        </dd>
      </div>
      {% if membership.display_name %}
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Display Name</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">{{ membership.display_name }}</dd>
      </div>
      {% endif %}
      {% if membership.accepted_at %}
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Joined</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">{{ membership.accepted_at|date:"M d, Y" }}</dd>
      </div>
      {% endif %}
      {% if membership.invited_by %}
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Invited By</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">{{ membership.invited_by.get_display_name }}</dd>
      </div>
      {% endif %}
    </dl>
  </div>

  <!-- Provider Profile (doctors only) -->
  {% if provider_profile %}
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Provider Profile</h2>
      {% if provider_profile.is_verified_for_org %}
      <span class="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
        </svg>
        Org-Verified
      </span>
      {% endif %}
    </div>
    <dl class="grid grid-cols-2 gap-4">
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Provider ID</dt>
        <dd class="mt-1 text-gray-900 dark:text-white font-mono">{{ provider_profile.provider_id|default:"—" }}</dd>
      </div>
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Accepting Patients</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">
          {% if provider_profile.is_accepting_patients %}Yes{% else %}No{% endif %}
        </dd>
      </div>
      {% if provider_profile.title %}
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Title</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">{{ provider_profile.title }}</dd>
      </div>
      {% endif %}
      {% if provider_profile.department %}
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Department</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">{{ provider_profile.department }}</dd>
      </div>
      {% endif %}
      {% if provider_profile.specialization %}
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Specialization</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">{{ provider_profile.specialization }}</dd>
      </div>
      {% endif %}
      <div>
        <dt class="text-xs text-gray-500 uppercase tracking-wide">Org Consultation Fee</dt>
        <dd class="mt-1 text-gray-900 dark:text-white">${{ provider_profile.consultation_fee }}</dd>
      </div>
    </dl>
  </div>
  {% elif membership.role == 'doctor' %}
  <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-sm text-amber-800 dark:text-amber-300">
    No provider profile yet. Profile is auto-created when the doctor accepts an invite.
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Update staff_list.html to link member rows**

Open `templates/organizations/staff_list.html`. Find where member rows are rendered (each `<tr>` or `<li>` with member info). Add a "View" link pointing to `member_detail`:

Find the table row or list item that shows the member name/role. It will look something like:

```html
<td ...>{{ m.user.get_display_name }}</td>
```

Add a "View" link column or wrap the name in a link:

```html
<a href="{% url 'organizations:member_detail' org.slug m.id %}"
   class="text-blue-600 hover:underline font-medium">
  {{ m.user.get_display_name }}
</a>
```

Also surface `hospital_user_id` in the staff list table. Add a column header `ID` and in each row add:

```html
<td class="px-4 py-3 font-mono text-xs text-gray-500">{{ m.hospital_user_id|default:"—" }}</td>
```

- [ ] **Step 6: Run tests**

```bash
python manage.py test apps.organizations.tests.MemberDetailViewTest --settings=config.settings.dev
```

Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add apps/organizations/urls.py apps/organizations/views.py \
        templates/organizations/member_detail.html \
        templates/organizations/staff_list.html
git commit -m "feat(identity): hospital-facing member detail view with provider profile"
```

---

## Task 4: Platform-Admin Member Detail View

**Files:**
- Modify: `apps/adminpanel/urls.py`
- Modify: `apps/adminpanel/views.py` — add `org_member_detail`
- Create: `apps/adminpanel/templates/adminpanel/organizations/member_detail.html`
- Modify: `apps/adminpanel/templates/adminpanel/organizations/detail.html` — link rows
- Modify: `apps/accounts/tests.py` — admin view tests

- [ ] **Step 1: Write failing test**

In `apps/accounts/tests.py`, add:

```python
class AdminMemberDetailTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(
            name='City General', slug='city-general',
            org_type='hospital', status='active',
        )
        self.platform_owner = User.objects.create_user(
            username='platowner', email='plat@test.com',
            password='pass', role='platform_owner',
        )
        self.doctor_user = User.objects.create_user(
            username='doc99', email='doc99@test.com',
            password='pass', role='doctor',
        )
        self.membership = OrganizationMembership.objects.create(
            user=self.doctor_user, organization=self.org,
            role='doctor', is_active=True,
            hospital_user_id='CIT-DOC-0001',
        )
        self.client.force_login(self.platform_owner)

    def test_admin_member_detail_loads(self):
        from django.urls import reverse
        url = reverse('adminpanel:org_member_detail', kwargs={
            'org_id': self.org.id,
            'membership_id': self.membership.id,
        })
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CIT-DOC-0001')

    def test_non_platform_staff_gets_403(self):
        from django.urls import reverse
        patient = User.objects.create_user(
            username='pat1', email='pat1@test.com',
            password='pass', role='patient',
        )
        self.client.force_login(patient)
        url = reverse('adminpanel:org_member_detail', kwargs={
            'org_id': self.org.id,
            'membership_id': self.membership.id,
        })
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)  # redirected by _platform_forbidden
```

Run: `python manage.py test apps.accounts.tests.AdminMemberDetailTest --settings=config.settings.dev`
Expected: FAIL — `NoReverseMatch`

- [ ] **Step 2: Add URL to adminpanel**

In `apps/adminpanel/urls.py`, add after the existing `organizations/<int:org_id>/needs-info/` line:

```python
    path('organizations/<int:org_id>/members/<int:membership_id>/', views.org_member_detail, name='org_member_detail'),
```

- [ ] **Step 3: Add org_member_detail view**

In `apps/adminpanel/views.py`, add after the `organization_needs_info` function:

```python
@login_required
def org_member_detail(request, org_id, membership_id):
    _platform_forbidden(request)
    from apps.accounts.models import Organization, OrganizationMembership, ProviderOrganizationProfile
    from apps.scheduling.models import Appointment

    org = get_object_or_404(Organization, id=org_id)
    membership = get_object_or_404(
        OrganizationMembership.objects.select_related('user', 'invited_by'),
        id=membership_id, organization=org,
    )

    provider_profile = None
    appointments = []
    if membership.role == 'doctor':
        provider_profile = ProviderOrganizationProfile.objects.filter(
            membership=membership,
        ).first()
        appointments = Appointment.objects.filter(
            slot__doctor=membership.user,
            organization=org,
        ).select_related('patient', 'slot').order_by('-slot__start_time')[:10]

    return render(request, 'adminpanel/organizations/member_detail.html', {
        'org': org,
        'membership': membership,
        'member': membership.user,
        'provider_profile': provider_profile,
        'recent_appointments': appointments,
    })
```

- [ ] **Step 4: Create the admin member_detail template**

Create `apps/adminpanel/templates/adminpanel/organizations/member_detail.html`:

```html
{% extends "adminpanel/base.html" %}
{% block title %}{{ member.get_display_name }} — {{ org.name }} — Admin{% endblock %}
{% block content %}
<div class="p-6 max-w-4xl">
  <div class="flex items-center gap-3 mb-6">
    <a href="{% url 'adminpanel:organization_detail' org.id %}"
       class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
    </a>
    <div>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ member.get_display_name }}</h1>
      <p class="text-sm text-gray-500">{{ org.name }}</p>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
    <!-- Identity -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Identity</h2>
      <dl class="space-y-3">
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Hospital User ID</dt>
          <dd class="text-sm font-mono font-medium text-gray-900 dark:text-white">
            {{ membership.hospital_user_id|default:"—" }}
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Org Role</dt>
          <dd>
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
              bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
              {{ membership.get_role_display }}
            </span>
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Global Role</dt>
          <dd class="text-sm text-gray-900 dark:text-white">{{ member.role }}</dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Email</dt>
          <dd class="text-sm text-gray-900 dark:text-white">{{ member.email }}</dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Membership Status</dt>
          <dd class="text-sm {% if membership.is_active %}text-emerald-600 dark:text-emerald-400{% else %}text-red-600 dark:text-red-400{% endif %}">
            {% if membership.is_active %}Active{% else %}Inactive{% endif %}
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Account Active</dt>
          <dd class="text-sm {% if member.is_active %}text-emerald-600 dark:text-emerald-400{% else %}text-red-600 dark:text-red-400{% endif %}">
            {% if member.is_active %}Yes{% else %}No{% endif %}
          </dd>
        </div>
        {% if membership.accepted_at %}
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Joined Org</dt>
          <dd class="text-sm text-gray-900 dark:text-white">{{ membership.accepted_at|date:"M d, Y" }}</dd>
        </div>
        {% endif %}
        {% if membership.invited_by %}
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Invited By</dt>
          <dd class="text-sm text-gray-900 dark:text-white">{{ membership.invited_by.get_display_name }}</dd>
        </div>
        {% endif %}
      </dl>
    </div>

    <!-- Provider Profile -->
    {% if provider_profile %}
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Provider Profile</h2>
        {% if provider_profile.is_verified_for_org %}
        <span class="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Org-Verified</span>
        {% else %}
        <span class="text-xs text-amber-600 dark:text-amber-400 font-medium">Not Org-Verified</span>
        {% endif %}
      </div>
      <dl class="space-y-3">
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Provider ID</dt>
          <dd class="text-sm font-mono text-gray-900 dark:text-white">{{ provider_profile.provider_id|default:"—" }}</dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Accepting Patients</dt>
          <dd class="text-sm text-gray-900 dark:text-white">
            {% if provider_profile.is_accepting_patients %}Yes{% else %}No{% endif %}
          </dd>
        </div>
        {% if provider_profile.title %}
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Title</dt>
          <dd class="text-sm text-gray-900 dark:text-white">{{ provider_profile.title }}</dd>
        </div>
        {% endif %}
        {% if provider_profile.department %}
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Department</dt>
          <dd class="text-sm text-gray-900 dark:text-white">{{ provider_profile.department }}</dd>
        </div>
        {% endif %}
        {% if provider_profile.specialization %}
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Specialization</dt>
          <dd class="text-sm text-gray-900 dark:text-white">{{ provider_profile.specialization }}</dd>
        </div>
        {% endif %}
        <div class="flex justify-between">
          <dt class="text-sm text-gray-500">Org Fee</dt>
          <dd class="text-sm text-gray-900 dark:text-white">${{ provider_profile.consultation_fee }}</dd>
        </div>
      </dl>
    </div>
    {% elif membership.role == 'doctor' %}
    <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 flex items-center text-sm text-amber-800 dark:text-amber-300">
      No provider profile exists for this doctor in this org.
    </div>
    {% endif %}
  </div>

  <!-- Recent Appointments (doctors only) -->
  {% if recent_appointments %}
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Recent Appointments ({{ recent_appointments|length }})</h2>
    </div>
    <ul class="divide-y divide-gray-200 dark:divide-gray-700">
      {% for appt in recent_appointments %}
      <li class="px-6 py-3 flex items-center justify-between">
        <div>
          <span class="text-sm font-medium text-gray-900 dark:text-white">{{ appt.patient.get_display_name }}</span>
          <span class="text-xs text-gray-500 ml-2">{{ appt.slot.start_time|date:"M d, Y H:i" }}</span>
        </div>
        <span class="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-1 rounded-full">
          {{ appt.status }}
        </span>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Update adminpanel org detail template to link member rows**

In `apps/adminpanel/templates/adminpanel/organizations/detail.html`, find the members list `{% for m in memberships %}` block. Replace:

```html
      <li class="px-6 py-3 flex items-center justify-between">
        <div>
          <span class="font-medium text-gray-900 dark:text-white">{{ m.user.get_display_name }}</span>
          <span class="text-xs text-gray-500 ml-2">{{ m.user.email }}</span>
        </div>
        <span class="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-1 rounded-full">{{ m.role }}</span>
      </li>
```

With:

```html
      <li class="px-6 py-3 flex items-center justify-between">
        <div>
          <a href="{% url 'adminpanel:org_member_detail' org.id m.id %}"
             class="font-medium text-blue-600 dark:text-blue-400 hover:underline">
            {{ m.user.get_display_name }}
          </a>
          <span class="text-xs text-gray-500 ml-2">{{ m.user.email }}</span>
          {% if m.hospital_user_id %}
          <span class="text-xs text-gray-400 font-mono ml-2">{{ m.hospital_user_id }}</span>
          {% endif %}
        </div>
        <span class="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-1 rounded-full">{{ m.role }}</span>
      </li>
```

- [ ] **Step 6: Run tests**

```bash
python manage.py test apps.accounts.tests.AdminMemberDetailTest --settings=config.settings.dev
```

Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add apps/adminpanel/urls.py apps/adminpanel/views.py \
        "apps/adminpanel/templates/adminpanel/organizations/member_detail.html" \
        "apps/adminpanel/templates/adminpanel/organizations/detail.html" \
        apps/accounts/tests.py
git commit -m "feat(identity): platform-admin org member detail with provider profile + appointments"
```

---

## Task 5: ProviderOrganizationProfile Edit View (Hospital Owner/Admin)

**Files:**
- Modify: `apps/organizations/urls.py` — add edit route
- Modify: `apps/organizations/views.py` — add `edit_provider_profile` view
- Modify: `templates/organizations/member_detail.html` — add Edit button

This allows a hospital owner/admin to fill in department, title, specialization, and org fee for a doctor in their org.

- [ ] **Step 1: Write failing test**

In `apps/organizations/tests.py`, add:

```python
class EditProviderProfileTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(
            name='City General', slug='city-general',
            org_type='hospital', status='active',
        )
        self.owner = User.objects.create_user(
            username='own2', email='own2@test.com', password='pass', role='org_user',
        )
        self.owner_membership = OrganizationMembership.objects.create(
            user=self.owner, organization=self.org,
            role='hospital_owner', is_active=True,
            hospital_user_id='CIT-OWN-0001',
        )
        self.doctor = User.objects.create_user(
            username='doc10', email='doc10@test.com', password='pass', role='doctor',
        )
        self.doc_membership = OrganizationMembership.objects.create(
            user=self.doctor, organization=self.org,
            role='doctor', is_active=True,
            hospital_user_id='CIT-DOC-0002',
        )
        self.profile = ProviderOrganizationProfile.objects.create(
            doctor=self.doctor, organization=self.org,
            membership=self.doc_membership,
            provider_id='CIT-DOC-0002',
        )
        self.client.force_login(self.owner)

    def test_post_updates_profile(self):
        url = reverse('organizations:edit_provider_profile', kwargs={
            'org_slug': self.org.slug,
            'member_id': self.doc_membership.id,
        })
        resp = self.client.post(url, {
            'department': 'Cardiology',
            'title': 'MD',
            'specialization': 'Cardiologist',
            'consultation_fee': '150.00',
            'is_accepting_patients': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.department, 'Cardiology')
        self.assertEqual(str(self.profile.consultation_fee), '150.00')
```

Run: `python manage.py test apps.organizations.tests.EditProviderProfileTest --settings=config.settings.dev`
Expected: FAIL — `NoReverseMatch`

- [ ] **Step 2: Add URL**

In `apps/organizations/urls.py`, add:

```python
    path('<slug:org_slug>/staff/<int:member_id>/provider-profile/', views.edit_provider_profile, name='edit_provider_profile'),
```

- [ ] **Step 3: Add edit_provider_profile view**

In `apps/organizations/views.py`, add after `member_detail`:

```python
@login_required
@require_POST
def edit_provider_profile(request, org_slug, member_id):
    from apps.accounts.models import Organization, OrganizationMembership, ProviderOrganizationProfile
    from apps.accounts.permissions import is_platform_staff, get_membership
    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        raise Http404

    if not is_platform_staff(request.user):
        viewer_membership = get_membership(request.user, org)
        if not viewer_membership or viewer_membership.role not in ('hospital_owner', 'hospital_admin'):
            raise PermissionDenied

    membership = get_object_or_404(OrganizationMembership, id=member_id, organization=org, role='doctor')
    profile, _ = ProviderOrganizationProfile.objects.get_or_create(
        membership=membership,
        defaults={'doctor': membership.user, 'organization': org, 'provider_id': membership.hospital_user_id},
    )

    profile.department = request.POST.get('department', '').strip()
    profile.title = request.POST.get('title', '').strip()
    profile.specialization = request.POST.get('specialization', '').strip()
    try:
        profile.consultation_fee = float(request.POST.get('consultation_fee', 0))
    except (ValueError, TypeError):
        profile.consultation_fee = 0
    profile.is_accepting_patients = 'is_accepting_patients' in request.POST
    profile.save(update_fields=[
        'department', 'title', 'specialization', 'consultation_fee', 'is_accepting_patients', 'updated_at',
    ])

    messages.success(request, "Provider profile updated.")
    return redirect(reverse('organizations:member_detail', kwargs={
        'org_slug': org_slug, 'member_id': member_id,
    }))
```

- [ ] **Step 4: Add Edit form to member_detail.html**

In `templates/organizations/member_detail.html`, inside the `{% if provider_profile %}` block, add an edit form after the `</dl>`:

```html
    <form method="post" action="{% url 'organizations:edit_provider_profile' org.slug membership.id %}"
          class="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700 space-y-3">
      {% csrf_token %}
      <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Edit Provider Details</h3>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-gray-500 mb-1">Title</label>
          <input type="text" name="title" value="{{ provider_profile.title }}"
            class="w-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Department</label>
          <input type="text" name="department" value="{{ provider_profile.department }}"
            class="w-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Specialization</label>
          <input type="text" name="specialization" value="{{ provider_profile.specialization }}"
            class="w-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Org Fee ($)</label>
          <input type="number" step="0.01" name="consultation_fee" value="{{ provider_profile.consultation_fee }}"
            class="w-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
        </div>
      </div>
      <div class="flex items-center gap-2">
        <input type="checkbox" name="is_accepting_patients" id="accepting"
          {% if provider_profile.is_accepting_patients %}checked{% endif %}
          class="rounded border-gray-300 dark:border-gray-600 text-blue-600">
        <label for="accepting" class="text-sm text-gray-700 dark:text-gray-300">Accepting patients</label>
      </div>
      <button type="submit"
        class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg text-sm transition-colors">
        Save
      </button>
    </form>
```

- [ ] **Step 5: Run tests**

```bash
python manage.py test apps.organizations.tests.EditProviderProfileTest --settings=config.settings.dev
```

Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add apps/organizations/urls.py apps/organizations/views.py \
        templates/organizations/member_detail.html \
        apps/organizations/tests.py
git commit -m "feat(identity): edit provider profile for hospital owner/admin"
```

---

## Task 6: Full Test Run + CLAUDE.md Update

- [ ] **Step 1: Run full test suite**

```bash
python manage.py test apps --settings=config.settings.dev 2>&1 | tail -20
```

Expected: no test failures. Coverage may drop slightly — that's acceptable.

- [ ] **Step 2: Update CLAUDE.md**

Add this to the "Completed Work" section of `CLAUDE.md` under a new heading after Multi-Tenancy:

```markdown
### Hospital-Specific User Identity (done)
- `hospital_user_id` auto-generated on `OrganizationMembership` creation — format `{ORG_PREFIX}-{ROLE_CODE}-{NNNN}` (e.g. `CGH-DOC-0007`)
- `display_name` field on membership for org-specific name override
- `ProviderOrganizationProfile` model in `apps/accounts/models.py` — org-scoped doctor profile (department, title, specialization, org fee, `is_verified_for_org`, `is_accepting_patients`)
- `generate_hospital_user_id(org, role)` + `create_membership(user, org, role)` in `apps/organizations/services.py`; `accept_invite` view now calls `create_membership`
- Backfill data migration for existing memberships (`0023_backfill_hospital_user_id`)
- Hospital-facing member detail: `/org/<slug>/staff/<id>/` — shows ID, role, provider profile, edit form for owner/admin
- Platform-admin member detail: `/internal/organizations/<id>/members/<id>/` — shows global role, membership, provider profile, recent appointments
- `staff_list.html` and adminpanel `organizations/detail.html` link rows to respective member detail pages
```

- [ ] **Step 3: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: mark hospital-specific user identity as complete in CLAUDE.md"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ `hospital_user_id` on `OrganizationMembership` (unique per org) — Task 1 + 2
- ✅ `display_name` on membership — Task 1
- ✅ `ProviderOrganizationProfile` model — Task 1
- ✅ Auto-generate ID on membership creation — Task 2
- ✅ Auto-create `ProviderOrganizationProfile` for doctor memberships — Task 2 `create_membership`
- ✅ Backfill existing memberships — Task 2 data migration
- ✅ Hospital click-flow: staff list → member detail — Task 3
- ✅ Platform admin click-flow: org detail → member detail — Task 4
- ✅ Recent appointments on admin member detail — Task 4
- ✅ Provider profile edit form (hospital owner/admin) — Task 5

**Not in scope (follow-up):**
- Platform admin toggling `is_verified_for_org` — no separate task; can be added as a small follow-up
- `display_name` edit form — omitted per YAGNI; can be added in the member detail edit form later
