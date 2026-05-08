# Multi-Tenancy UI Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the hospital signup flow, platform owner org review, role-based org dashboards, staff invite lifecycle, and org switcher for platform staff.

**Architecture:** New `apps/organizations/` app owns org-facing views and URLs. Platform review extends `apps/adminpanel/`. All views consume the permission helpers and OrgContext from Plan 1.

**Depends on:** `docs/superpowers/plans/2026-05-07-multi-tenancy-foundation.md` fully applied.

**Tech Stack:** Django 4.2, HTMX, Tailwind CSS (CDN), existing `layouts/app.html` and `layouts/admin.html`

**Spec:** `docs/superpowers/specs/2026-05-07-multi-tenancy-design.md`

---

## Phase 4 — UI Layer

### Task 1: New `organizations` app — scaffold + register

**Files:**
- Create: `apps/organizations/__init__.py`
- Create: `apps/organizations/apps.py`
- Create: `apps/organizations/urls.py`
- Create: `apps/organizations/views.py`
- Modify: `config/settings/base.py` (INSTALLED_APPS)
- Modify: `config/urls.py` (include org URLs)

- [ ] **Step 1: Create app files**

```python
# apps/organizations/__init__.py
# (empty)

# apps/organizations/apps.py
from django.apps import AppConfig

class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.organizations'
    label = 'organizations'
```

```python
# apps/organizations/urls.py
from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('register/', views.org_register, name='org_register'),
    path('invite/<str:token>/', views.accept_invite, name='accept_invite'),
    path('<slug:org_slug>/', views.org_dashboard, name='org_dashboard'),
    path('<slug:org_slug>/settings/', views.org_settings, name='org_settings'),
    path('<slug:org_slug>/staff/', views.staff_list, name='staff_list'),
    path('<slug:org_slug>/staff/invite/', views.send_invite, name='send_invite'),
    path('<slug:org_slug>/staff/<int:member_id>/deactivate/', views.deactivate_member, name='deactivate_member'),
]
```

```python
# apps/organizations/views.py
# (placeholder stubs — filled in Tasks 2-7)
from django.shortcuts import render

def org_register(request):
    return render(request, 'organizations/register.html')

def accept_invite(request, token):
    return render(request, 'organizations/accept_invite.html')

def org_dashboard(request, org_slug):
    return render(request, 'organizations/dashboard.html')

def org_settings(request, org_slug):
    return render(request, 'organizations/settings.html')

def staff_list(request, org_slug):
    return render(request, 'organizations/staff_list.html')

def send_invite(request, org_slug):
    return render(request, 'organizations/send_invite.html')

def deactivate_member(request, org_slug, member_id):
    return render(request, 'organizations/deactivate_member.html')
```

- [ ] **Step 2: Register app and URLs**

In `config/settings/base.py`, add to `INSTALLED_APPS`:
```python
'apps.organizations',
```

In `config/urls.py`, add:
```python
path('org/', include('apps.organizations.urls', namespace='organizations')),
path('invite/', include('apps.organizations.urls', namespace='organizations_invite')),
```

Wait — `invite/<token>/` and `org/<slug>/` share the same app but different prefixes. Wire them both from one include:

```python
# config/urls.py — add these two lines
path('org/', include('apps.organizations.urls')),
path('invite/', include('apps.organizations.urls')),
```

But `app_name` is already set in `urls.py` so only one namespace can be used. Keep the include once under `org/` and add the invite path directly:

```python
path('org/', include('apps.organizations.urls')),
path('invite/<str:token>/', include([
    path('', views_org.accept_invite, name='accept_invite'),
])),
```

Simplest: just put invite URL under `/org/invite/<token>/` and update spec reference:

```python
# config/urls.py
path('org/', include('apps.organizations.urls')),
```

With invite at `/org/invite/<token>/` matching `apps/organizations/urls.py` entry:
```python
path('invite/<str:token>/', views.accept_invite, name='accept_invite'),
```

- [ ] **Step 3: Write smoke test**

```python
# apps/organizations/tests.py
from django.test import TestCase
from django.urls import reverse

class OrgURLsTest(TestCase):
    def test_register_url_resolves(self):
        url = reverse('organizations:org_register')
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302])
```

- [ ] **Step 4: Run test**

```bash
python manage.py test apps.organizations.tests.OrgURLsTest --settings=config.settings.dev
```

Expected: PASS (stub views return 200)

- [ ] **Step 5: Commit**

```bash
git add apps/organizations/ config/settings/base.py config/urls.py
git commit -m "feat: scaffold organizations app with stub views and URLs"
```

---

### Task 2: Hospital self-service signup — `/org/register/`

**Files:**
- Modify: `apps/organizations/views.py`
- Create: `apps/organizations/forms.py`
- Create: `apps/organizations/services.py`
- Create: `templates/organizations/register.html`
- Create: `templates/organizations/register_pending.html`

- [ ] **Step 1: Write failing tests**

```python
# apps/organizations/tests.py
from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import User
from apps.accounts.models import Organization, OrganizationMembership

class OrgRegisterTest(TestCase):
    def _post_valid(self):
        return self.client.post(reverse('organizations:org_register'), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@cityhospital.com',
            'password1': 'Str0ng!Pass',
            'password2': 'Str0ng!Pass',
            'org_name': 'City General Hospital',
            'org_type': 'hospital',
            'address': '123 Main St',
            'phone': '555-0100',
        })

    def test_creates_user_with_org_user_role(self):
        self._post_valid()
        user = User.objects.get(email='jane@cityhospital.com')
        self.assertEqual(user.role, 'org_user')

    def test_creates_org_with_pending_status(self):
        self._post_valid()
        org = Organization.objects.get(name='City General Hospital')
        self.assertEqual(org.status, 'pending')

    def test_creates_hospital_owner_membership(self):
        self._post_valid()
        user = User.objects.get(email='jane@cityhospital.com')
        org = Organization.objects.get(name='City General Hospital')
        membership = OrganizationMembership.objects.get(user=user, organization=org)
        self.assertEqual(membership.role, 'hospital_owner')

    def test_redirects_to_pending_page(self):
        response = self._post_valid()
        self.assertRedirects(response, reverse('organizations:org_register_pending'))
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python manage.py test apps.organizations.tests.OrgRegisterTest --settings=config.settings.dev
```

Expected: FAIL — views are stubs, service doesn't exist yet.

- [ ] **Step 3: Create forms**

```python
# apps/organizations/forms.py
from django import forms
from apps.accounts.models import Organization

ORG_TYPE_CHOICES = [
    ('hospital', 'Hospital'),
    ('clinic', 'Clinic'),
    ('private_practice', 'Private Practice'),
    ('urgent_care', 'Urgent Care'),
    ('mental_health', 'Mental Health'),
]

class OrgOwnerAccountForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    def clean_email(self):
        from apps.accounts.models import User
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class OrgProfileForm(forms.Form):
    org_name = forms.CharField(max_length=255)
    org_type = forms.ChoiceField(choices=ORG_TYPE_CHOICES)
    address = forms.CharField(max_length=500, required=False)
    phone = forms.CharField(max_length=30, required=False)
    website = forms.URLField(required=False)
    logo = forms.ImageField(required=False)
```

- [ ] **Step 4: Create service**

```python
# apps/organizations/services.py
import uuid
from django.utils.text import slugify
from django.db import transaction
from apps.accounts.models import User, Organization, OrganizationMembership
from apps.accounts.tasks import send_verification_email_task


@transaction.atomic
def register_organization(account_data: dict, org_data: dict) -> tuple[User, Organization]:
    """Create org_user + pending Organization + hospital_owner membership."""
    user = User.objects.create_user(
        username=account_data['email'].split('@')[0] + '_' + uuid.uuid4().hex[:6],
        email=account_data['email'].lower(),
        password=account_data['password1'],
        first_name=account_data['first_name'],
        last_name=account_data['last_name'],
        role='org_user',
        is_email_verified=False,
    )

    base_slug = slugify(org_data['org_name'])
    slug = base_slug
    counter = 1
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization.objects.create(
        name=org_data['org_name'],
        slug=slug,
        org_type=org_data['org_type'],
        status='pending',
        address=org_data.get('address', ''),
        phone=org_data.get('phone', ''),
        website=org_data.get('website', ''),
        created_by=user,
    )
    if org_data.get('logo'):
        org.logo = org_data['logo']
        org.save(update_fields=['logo'])

    OrganizationMembership.objects.create(
        user=user,
        organization=org,
        role='hospital_owner',
        is_active=True,
    )

    send_verification_email_task.delay(user.id)
    _notify_platform_owner_new_org(org)
    return user, org


def _notify_platform_owner_new_org(org: Organization) -> None:
    from apps.accounts.services import create_notification
    from apps.accounts.models import User as UserModel
    for owner in UserModel.objects.filter(role='platform_owner', is_active=True):
        create_notification(
            recipient=owner,
            message=f"New organization pending review: {org.name}",
            notification_type='org_pending',
        )
```

- [ ] **Step 5: Implement view**

```python
# apps/organizations/views.py — replace org_register stub
from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import OrgOwnerAccountForm, OrgProfileForm
from .services import register_organization

def org_register(request):
    account_form = OrgOwnerAccountForm(request.POST or None)
    org_form = OrgProfileForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if account_form.is_valid() and org_form.is_valid():
            register_organization(account_form.cleaned_data, org_form.cleaned_data)
            return redirect(reverse('organizations:org_register_pending'))

    return render(request, 'organizations/register.html', {
        'account_form': account_form,
        'org_form': org_form,
    })

def org_register_pending(request):
    return render(request, 'organizations/register_pending.html')
```

Add `org_register_pending` to `urls.py`:
```python
path('register/pending/', views.org_register_pending, name='org_register_pending'),
```

- [ ] **Step 6: Create templates**

```html
<!-- templates/organizations/register.html -->
{% extends "layouts/public.html" %}
{% block title %}Register Your Organization — MedConsult{% endblock %}
{% block content %}
<div class="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
  <div class="max-w-2xl mx-auto">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold text-gray-900 dark:text-white">Register Your Organization</h1>
      <p class="mt-2 text-gray-600 dark:text-gray-400">Join MedConsult as a verified healthcare organization</p>
    </div>

    <form method="post" enctype="multipart/form-data" class="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8 space-y-8">
      {% csrf_token %}

      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Your Account</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">First Name</label>
            {{ account_form.first_name }}
            {% if account_form.first_name.errors %}<p class="text-red-500 text-xs mt-1">{{ account_form.first_name.errors.0 }}</p>{% endif %}
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Last Name</label>
            {{ account_form.last_name }}
          </div>
          <div class="sm:col-span-2">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Work Email</label>
            {{ account_form.email }}
            {% if account_form.email.errors %}<p class="text-red-500 text-xs mt-1">{{ account_form.email.errors.0 }}</p>{% endif %}
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
            {{ account_form.password1 }}
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Confirm Password</label>
            {{ account_form.password2 }}
            {% if account_form.non_field_errors %}<p class="text-red-500 text-xs mt-1">{{ account_form.non_field_errors.0 }}</p>{% endif %}
          </div>
        </div>
      </div>

      <hr class="border-gray-200 dark:border-gray-700">

      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Organization Details</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="sm:col-span-2">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Organization Name</label>
            {{ org_form.org_name }}
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
            {{ org_form.org_type }}
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone</label>
            {{ org_form.phone }}
          </div>
          <div class="sm:col-span-2">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Address</label>
            {{ org_form.address }}
          </div>
          <div class="sm:col-span-2">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Website</label>
            {{ org_form.website }}
          </div>
          <div class="sm:col-span-2">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Logo (optional)</label>
            {{ org_form.logo }}
          </div>
        </div>
      </div>

      <button type="submit"
        class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors">
        Submit for Review
      </button>
    </form>
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/organizations/register_pending.html -->
{% extends "layouts/public.html" %}
{% block title %}Application Submitted — MedConsult{% endblock %}
{% block content %}
<div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
  <div class="max-w-md text-center">
    <div class="w-20 h-20 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
      <svg class="w-10 h-10 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
    </div>
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-3">Application Under Review</h1>
    <p class="text-gray-600 dark:text-gray-400 mb-6">
      Your organization has been submitted for review. We'll verify your details and send you an email within 1–2 business days. Check your inbox to verify your email address in the meantime.
    </p>
    <a href="{% url 'login' %}" class="inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-medium transition-colors">
      Back to Login
    </a>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Apply input CSS classes to forms**

The form fields render as plain HTML inputs. In `forms.py`, add widget attrs:

```python
INPUT_CLASS = "w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
SELECT_CLASS = INPUT_CLASS

# Apply in __init__ or use widget attrs in field definitions:
class OrgOwnerAccountForm(forms.Form):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': INPUT_CLASS}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}))

class OrgProfileForm(forms.Form):
    org_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    org_type = forms.ChoiceField(choices=ORG_TYPE_CHOICES, widget=forms.Select(attrs={'class': SELECT_CLASS}))
    address = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    website = forms.URLField(required=False, widget=forms.URLInput(attrs={'class': INPUT_CLASS}))
    logo = forms.ImageField(required=False)
```

- [ ] **Step 8: Run tests**

```bash
python manage.py test apps.organizations.tests.OrgRegisterTest --settings=config.settings.dev
```

Expected: all 4 tests PASS

- [ ] **Step 9: Commit**

```bash
git add apps/organizations/ templates/organizations/register.html templates/organizations/register_pending.html
git commit -m "feat: hospital self-service signup flow with pending review state"
```

---

### Task 3: Invite acceptance — `/org/invite/<token>/`

**Files:**
- Modify: `apps/organizations/views.py`
- Modify: `apps/organizations/services.py`
- Create: `templates/organizations/accept_invite.html`
- Create: `templates/organizations/invite_mini_register.html`

- [ ] **Step 1: Write failing tests**

```python
# apps/organizations/tests.py
import hashlib, uuid
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import Organization, OrganizationInvite, OrganizationMembership, User

class InviteAcceptanceTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Test Clinic', slug='test-clinic', org_type='clinic', status='active'
        )
        self.inviter = User.objects.create_user(
            username='owner', email='owner@test.com', password='pass1234!', role='org_user'
        )
        raw = uuid.uuid4().hex
        self.raw_token = raw
        self.invite = OrganizationInvite.objects.create(
            organization=self.org,
            invited_by=self.inviter,
            email='newdoc@test.com',
            role='doctor',
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            status='pending',
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_valid_token_shows_accept_page(self):
        response = self.client.get(f'/org/invite/{self.raw_token}/')
        self.assertEqual(response.status_code, 200)

    def test_expired_token_returns_400(self):
        self.invite.expires_at = timezone.now() - timedelta(hours=1)
        self.invite.save()
        response = self.client.get(f'/org/invite/{self.raw_token}/')
        self.assertEqual(response.status_code, 400)

    def test_email_mismatch_blocked(self):
        wrong_user = User.objects.create_user(
            username='wronguser', email='wrong@test.com', password='pass1234!', role='doctor'
        )
        self.client.force_login(wrong_user)
        response = self.client.post(f'/org/invite/{self.raw_token}/', {
            'accept': '1'
        })
        self.assertEqual(response.status_code, 403)

    def test_valid_accept_creates_membership(self):
        user = User.objects.create_user(
            username='newdoc', email='newdoc@test.com', password='pass1234!', role='doctor'
        )
        self.client.force_login(user)
        self.client.post(f'/org/invite/{self.raw_token}/', {'accept': '1'})
        self.assertTrue(
            OrganizationMembership.objects.filter(user=user, organization=self.org).exists()
        )

    def test_double_acceptance_blocked(self):
        user = User.objects.create_user(
            username='newdoc2', email='newdoc@test.com', password='pass1234!', role='doctor'
        )
        self.client.force_login(user)
        self.client.post(f'/org/invite/{self.raw_token}/', {'accept': '1'})
        # Second submit — invite now accepted, should not create duplicate
        response = self.client.post(f'/org/invite/{self.raw_token}/', {'accept': '1'})
        self.assertEqual(OrganizationMembership.objects.filter(user=user, organization=self.org).count(), 1)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python manage.py test apps.organizations.tests.InviteAcceptanceTest --settings=config.settings.dev
```

- [ ] **Step 3: Add service**

```python
# apps/organizations/services.py — add below register_organization

import hashlib
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from apps.accounts.models import OrganizationInvite, OrganizationMembership, DoctorProfile


def resolve_invite(raw_token: str) -> OrganizationInvite:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    try:
        invite = OrganizationInvite.objects.select_related('organization').get(
            token_hash=token_hash
        )
    except OrganizationInvite.DoesNotExist:
        return None
    return invite


@transaction.atomic
def accept_invite(invite: OrganizationInvite, user) -> OrganizationMembership:
    # Re-lock row to prevent race
    invite = OrganizationInvite.objects.select_for_update().get(pk=invite.pk)

    if invite.status != 'pending':
        raise ValueError("Invite is no longer pending.")
    if invite.expires_at < timezone.now():
        raise ValueError("Invite has expired.")
    if invite.email.lower() != user.email.lower():
        raise PermissionDenied("This invite was sent to a different email address.")

    # Create or reactivate membership
    membership, created = OrganizationMembership.objects.get_or_create(
        user=user,
        organization=invite.organization,
        defaults={
            'role': invite.role,
            'is_active': True,
            'invited_by': invite.invited_by,
            'accepted_at': timezone.now(),
        }
    )
    if not created:
        membership.is_active = True
        membership.role = invite.role
        membership.accepted_at = timezone.now()
        membership.save(update_fields=['is_active', 'role', 'accepted_at'])

    invite.status = 'accepted'
    invite.accepted_by = user
    invite.save(update_fields=['status', 'accepted_by'])

    # If doctor, link DoctorProfile to org
    if invite.role == 'doctor':
        DoctorProfile.objects.filter(user=user).update(organization=invite.organization)

    return membership


def post_accept_redirect(membership) -> str:
    from django.urls import reverse
    role = membership.role
    slug = membership.organization.slug
    if role in ('hospital_owner', 'hospital_admin', 'scheduler'):
        return reverse('organizations:org_dashboard', kwargs={'org_slug': slug})
    if role == 'doctor':
        return reverse('accounts:profile')
    # deferred roles
    return reverse('organizations:org_dashboard', kwargs={'org_slug': slug})
```

- [ ] **Step 4: Implement view**

```python
# apps/organizations/views.py — replace accept_invite stub
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render, redirect
from .services import resolve_invite, accept_invite as svc_accept_invite, post_accept_redirect

def accept_invite(request, token):
    invite = resolve_invite(token)
    if invite is None:
        return HttpResponseBadRequest("Invalid invite link.")
    from django.utils import timezone
    if invite.expires_at < timezone.now() or invite.status != 'pending':
        return HttpResponseBadRequest("This invite has expired or has already been used.")

    if not request.user.is_authenticated:
        # Check if email has an account
        from apps.accounts.models import User
        existing = User.objects.filter(email__iexact=invite.email).first()
        if existing:
            # Send to login, then redirect back
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        # Show mini-register form
        from .forms import InviteeRegisterForm
        form = InviteeRegisterForm(request.POST or None, initial={'email': invite.email})
        if request.method == 'POST' and form.is_valid():
            from apps.accounts.models import User
            import uuid
            user = User.objects.create_user(
                username=invite.email.split('@')[0] + '_' + uuid.uuid4().hex[:6],
                email=invite.email.lower(),
                password=form.cleaned_data['password1'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role='doctor' if invite.role == 'doctor' else 'org_user',
                is_email_verified=True,  # invite email is pre-verified
            )
            from django.contrib.auth import login
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            membership = svc_accept_invite(invite, user)
            return redirect(post_accept_redirect(membership))
        return render(request, 'organizations/invite_mini_register.html', {
            'invite': invite, 'form': form
        })

    # User is logged in
    if request.method == 'POST' and request.POST.get('accept') == '1':
        try:
            membership = svc_accept_invite(invite, request.user)
        except PermissionDenied as e:
            return HttpResponseForbidden(str(e))
        except ValueError as e:
            messages.error(request, str(e))
            return redirect(request.path)
        return redirect(post_accept_redirect(membership))

    return render(request, 'organizations/accept_invite.html', {'invite': invite})
```

- [ ] **Step 5: Add InviteeRegisterForm**

```python
# apps/organizations/forms.py — add at bottom
class InviteeRegisterForm(forms.Form):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': INPUT_CLASS, 'readonly': 'readonly'}))
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned
```

- [ ] **Step 6: Create templates**

```html
<!-- templates/organizations/accept_invite.html -->
{% extends "layouts/public.html" %}
{% block title %}Accept Invite — MedConsult{% endblock %}
{% block content %}
<div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
  <div class="max-w-md w-full bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">You're invited</h1>
    <p class="text-gray-600 dark:text-gray-400 mb-6">
      Join <strong>{{ invite.organization.name }}</strong> as
      <strong>{{ invite.get_role_display }}</strong>.
    </p>
    {% if messages %}
    <div class="mb-4">
      {% for msg in messages %}
      <p class="text-red-600 dark:text-red-400 text-sm">{{ msg }}</p>
      {% endfor %}
    </div>
    {% endif %}
    <form method="post">
      {% csrf_token %}
      <input type="hidden" name="accept" value="1">
      <button type="submit"
        class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors">
        Accept Invitation
      </button>
    </form>
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/organizations/invite_mini_register.html -->
{% extends "layouts/public.html" %}
{% block title %}Create Account — MedConsult{% endblock %}
{% block content %}
<div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
  <div class="max-w-md w-full bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Create your account</h1>
    <p class="text-gray-600 dark:text-gray-400 mb-6">
      You've been invited to join <strong>{{ invite.organization.name }}</strong>.
      Set up your account to accept.
    </p>
    <form method="post" class="space-y-4">
      {% csrf_token %}
      {% for field in form %}
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ field.label }}</label>
        {{ field }}
        {% if field.errors %}<p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}</p>{% endif %}
      </div>
      {% endfor %}
      <button type="submit"
        class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors">
        Create Account & Accept
      </button>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Run tests**

```bash
python manage.py test apps.organizations.tests.InviteAcceptanceTest --settings=config.settings.dev
```

Expected: all 5 tests PASS

- [ ] **Step 8: Commit**

```bash
git add apps/organizations/ templates/organizations/accept_invite.html templates/organizations/invite_mini_register.html
git commit -m "feat: invite acceptance flow with email lock and race-safe select_for_update"
```

---

### Task 4: Platform owner — org review UI

**Files:**
- Modify: `apps/adminpanel/views.py`
- Modify: `apps/adminpanel/urls.py`
- Create: `apps/adminpanel/templates/adminpanel/organizations/list.html`
- Create: `apps/adminpanel/templates/adminpanel/organizations/detail.html`

- [ ] **Step 1: Write failing tests**

```python
# apps/adminpanel/tests.py — add to existing
from apps.accounts.models import Organization, User

class OrgReviewTest(TestCase):
    def setUp(self):
        self.platform_owner = User.objects.create_user(
            username='po', email='po@test.com', password='pass', role='platform_owner'
        )
        self.org = Organization.objects.create(
            name='Test Hospital', slug='test-hospital',
            org_type='hospital', status='pending'
        )

    def test_org_list_requires_platform_staff(self):
        response = self.client.get('/internal/organizations/')
        self.assertRedirects(response, '/auth/login/?next=/internal/organizations/')

    def test_org_list_visible_to_platform_owner(self):
        self.client.force_login(self.platform_owner)
        response = self.client.get('/internal/organizations/')
        self.assertEqual(response.status_code, 200)

    def test_approve_org_sets_status_active(self):
        self.client.force_login(self.platform_owner)
        self.client.post(f'/internal/organizations/{self.org.id}/approve/')
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'active')

    def test_reject_org_stores_reason(self):
        self.client.force_login(self.platform_owner)
        self.client.post(f'/internal/organizations/{self.org.id}/reject/', {'reason': 'Incomplete docs'})
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'rejected')
        self.assertIn('Incomplete docs', self.org.rejected_reason)

    def test_suspend_org(self):
        self.org.status = 'active'
        self.org.save()
        self.client.force_login(self.platform_owner)
        self.client.post(f'/internal/organizations/{self.org.id}/suspend/')
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'suspended')
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python manage.py test apps.adminpanel.tests.OrgReviewTest --settings=config.settings.dev
```

- [ ] **Step 3: Add views**

```python
# apps/adminpanel/views.py — add at bottom

from apps.accounts.models import Organization, OrganizationMembership
from apps.accounts.permissions import is_platform_staff
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone


def _require_platform_staff(request):
    if not is_platform_staff(request.user):
        raise PermissionDenied


@login_required
def organization_list(request):
    _require_platform_staff(request)
    status_filter = request.GET.get('status', '')
    orgs = Organization.objects.select_related('created_by').order_by('-created_at')
    if status_filter:
        orgs = orgs.filter(status=status_filter)
    return render(request, 'adminpanel/organizations/list.html', {
        'orgs': orgs,
        'status_filter': status_filter,
        'pending_count': Organization.objects.filter(status='pending').count(),
    })


@login_required
def organization_detail(request, org_id):
    _require_platform_staff(request)
    org = get_object_or_404(Organization, id=org_id)
    memberships = OrganizationMembership.objects.filter(
        organization=org, is_active=True
    ).select_related('user')
    return render(request, 'adminpanel/organizations/detail.html', {
        'org': org, 'memberships': memberships,
    })


@login_required
def organization_approve(request, org_id):
    _require_platform_staff(request)
    if request.method != 'POST':
        return redirect('adminpanel:organization_detail', org_id=org_id)
    org = get_object_or_404(Organization, id=org_id)
    org.status = 'active'
    org.approved_by = request.user
    org.approved_at = timezone.now()
    org.save(update_fields=['status', 'approved_by', 'approved_at'])
    _notify_org_owner(org, 'approved')
    log_admin_action(request.user, f"Approved organization: {org.name}", org_id=org.id)
    messages.success(request, f"{org.name} approved.")
    return redirect('adminpanel:organization_list')


@login_required
def organization_reject(request, org_id):
    _require_platform_staff(request)
    if request.method != 'POST':
        return redirect('adminpanel:organization_detail', org_id=org_id)
    org = get_object_or_404(Organization, id=org_id)
    reason = request.POST.get('reason', '').strip()
    org.status = 'rejected'
    org.rejected_reason = reason
    org.save(update_fields=['status', 'rejected_reason'])
    _notify_org_owner(org, 'rejected', reason=reason)
    log_admin_action(request.user, f"Rejected organization: {org.name} — {reason}", org_id=org.id)
    messages.warning(request, f"{org.name} rejected.")
    return redirect('adminpanel:organization_list')


@login_required
def organization_suspend(request, org_id):
    _require_platform_staff(request)
    if request.method != 'POST':
        return redirect('adminpanel:organization_detail', org_id=org_id)
    org = get_object_or_404(Organization, id=org_id, status='active')
    org.status = 'suspended'
    org.save(update_fields=['status'])
    log_admin_action(request.user, f"Suspended organization: {org.name}", org_id=org.id)
    messages.warning(request, f"{org.name} suspended.")
    return redirect('adminpanel:organization_list')


@login_required
def organization_reactivate(request, org_id):
    _require_platform_staff(request)
    if request.method != 'POST':
        return redirect('adminpanel:organization_detail', org_id=org_id)
    org = get_object_or_404(Organization, id=org_id, status='suspended')
    org.status = 'active'
    org.save(update_fields=['status'])
    log_admin_action(request.user, f"Reactivated organization: {org.name}", org_id=org.id)
    messages.success(request, f"{org.name} reactivated.")
    return redirect('adminpanel:organization_list')


@login_required
def organization_needs_info(request, org_id):
    _require_platform_staff(request)
    if request.method != 'POST':
        return redirect('adminpanel:organization_detail', org_id=org_id)
    org = get_object_or_404(Organization, id=org_id)
    message = request.POST.get('message', '').strip()
    org.status = 'needs_info'
    org.save(update_fields=['status'])
    _notify_org_owner(org, 'needs_info', reason=message)
    log_admin_action(request.user, f"Requested more info from: {org.name}", org_id=org.id)
    messages.info(request, f"Requested more info from {org.name}.")
    return redirect('adminpanel:organization_list')


def _notify_org_owner(org, action, reason=''):
    from apps.accounts.services import create_notification
    owner_memberships = OrganizationMembership.objects.filter(
        organization=org, role='hospital_owner', is_active=True
    ).select_related('user')
    messages_map = {
        'approved': f"Your organization '{org.name}' has been approved. You can now invite staff.",
        'rejected': f"Your organization '{org.name}' was not approved. Reason: {reason}",
        'needs_info': f"We need more information about '{org.name}': {reason}",
    }
    msg = messages_map.get(action, '')
    for m in owner_memberships:
        create_notification(recipient=m.user, message=msg, notification_type=f'org_{action}')
```

- [ ] **Step 4: Wire URLs**

```python
# apps/adminpanel/urls.py — add to urlpatterns
path('organizations/', views.organization_list, name='organization_list'),
path('organizations/<int:org_id>/', views.organization_detail, name='organization_detail'),
path('organizations/<int:org_id>/approve/', views.organization_approve, name='organization_approve'),
path('organizations/<int:org_id>/reject/', views.organization_reject, name='organization_reject'),
path('organizations/<int:org_id>/suspend/', views.organization_suspend, name='organization_suspend'),
path('organizations/<int:org_id>/reactivate/', views.organization_reactivate, name='organization_reactivate'),
path('organizations/<int:org_id>/needs-info/', views.organization_needs_info, name='organization_needs_info'),
```

- [ ] **Step 5: Create templates**

```html
<!-- apps/adminpanel/templates/adminpanel/organizations/list.html -->
{% extends "layouts/admin.html" %}
{% block title %}Organizations — MedConsult Admin{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Organizations</h1>
  {% if pending_count %}
  <span class="bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 text-sm font-semibold px-3 py-1 rounded-full">
    {{ pending_count }} pending review
  </span>
  {% endif %}
</div>

<!-- Status filter tabs -->
<div class="flex gap-2 mb-6 flex-wrap">
  {% for val, label in statuses %}
  <a href="?status={{ val }}"
     class="px-4 py-2 rounded-lg text-sm font-medium transition-colors
       {% if status_filter == val %}bg-blue-600 text-white{% else %}bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700{% endif %}">
    {{ label }}
  </a>
  {% endfor %}
  <a href="?" class="px-4 py-2 rounded-lg text-sm font-medium bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">All</a>
</div>

<div class="bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
  <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
    <thead class="bg-gray-50 dark:bg-gray-700/50">
      <tr>
        <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Organization</th>
        <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Type</th>
        <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
        <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Owner</th>
        <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Created</th>
        <th class="px-6 py-3"></th>
      </tr>
    </thead>
    <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
      {% for org in orgs %}
      <tr class="hover:bg-gray-50 dark:hover:bg-gray-700/30">
        <td class="px-6 py-4">
          <div class="font-medium text-gray-900 dark:text-white">{{ org.name }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">{{ org.slug }}</div>
        </td>
        <td class="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">{{ org.get_org_type_display }}</td>
        <td class="px-6 py-4">
          <span class="px-2.5 py-1 rounded-full text-xs font-semibold
            {% if org.status == 'active' %}bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300
            {% elif org.status == 'pending' %}bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300
            {% elif org.status == 'rejected' %}bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300
            {% elif org.status == 'suspended' %}bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300
            {% else %}bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300{% endif %}">
            {{ org.get_status_display }}
          </span>
        </td>
        <td class="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
          {% if org.created_by %}{{ org.created_by.get_display_name }}{% else %}—{% endif %}
        </td>
        <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{{ org.created_at|date:"M j, Y" }}</td>
        <td class="px-6 py-4 text-right">
          <a href="{% url 'adminpanel:organization_detail' org.id %}"
             class="text-blue-600 dark:text-blue-400 hover:underline text-sm font-medium">Review →</a>
        </td>
      </tr>
      {% empty %}
      <tr><td colspan="6" class="px-6 py-8 text-center text-gray-500 dark:text-gray-400">No organizations found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

```html
<!-- apps/adminpanel/templates/adminpanel/organizations/detail.html -->
{% extends "layouts/admin.html" %}
{% block title %}{{ org.name }} — Review{% endblock %}
{% block content %}
<div class="max-w-3xl">
  <div class="flex items-start justify-between mb-6">
    <div>
      <a href="{% url 'adminpanel:organization_list' %}" class="text-sm text-gray-500 dark:text-gray-400 hover:underline">← Organizations</a>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white mt-1">{{ org.name }}</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400">{{ org.get_org_type_display }} · {{ org.slug }}</p>
    </div>
    <span class="mt-2 px-3 py-1 rounded-full text-sm font-semibold
      {% if org.status == 'active' %}bg-green-100 text-green-800
      {% elif org.status == 'pending' %}bg-amber-100 text-amber-800
      {% elif org.status == 'rejected' %}bg-red-100 text-red-800
      {% elif org.status == 'suspended' %}bg-orange-100 text-orange-800
      {% else %}bg-blue-100 text-blue-800{% endif %}">
      {{ org.get_status_display }}
    </span>
  </div>

  <!-- Details -->
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6 mb-6 space-y-3 text-sm">
    <div class="grid grid-cols-2 gap-4">
      <div><span class="text-gray-500 dark:text-gray-400">Address</span><p class="font-medium text-gray-900 dark:text-white">{{ org.address|default:"—" }}</p></div>
      <div><span class="text-gray-500 dark:text-gray-400">Phone</span><p class="font-medium text-gray-900 dark:text-white">{{ org.phone|default:"—" }}</p></div>
      <div><span class="text-gray-500 dark:text-gray-400">Website</span><p class="font-medium text-gray-900 dark:text-white">{% if org.website %}<a href="{{ org.website }}" class="text-blue-600 underline" target="_blank">{{ org.website }}</a>{% else %}—{% endif %}</p></div>
      <div><span class="text-gray-500 dark:text-gray-400">Submitted</span><p class="font-medium text-gray-900 dark:text-white">{{ org.created_at|date:"M j, Y" }}</p></div>
    </div>
  </div>

  <!-- Review checklist (informational only — no DB backing) -->
  {% if org.status == 'pending' or org.status == 'needs_info' %}
  <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-5 mb-6">
    <h2 class="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-3 uppercase tracking-wide">Review Checklist</h2>
    <ul class="space-y-2 text-sm text-blue-700 dark:text-blue-400">
      <li class="flex items-center gap-2"><input type="checkbox" class="rounded"> Organization name verified</li>
      <li class="flex items-center gap-2"><input type="checkbox" class="rounded"> Website/domain checked</li>
      <li class="flex items-center gap-2"><input type="checkbox" class="rounded"> Phone/address checked</li>
      <li class="flex items-center gap-2"><input type="checkbox" class="rounded"> Owner email verified</li>
      <li class="flex items-center gap-2"><input type="checkbox" class="rounded"> Business documents reviewed</li>
    </ul>
  </div>
  {% endif %}

  <!-- Members -->
  {% if memberships %}
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6 mb-6">
    <h2 class="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">Members</h2>
    <ul class="divide-y divide-gray-100 dark:divide-gray-700">
      {% for m in memberships %}
      <li class="py-3 flex items-center justify-between">
        <div>
          <p class="font-medium text-gray-900 dark:text-white text-sm">{{ m.user.get_display_name }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400">{{ m.user.email }}</p>
        </div>
        <span class="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">{{ m.role }}</span>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  <!-- Actions -->
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
    <h2 class="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">Actions</h2>
    <div class="flex flex-wrap gap-3">
      {% if org.status == 'pending' or org.status == 'needs_info' %}
      <form method="post" action="{% url 'adminpanel:organization_approve' org.id %}">
        {% csrf_token %}
        <button class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium">Approve</button>
      </form>
      <form method="post" action="{% url 'adminpanel:organization_reject' org.id %}" class="flex gap-2">
        {% csrf_token %}
        <input name="reason" placeholder="Rejection reason" required
               class="border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm w-48">
        <button class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium">Reject</button>
      </form>
      <form method="post" action="{% url 'adminpanel:organization_needs_info' org.id %}" class="flex gap-2">
        {% csrf_token %}
        <input name="message" placeholder="What info is needed?" required
               class="border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm w-48">
        <button class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium">Request Info</button>
      </form>
      {% endif %}
      {% if org.status == 'active' %}
      <form method="post" action="{% url 'adminpanel:organization_suspend' org.id %}" onsubmit="return confirm('Suspend {{ org.name }}?')">
        {% csrf_token %}
        <button class="bg-orange-600 hover:bg-orange-700 text-white px-4 py-2 rounded-lg text-sm font-medium">Suspend</button>
      </form>
      {% endif %}
      {% if org.status == 'suspended' %}
      <form method="post" action="{% url 'adminpanel:organization_reactivate' org.id %}">
        {% csrf_token %}
        <button class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium">Reactivate</button>
      </form>
      {% endif %}
    </div>
  </div>
</div>
{% endblock %}
```

Also pass `statuses` context in `organization_list` view:
```python
STATUS_DISPLAY = [('pending','Pending'),('active','Active'),('needs_info','Needs Info'),('rejected','Rejected'),('suspended','Suspended')]
# Add to return:
return render(request, 'adminpanel/organizations/list.html', {
    'orgs': orgs,
    'status_filter': status_filter,
    'pending_count': Organization.objects.filter(status='pending').count(),
    'statuses': STATUS_DISPLAY,
})
```

- [ ] **Step 6: Add nav link in admin sidebar**

In `templates/layouts/admin.html`, inside the sidebar nav links section, add:
```html
<a href="{% url 'adminpanel:organization_list' %}"
   class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors {% if request.resolver_match.url_name|slice:':12' == 'organization' %}bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300{% endif %}">
  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
  </svg>
  Organizations
  {% if pending_org_count %}
  <span class="ml-auto bg-amber-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">{{ pending_org_count }}</span>
  {% endif %}
</a>
```

Add `pending_org_count` to `apps/adminpanel/context_processors.py`:
```python
def admin_context(request):
    if not request.user.is_authenticated:
        return {}
    from apps.accounts.models import Organization
    ctx = {}
    # existing pending verification count...
    ctx['pending_org_count'] = Organization.objects.filter(status='pending').count()
    return ctx
```

- [ ] **Step 7: Run tests**

```bash
python manage.py test apps.adminpanel.tests.OrgReviewTest --settings=config.settings.dev
```

Expected: all 5 PASS

- [ ] **Step 8: Commit**

```bash
git add apps/adminpanel/ templates/layouts/admin.html
git commit -m "feat: platform owner org review UI — approve, reject, suspend, needs-info"
```

---

### Task 5: Staff management — send invites, list staff, deactivate

**Files:**
- Modify: `apps/organizations/views.py`
- Modify: `apps/organizations/forms.py`
- Modify: `apps/organizations/services.py`
- Create: `templates/organizations/staff_list.html`
- Create: `templates/organizations/send_invite.html`

- [ ] **Step 1: Write failing tests**

```python
# apps/organizations/tests.py
class StaffManagementTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Good Clinic', slug='good-clinic', org_type='clinic', status='active'
        )
        self.owner = User.objects.create_user(
            username='owner2', email='owner2@test.com', password='pass1234!', role='org_user'
        )
        OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner', is_active=True
        )
        self.client.force_login(self.owner)

    def test_staff_list_accessible_to_hospital_owner(self):
        response = self.client.get(f'/org/good-clinic/staff/')
        self.assertEqual(response.status_code, 200)

    def test_send_invite_creates_invite_record(self):
        response = self.client.post(f'/org/good-clinic/staff/invite/', {
            'email': 'newstaff@clinic.com',
            'role': 'scheduler',
        })
        self.assertTrue(
            OrganizationInvite.objects.filter(
                organization=self.org, email='newstaff@clinic.com'
            ).exists()
        )

    def test_send_invite_role_restricted_by_grant_matrix(self):
        # hospital_admin cannot invite hospital_owner
        admin = User.objects.create_user(
            username='hadmin', email='hadmin@test.com', password='pass1234!', role='org_user'
        )
        OrganizationMembership.objects.create(
            user=admin, organization=self.org, role='hospital_admin', is_active=True
        )
        self.client.force_login(admin)
        response = self.client.post(f'/org/good-clinic/staff/invite/', {
            'email': 'newowner@clinic.com',
            'role': 'hospital_owner',
        })
        self.assertFalse(
            OrganizationInvite.objects.filter(email='newowner@clinic.com').exists()
        )
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python manage.py test apps.organizations.tests.StaffManagementTest --settings=config.settings.dev
```

- [ ] **Step 3: Add invite service**

```python
# apps/organizations/services.py — add
import secrets
import hashlib
from django.core.mail import send_mail
from django.conf import settings as django_settings
from apps.accounts.models import OrganizationInvite
from apps.accounts.permissions import get_invitable_roles


@transaction.atomic
def create_invite(organization, invited_by, email: str, role: str) -> OrganizationInvite:
    email = email.lower().strip()
    allowed = get_invitable_roles(invited_by, organization)
    if role not in allowed:
        raise PermissionDenied(f"You cannot invite someone with role '{role}'.")

    # Revoke any existing pending invite for this email+org before creating new
    OrganizationInvite.objects.filter(
        organization=organization, email=email, status='pending'
    ).update(status='revoked')

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    from django.utils import timezone
    from datetime import timedelta

    invite = OrganizationInvite.objects.create(
        organization=organization,
        invited_by=invited_by,
        email=email,
        role=role,
        token_hash=token_hash,
        status='pending',
        expires_at=timezone.now() + timedelta(days=7),
    )

    invite_url = f"{django_settings.BASE_URL}/org/invite/{raw_token}/"
    send_mail(
        subject=f"You're invited to join {organization.name} on MedConsult",
        message=(
            f"Hi,\n\nYou've been invited to join {organization.name} as {role}.\n\n"
            f"Accept your invitation here (expires in 7 days):\n{invite_url}\n\n"
            f"If you did not expect this invite, you can ignore this email."
        ),
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )
    return invite


def deactivate_membership(membership, deactivated_by):
    from django.utils import timezone
    membership.is_active = False
    membership.deactivated_at = timezone.now()
    membership.deactivated_by = deactivated_by
    membership.save(update_fields=['is_active', 'deactivated_at', 'deactivated_by'])
```

- [ ] **Step 4: Add to `accounts/permissions.py`**

Plan 1 defines `get_invitable_roles`. Verify it exists; if not, add:

```python
# apps/accounts/permissions.py
GRANT_MATRIX = {
    'hospital_owner': [
        'hospital_admin', 'doctor', 'scheduler',
        'billing_staff', 'compliance_officer', 'clinical_staff',
    ],
    'hospital_admin': ['doctor', 'scheduler', 'billing_staff', 'clinical_staff'],
    'platform_owner': [
        'platform_admin', 'hospital_owner', 'hospital_admin', 'doctor',
        'scheduler', 'billing_staff', 'compliance_officer', 'clinical_staff',
    ],
    'platform_admin': [
        'hospital_owner', 'hospital_admin', 'doctor',
        'scheduler', 'billing_staff', 'compliance_officer', 'clinical_staff',
    ],
}

def get_invitable_roles(user, organization) -> list:
    if is_platform_staff(user):
        return GRANT_MATRIX.get('platform_owner', [])
    membership = get_membership(user, organization)
    if not membership:
        return []
    return GRANT_MATRIX.get(membership.role, [])
```

- [ ] **Step 5: Implement views**

```python
# apps/organizations/views.py — replace staff_list, send_invite, deactivate_member stubs

from apps.accounts.permissions import (
    get_membership, has_org_role, can_manage_staff, get_invitable_roles, is_platform_staff
)
from apps.accounts.models import Organization, OrganizationMembership, OrganizationInvite
from .services import create_invite, deactivate_membership


def _get_org_or_403(request, org_slug):
    from django.shortcuts import get_object_or_404
    from django.core.exceptions import PermissionDenied
    org = get_object_or_404(Organization, slug=org_slug, status='active')
    if not (is_platform_staff(request.user) or
            has_org_role(request.user, org, ['hospital_owner', 'hospital_admin'])):
        raise PermissionDenied
    return org


@login_required
def staff_list(request, org_slug):
    org = _get_org_or_403(request, org_slug)
    members = OrganizationMembership.objects.filter(
        organization=org
    ).select_related('user').order_by('role', 'user__first_name')
    invites = OrganizationInvite.objects.filter(
        organization=org
    ).order_by('-created_at')
    return render(request, 'organizations/staff_list.html', {
        'org': org,
        'members': members,
        'invites': invites,
        'can_invite': can_manage_staff(request.user, org),
    })


@login_required
def send_invite(request, org_slug):
    org = _get_org_or_403(request, org_slug)
    invitable_roles = get_invitable_roles(request.user, org)
    role_choices = [(r, r.replace('_', ' ').title()) for r in invitable_roles]
    from .forms import InviteForm
    form = InviteForm(request.POST or None, role_choices=role_choices)
    if request.method == 'POST' and form.is_valid():
        try:
            create_invite(
                organization=org,
                invited_by=request.user,
                email=form.cleaned_data['email'],
                role=form.cleaned_data['role'],
            )
            messages.success(request, f"Invite sent to {form.cleaned_data['email']}.")
            return redirect(reverse('organizations:staff_list', kwargs={'org_slug': org_slug}))
        except PermissionDenied as e:
            form.add_error('role', str(e))
    return render(request, 'organizations/send_invite.html', {
        'org': org, 'form': form
    })


@login_required
def deactivate_member(request, org_slug, member_id):
    org = _get_org_or_403(request, org_slug)
    if request.method != 'POST':
        return redirect(reverse('organizations:staff_list', kwargs={'org_slug': org_slug}))
    membership = get_object_or_404(OrganizationMembership, id=member_id, organization=org)
    if membership.user == request.user:
        messages.error(request, "You cannot deactivate your own membership.")
        return redirect(reverse('organizations:staff_list', kwargs={'org_slug': org_slug}))
    deactivate_membership(membership, deactivated_by=request.user)
    messages.success(request, f"{membership.user.get_display_name()} deactivated.")
    return redirect(reverse('organizations:staff_list', kwargs={'org_slug': org_slug}))
```

- [ ] **Step 6: Add InviteForm**

```python
# apps/organizations/forms.py
class InviteForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': INPUT_CLASS}))
    role = forms.ChoiceField(widget=forms.Select(attrs={'class': SELECT_CLASS}))

    def __init__(self, *args, role_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = role_choices or []
```

- [ ] **Step 7: Create templates**

```html
<!-- templates/organizations/staff_list.html -->
{% extends "layouts/app.html" %}
{% block title %}Staff — {{ org.name }}{% endblock %}
{% block content %}
<div class="max-w-4xl mx-auto py-8 px-4">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ org.name }}</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400">Staff Management</p>
    </div>
    {% if can_invite %}
    <a href="{% url 'organizations:send_invite' org.slug %}"
       class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium">
      + Invite Staff
    </a>
    {% endif %}
  </div>

  <!-- Active members -->
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow mb-6">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
      <h2 class="font-semibold text-gray-900 dark:text-white">Active Members</h2>
    </div>
    <ul class="divide-y divide-gray-100 dark:divide-gray-700">
      {% for m in members %}
      <li class="px-6 py-4 flex items-center justify-between">
        <div>
          <p class="font-medium text-gray-900 dark:text-white text-sm">{{ m.user.get_display_name }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400">{{ m.user.email }}</p>
        </div>
        <div class="flex items-center gap-4">
          <span class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2.5 py-1 rounded-full">
            {{ m.get_role_display|default:m.role }}
          </span>
          {% if m.is_active %}
          <span class="w-2 h-2 rounded-full bg-green-500"></span>
          {% else %}
          <span class="w-2 h-2 rounded-full bg-gray-400"></span>
          {% endif %}
          {% if can_invite and m.user != request.user %}
          <form method="post" action="{% url 'organizations:deactivate_member' org.slug m.id %}"
                onsubmit="return confirm('Deactivate {{ m.user.get_display_name }}?')">
            {% csrf_token %}
            <button type="submit" class="text-xs text-red-600 dark:text-red-400 hover:underline">Deactivate</button>
          </form>
          {% endif %}
        </div>
      </li>
      {% empty %}
      <li class="px-6 py-6 text-center text-gray-500 dark:text-gray-400 text-sm">No members yet.</li>
      {% endfor %}
    </ul>
  </div>

  <!-- Pending invites -->
  {% if invites %}
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
      <h2 class="font-semibold text-gray-900 dark:text-white">Invites</h2>
    </div>
    <ul class="divide-y divide-gray-100 dark:divide-gray-700">
      {% for inv in invites %}
      <li class="px-6 py-4 flex items-center justify-between">
        <div>
          <p class="font-medium text-gray-900 dark:text-white text-sm">{{ inv.email }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400">Role: {{ inv.role }} · Sent {{ inv.created_at|date:"M j" }} · Expires {{ inv.expires_at|date:"M j" }}</p>
        </div>
        <span class="text-xs font-semibold uppercase px-2.5 py-1 rounded-full
          {% if inv.status == 'pending' %}bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300
          {% elif inv.status == 'accepted' %}bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300
          {% elif inv.status == 'expired' %}bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400
          {% else %}bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300{% endif %}">
          {{ inv.status }}
        </span>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}
</div>
{% endblock %}
```

```html
<!-- templates/organizations/send_invite.html -->
{% extends "layouts/app.html" %}
{% block title %}Invite Staff — {{ org.name }}{% endblock %}
{% block content %}
<div class="max-w-lg mx-auto py-8 px-4">
  <a href="{% url 'organizations:staff_list' org.slug %}" class="text-sm text-gray-500 dark:text-gray-400 hover:underline mb-4 inline-block">← Back to Staff</a>
  <div class="bg-white dark:bg-gray-800 rounded-2xl shadow p-8">
    <h1 class="text-xl font-bold text-gray-900 dark:text-white mb-6">Invite Staff Member</h1>
    <form method="post" class="space-y-4">
      {% csrf_token %}
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email Address</label>
        {{ form.email }}
        {% if form.email.errors %}<p class="text-red-500 text-xs mt-1">{{ form.email.errors.0 }}</p>{% endif %}
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
        {{ form.role }}
        {% if form.role.errors %}<p class="text-red-500 text-xs mt-1">{{ form.role.errors.0 }}</p>{% endif %}
      </div>
      <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl">Send Invite</button>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 8: Run tests**

```bash
python manage.py test apps.organizations.tests.StaffManagementTest --settings=config.settings.dev
```

Expected: all 3 PASS

- [ ] **Step 9: Commit**

```bash
git add apps/organizations/ templates/organizations/staff_list.html templates/organizations/send_invite.html
git commit -m "feat: staff invite lifecycle — send invites, list members, deactivate"
```

---

### Task 6: Org dashboards — hospital_owner, hospital_admin, scheduler

**Files:**
- Modify: `apps/organizations/views.py` (org_dashboard)
- Create: `templates/organizations/dashboard_owner.html`
- Create: `templates/organizations/dashboard_admin.html`
- Create: `templates/organizations/dashboard_scheduler.html`
- Create: `templates/organizations/dashboard_deferred.html`

- [ ] **Step 1: Write tests**

```python
# apps/organizations/tests.py
class OrgDashboardTest(TestCase):
    def _make_org_user(self, role):
        org = Organization.objects.create(
            name='Test Org', slug=f'test-org-{role}', org_type='clinic', status='active'
        )
        user = User.objects.create_user(
            username=f'user_{role}', email=f'{role}@test.com',
            password='pass1234!', role='org_user'
        )
        OrganizationMembership.objects.create(user=user, organization=org, role=role, is_active=True)
        return user, org

    def test_hospital_owner_sees_dashboard(self):
        user, org = self._make_org_user('hospital_owner')
        self.client.force_login(user)
        response = self.client.get(f'/org/{org.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hospital_owner')  # template role context

    def test_hospital_admin_sees_dashboard(self):
        user, org = self._make_org_user('hospital_admin')
        self.client.force_login(user)
        response = self.client.get(f'/org/{org.slug}/')
        self.assertEqual(response.status_code, 200)

    def test_scheduler_sees_dashboard(self):
        user, org = self._make_org_user('scheduler')
        self.client.force_login(user)
        response = self.client.get(f'/org/{org.slug}/')
        self.assertEqual(response.status_code, 200)

    def test_non_member_gets_403(self):
        _, org = self._make_org_user('hospital_owner')
        outsider = User.objects.create_user(
            username='outsider', email='out@test.com', password='pass1234!', role='org_user'
        )
        self.client.force_login(outsider)
        response = self.client.get(f'/org/{org.slug}/')
        self.assertEqual(response.status_code, 403)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python manage.py test apps.organizations.tests.OrgDashboardTest --settings=config.settings.dev
```

- [ ] **Step 3: Implement org_dashboard view**

```python
# apps/organizations/views.py — replace org_dashboard stub
from django.utils import timezone

DASHBOARD_TEMPLATES = {
    'hospital_owner': 'organizations/dashboard_owner.html',
    'hospital_admin': 'organizations/dashboard_admin.html',
    'scheduler': 'organizations/dashboard_scheduler.html',
    'doctor': 'organizations/dashboard_doctor_org.html',
    'billing_staff': 'organizations/dashboard_deferred.html',
    'compliance_officer': 'organizations/dashboard_deferred.html',
    'clinical_staff': 'organizations/dashboard_deferred.html',
}


@login_required
def org_dashboard(request, org_slug):
    from apps.accounts.models import Organization
    from django.core.exceptions import PermissionDenied as DjPermDenied
    org = get_object_or_404(Organization, slug=org_slug)
    if org.status not in ('active', 'pending'):
        return HttpResponseForbidden("This organization is not active.")

    # Platform staff can view any org
    if is_platform_staff(request.user):
        membership_role = 'platform_owner'
    else:
        membership = get_membership(request.user, org)
        if not membership or not membership.is_active:
            raise DjPermDenied
        membership_role = membership.role

    template = DASHBOARD_TEMPLATES.get(membership_role, 'organizations/dashboard_deferred.html')

    # Build stats context
    from apps.scheduling.models import Appointment, Slot
    from apps.accounts.models import DoctorProfile
    today = timezone.now().date()
    ctx = {
        'org': org,
        'membership_role': membership_role,
        'active_doctors': DoctorProfile.objects.filter(organization=org, user__is_active=True).count(),
        'today_appointments': Appointment.objects.filter(
            organization=org, start_datetime__date=today
        ).count(),
        'pending_invites': OrganizationInvite.objects.filter(
            organization=org, status='pending'
        ).count(),
        'pending_members': OrganizationMembership.objects.filter(
            organization=org, is_active=True
        ).count(),
    }
    return render(request, template, ctx)
```

- [ ] **Step 4: Create dashboard templates**

```html
<!-- templates/organizations/dashboard_owner.html -->
{% extends "layouts/app.html" %}
{% block title %}{{ org.name }} — Dashboard{% endblock %}
{% block content %}
<div class="max-w-5xl mx-auto py-8 px-4 space-y-6">
  <div>
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ org.name }}</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400">Hospital Owner Dashboard</p>
  </div>

  <!-- Stats -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Active Doctors</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{{ active_doctors }}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Today's Appointments</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{{ today_appointments }}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Staff Members</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{{ pending_members }}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Pending Invites</p>
      <p class="text-3xl font-bold {% if pending_invites %}text-amber-600 dark:text-amber-400{% else %}text-gray-900 dark:text-white{% endif %}">{{ pending_invites }}</p>
    </div>
  </div>

  <!-- Quick links -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <a href="{% url 'organizations:staff_list' org.slug %}"
       class="bg-white dark:bg-gray-800 rounded-xl shadow p-5 flex items-center gap-4 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-colors group">
      <div class="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
        <svg class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-gray-900 dark:text-white">Staff Management</p>
        <p class="text-sm text-gray-500 dark:text-gray-400">Invite and manage team members</p>
      </div>
    </a>
    <a href="{% url 'organizations:org_settings' org.slug %}"
       class="bg-white dark:bg-gray-800 rounded-xl shadow p-5 flex items-center gap-4 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-colors">
      <div class="w-10 h-10 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center">
        <svg class="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-gray-900 dark:text-white">Organization Settings</p>
        <p class="text-sm text-gray-500 dark:text-gray-400">Update profile, logo, contact info</p>
      </div>
    </a>
  </div>

  <!-- Analytics placeholder -->
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6 border border-dashed border-gray-300 dark:border-gray-600">
    <p class="text-sm font-semibold text-gray-500 dark:text-gray-400 text-center">Analytics dashboard — next sprint</p>
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/organizations/dashboard_admin.html -->
{% extends "layouts/app.html" %}
{% block title %}{{ org.name }} — Admin Dashboard{% endblock %}
{% block content %}
<div class="max-w-5xl mx-auto py-8 px-4 space-y-6">
  <div>
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ org.name }}</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400">Admin Dashboard</p>
  </div>
  <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Today's Appointments</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{{ today_appointments }}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Active Doctors</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{{ active_doctors }}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Pending Invites</p>
      <p class="text-3xl font-bold {% if pending_invites %}text-amber-600 dark:text-amber-400{% else %}text-gray-900 dark:text-white{% endif %}">{{ pending_invites }}</p>
    </div>
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <a href="{% url 'organizations:staff_list' org.slug %}"
       class="bg-white dark:bg-gray-800 rounded-xl shadow p-5 flex items-center gap-4 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-colors">
      <div class="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
        <svg class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
      </div>
      <div>
        <p class="font-semibold text-gray-900 dark:text-white">Manage Staff</p>
        <p class="text-sm text-gray-500 dark:text-gray-400">View team, send invites</p>
      </div>
    </a>
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/organizations/dashboard_scheduler.html -->
{% extends "layouts/app.html" %}
{% block title %}{{ org.name }} — Scheduler{% endblock %}
{% block content %}
<div class="max-w-5xl mx-auto py-8 px-4 space-y-6">
  <div>
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ org.name }}</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400">Scheduler Dashboard</p>
  </div>
  <div class="grid grid-cols-2 gap-4">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Today's Appointments</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{{ today_appointments }}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Active Doctors</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{{ active_doctors }}</p>
    </div>
  </div>
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow p-6 border border-dashed border-gray-300 dark:border-gray-600">
    <p class="text-center text-sm text-gray-500 dark:text-gray-400 font-medium">Today's schedule view — next sprint</p>
    <p class="text-center text-xs text-gray-400 dark:text-gray-500 mt-1">Book appointments on behalf of patients, view all org slots by time</p>
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/organizations/dashboard_deferred.html -->
{% extends "layouts/app.html" %}
{% block title %}{{ org.name }} — Dashboard{% endblock %}
{% block content %}
<div class="max-w-xl mx-auto py-16 px-4 text-center">
  <div class="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
    <svg class="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
    </svg>
  </div>
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-3">{{ org.name }}</h1>
  <p class="text-gray-600 dark:text-gray-400 mb-2">Welcome to MedConsult.</p>
  <p class="text-gray-500 dark:text-gray-500 text-sm">Your dashboard is being built. You'll receive an update when it's ready.</p>
  <p class="mt-4 text-xs text-gray-400 dark:text-gray-600">Role: {{ membership_role }}</p>
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests**

```bash
python manage.py test apps.organizations.tests.OrgDashboardTest --settings=config.settings.dev
```

Expected: all 4 PASS

- [ ] **Step 6: Commit**

```bash
git add apps/organizations/ templates/organizations/
git commit -m "feat: role-based org dashboards for owner, admin, scheduler, deferred roles"
```

---

### Task 7: Doctor org-aware dashboard update

**Files:**
- Create: `templates/organizations/dashboard_doctor_org.html`
- Modify: `apps/dashboard/views.py` (doctor home)

- [ ] **Step 1: Write tests**

```python
# apps/organizations/tests.py
class DoctorOrgDashboardTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Docs Clinic', slug='docs-clinic', org_type='clinic', status='active'
        )
        self.doctor = User.objects.create_user(
            username='doc1', email='doc1@test.com', password='pass1234!', role='doctor'
        )
        OrganizationMembership.objects.create(
            user=self.doctor, organization=self.org, role='doctor', is_active=True
        )
        self.client.force_login(self.doctor)

    def test_doctor_dashboard_shows_org_name(self):
        response = self.client.get(f'/org/docs-clinic/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Docs Clinic')

    def test_doctor_without_org_sees_waiting_message(self):
        solo_doc = User.objects.create_user(
            username='solo', email='solo@test.com', password='pass1234!', role='doctor'
        )
        self.client.force_login(solo_doc)
        # Solo doctor hits their own dashboard via /app/ not /org/<slug>/
        response = self.client.get('/app/')
        self.assertEqual(response.status_code, 200)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python manage.py test apps.organizations.tests.DoctorOrgDashboardTest --settings=config.settings.dev
```

- [ ] **Step 3: Create doctor org dashboard template**

```html
<!-- templates/organizations/dashboard_doctor_org.html -->
{% extends "layouts/app.html" %}
{% block title %}{{ org.name }} — Dr. {{ request.user.get_display_name }}{% endblock %}
{% block content %}
<div class="max-w-5xl mx-auto py-8 px-4 space-y-6">
  <!-- Org badge -->
  <div class="flex items-center gap-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl px-5 py-3 border border-blue-100 dark:border-blue-800">
    {% if org.logo %}
    <img src="{{ org.logo.url }}" alt="{{ org.name }}" class="w-8 h-8 rounded-md object-cover">
    {% endif %}
    <div>
      <p class="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide">Your Organization</p>
      <p class="font-semibold text-gray-900 dark:text-white text-sm">{{ org.name }}</p>
    </div>
  </div>

  <div>
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Dr. {{ request.user.get_display_name }}</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400">Your appointments and availability are scoped to {{ org.name }}</p>
  </div>

  <!-- Quick links to existing doctor views -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <a href="{% url 'doctor:doctor_dashboard' %}"
       class="bg-white dark:bg-gray-800 rounded-xl shadow p-5 flex items-center gap-4 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-colors">
      <div class="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
        <svg class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-gray-900 dark:text-white">My Schedule</p>
        <p class="text-sm text-gray-500 dark:text-gray-400">Appointments and availability</p>
      </div>
    </a>
    <a href="{% url 'doctor:doctor_availability' %}"
       class="bg-white dark:bg-gray-800 rounded-xl shadow p-5 flex items-center gap-4 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-colors">
      <div class="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
        <svg class="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-gray-900 dark:text-white">Manage Availability</p>
        <p class="text-sm text-gray-500 dark:text-gray-400">Set windows and slots</p>
      </div>
    </a>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Update doctor app home to show org context**

In `apps/dashboard/views.py`, find the doctor home view and add org context:

```python
# In apps/dashboard/views.py — doctor_dashboard or equivalent
from apps.accounts.models import OrganizationMembership
from apps.accounts.org_context import get_selected_organization

# In the view function, before render():
org_ctx = get_selected_organization(request)
memberships = OrganizationMembership.objects.filter(
    user=request.user, is_active=True
).select_related('organization')

# Add to context:
context['org_ctx'] = org_ctx
context['memberships'] = memberships
context['no_org'] = not memberships.exists() and request.user.role == 'doctor'
```

Add a banner in the doctor dashboard template (`templates/dashboard/doctor_home.html` or equivalent) at the top of `{% block content %}`:

```html
{% if no_org %}
<div class="mb-6 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl px-5 py-4 flex items-start gap-3">
  <svg class="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
  </svg>
  <div>
    <p class="font-semibold text-amber-800 dark:text-amber-300 text-sm">No organization assigned</p>
    <p class="text-amber-700 dark:text-amber-400 text-sm">You'll be added to an organization once a hospital admin invites you. Reach out to your hospital administrator.</p>
  </div>
</div>
{% elif org_ctx.organization %}
<div class="mb-4 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16"/></svg>
  <span>{{ org_ctx.organization.name }}</span>
</div>
{% endif %}
```

- [ ] **Step 5: Run tests**

```bash
python manage.py test apps.organizations.tests.DoctorOrgDashboardTest --settings=config.settings.dev
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/organizations/ apps/dashboard/ templates/organizations/dashboard_doctor_org.html
git commit -m "feat: doctor org-aware dashboard with org badge and no-org warning"
```

---

### Task 8: Organization switcher for platform staff

**Files:**
- Create: `templates/partials/org_switcher.html`
- Modify: `templates/layouts/app.html`
- Modify: `apps/accounts/org_context.py`

- [ ] **Step 1: Write tests**

```python
# apps/accounts/tests.py — add
class OrgSwitcherTest(TestCase):
    def setUp(self):
        self.platform_owner = User.objects.create_user(
            username='po_sw', email='po_sw@test.com', password='pass1234!', role='platform_owner'
        )
        self.org1 = Organization.objects.create(name='Hospital A', slug='hospital-a', org_type='hospital', status='active')
        self.org2 = Organization.objects.create(name='Hospital B', slug='hospital-b', org_type='hospital', status='active')
        self.client.force_login(self.platform_owner)

    def test_switch_org_sets_session(self):
        response = self.client.post('/auth/switch-org/', {'org_id': self.org1.id})
        self.assertEqual(self.client.session.get('active_organization_id'), self.org1.id)

    def test_switch_to_platform_view_clears_session(self):
        session = self.client.session
        session['active_organization_id'] = self.org1.id
        session.save()
        self.client.post('/auth/switch-org/', {'org_id': ''})
        self.assertIsNone(self.client.session.get('active_organization_id'))

    def test_non_platform_staff_cannot_switch(self):
        regular = User.objects.create_user(
            username='reg', email='reg@test.com', password='pass1234!', role='org_user'
        )
        self.client.force_login(regular)
        response = self.client.post('/auth/switch-org/', {'org_id': self.org1.id})
        self.assertEqual(response.status_code, 403)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python manage.py test apps.accounts.tests.OrgSwitcherTest --settings=config.settings.dev
```

- [ ] **Step 3: Add switch-org view**

```python
# apps/accounts/views.py — add at bottom
from apps.accounts.permissions import is_platform_staff
from django.http import JsonResponse, HttpResponseForbidden

@login_required
def switch_org(request):
    if not is_platform_staff(request.user):
        return HttpResponseForbidden()
    if request.method != 'POST':
        return redirect('dashboard:home')
    org_id = request.POST.get('org_id', '').strip()
    if org_id:
        from apps.accounts.models import Organization
        org = get_object_or_404(Organization, id=org_id, status='active')
        request.session['active_organization_id'] = org.id
    else:
        request.session.pop('active_organization_id', None)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)
```

Add URL in `apps/accounts/urls.py`:
```python
path('switch-org/', views.switch_org, name='switch_org'),
```

- [ ] **Step 4: Update `get_selected_organization` in org_context.py**

Plan 1 defines this. Ensure session lookup is wired:

```python
# apps/accounts/org_context.py — verify/update get_selected_organization
def get_selected_organization(request) -> OrgContext:
    from apps.accounts.permissions import is_platform_staff, get_membership, get_user_organizations
    user = request.user
    if not user.is_authenticated:
        return OrgContext(organization=None, membership=None, is_platform_scope=False, source='none')

    # 1. URL kwarg org_slug
    org_slug = request.resolver_match.kwargs.get('org_slug') if request.resolver_match else None
    if org_slug:
        from apps.accounts.models import Organization
        org = Organization.objects.filter(slug=org_slug).first()
        if org:
            if is_platform_staff(user):
                return OrgContext(organization=org, membership=None, is_platform_scope=True, source='url')
            membership = get_membership(user, org)
            if not membership or not membership.is_active:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            return OrgContext(organization=org, membership=membership, source='url')

    # 2. Session
    session_org_id = request.session.get('active_organization_id')
    if session_org_id:
        from apps.accounts.models import Organization
        org = Organization.objects.filter(id=session_org_id).first()
        if org:
            membership = None if is_platform_staff(user) else get_membership(user, org)
            return OrgContext(
                organization=org,
                membership=membership,
                is_platform_scope=is_platform_staff(user),
                source='session',
            )

    # 3. Single active membership
    orgs = get_user_organizations(user)
    if orgs.count() == 1:
        org = orgs.first()
        membership = get_membership(user, org)
        return OrgContext(organization=org, membership=membership, source='single_membership')

    # 4. Platform staff with no selection = platform view
    return OrgContext(
        organization=None,
        membership=None,
        is_platform_scope=is_platform_staff(user),
        source='none',
    )
```

- [ ] **Step 5: Create switcher partial**

```html
<!-- templates/partials/org_switcher.html -->
{% load i18n %}
{% if user.role in 'platform_owner,platform_admin' %}
<div class="relative" x-data="{ open: false }">
  <button @click="open = !open"
    class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16"/>
    </svg>
    {% if active_org %}
      {{ active_org.name }}
    {% else %}
      Platform View
    {% endif %}
    <svg class="w-3.5 h-3.5 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
    </svg>
  </button>
  <div x-show="open" @click.outside="open = false"
       class="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 z-50 py-1"
       x-cloak>
    <form method="post" action="{% url 'accounts:switch_org' %}">
      {% csrf_token %}
      <input type="hidden" name="next" value="{{ request.get_full_path }}">
      <input type="hidden" name="org_id" value="">
      <button type="submit"
        class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 {% if not active_org %}font-semibold text-blue-600 dark:text-blue-400{% endif %}">
        Platform View
      </button>
    </form>
    {% for org in all_orgs %}
    <form method="post" action="{% url 'accounts:switch_org' %}">
      {% csrf_token %}
      <input type="hidden" name="next" value="{{ request.get_full_path }}">
      <input type="hidden" name="org_id" value="{{ org.id }}">
      <button type="submit"
        class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 {% if active_org.id == org.id %}font-semibold text-blue-600 dark:text-blue-400{% endif %}">
        {{ org.name }}
        <span class="text-xs text-gray-400 dark:text-gray-500 ml-1">{{ org.get_org_type_display }}</span>
      </button>
    </form>
    {% endfor %}
  </div>
</div>
{% endif %}
```

- [ ] **Step 6: Add switcher to app navbar**

In `templates/layouts/app.html`, find the top navbar and insert the switcher before the user dropdown:

```html
{% include "partials/org_switcher.html" %}
```

Pass `active_org` and `all_orgs` via context processor in `apps/accounts/context_processors.py`:

```python
def user_info(request):
    ctx = { ... }  # existing
    # Add org switcher context for platform staff
    if request.user.is_authenticated:
        from apps.accounts.permissions import is_platform_staff
        if is_platform_staff(request.user):
            from apps.accounts.models import Organization
            ctx['all_orgs'] = Organization.objects.filter(status='active').order_by('name')
            session_org_id = request.session.get('active_organization_id')
            ctx['active_org'] = Organization.objects.filter(id=session_org_id).first() if session_org_id else None
    return ctx
```

- [ ] **Step 7: Run tests**

```bash
python manage.py test apps.accounts.tests.OrgSwitcherTest --settings=config.settings.dev
```

Expected: all 3 PASS

- [ ] **Step 8: Commit**

```bash
git add apps/accounts/ templates/partials/org_switcher.html templates/layouts/app.html
git commit -m "feat: org switcher for platform staff stored in session"
```

---

### Task 9: Org settings page

**Files:**
- Modify: `apps/organizations/views.py`
- Create: `apps/organizations/forms.py` (OrgEditForm)
- Create: `templates/organizations/settings.html`

- [ ] **Step 1: Write test**

```python
# apps/organizations/tests.py
class OrgSettingsTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Settings Clinic', slug='settings-clinic', org_type='clinic', status='active'
        )
        self.owner = User.objects.create_user(
            username='owner_s', email='owner_s@test.com', password='pass1234!', role='org_user'
        )
        OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner', is_active=True
        )
        self.client.force_login(self.owner)

    def test_settings_page_loads(self):
        response = self.client.get(f'/org/settings-clinic/settings/')
        self.assertEqual(response.status_code, 200)

    def test_can_update_org_name(self):
        self.client.post(f'/org/settings-clinic/settings/', {
            'name': 'Settings Clinic Updated',
            'org_type': 'clinic',
            'address': '',
            'phone': '',
            'website': '',
        })
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, 'Settings Clinic Updated')
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
python manage.py test apps.organizations.tests.OrgSettingsTest --settings=config.settings.dev
```

- [ ] **Step 3: Add form + view**

```python
# apps/organizations/forms.py — add OrgEditForm
class OrgEditForm(forms.Form):
    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    org_type = forms.ChoiceField(choices=ORG_TYPE_CHOICES, widget=forms.Select(attrs={'class': SELECT_CLASS}))
    address = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    website = forms.URLField(required=False, widget=forms.URLInput(attrs={'class': INPUT_CLASS}))
    logo = forms.ImageField(required=False)
```

```python
# apps/organizations/views.py — replace org_settings stub
@login_required
def org_settings(request, org_slug):
    org = get_object_or_404(Organization, slug=org_slug)
    if not (is_platform_staff(request.user) or
            has_org_role(request.user, org, ['hospital_owner', 'hospital_admin'])):
        raise PermissionDenied

    from .forms import OrgEditForm
    initial = {
        'name': org.name, 'org_type': org.org_type,
        'address': org.address, 'phone': org.phone, 'website': org.website,
    }
    form = OrgEditForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        org.name = form.cleaned_data['name']
        org.org_type = form.cleaned_data['org_type']
        org.address = form.cleaned_data.get('address', '')
        org.phone = form.cleaned_data.get('phone', '')
        org.website = form.cleaned_data.get('website', '')
        if form.cleaned_data.get('logo'):
            org.logo = form.cleaned_data['logo']
        org.save()
        messages.success(request, "Organization profile updated.")
        return redirect(reverse('organizations:org_settings', kwargs={'org_slug': org.slug}))

    return render(request, 'organizations/settings.html', {'org': org, 'form': form})
```

- [ ] **Step 4: Create template**

```html
<!-- templates/organizations/settings.html -->
{% extends "layouts/app.html" %}
{% block title %}Settings — {{ org.name }}{% endblock %}
{% block content %}
<div class="max-w-2xl mx-auto py-8 px-4">
  <a href="{% url 'organizations:org_dashboard' org.slug %}" class="text-sm text-gray-500 dark:text-gray-400 hover:underline mb-4 inline-block">← Dashboard</a>
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">Organization Settings</h1>
  <div class="bg-white dark:bg-gray-800 rounded-2xl shadow p-8">
    {% if messages %}
    {% for msg in messages %}
    <div class="mb-4 px-4 py-3 rounded-lg bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300 text-sm">{{ msg }}</div>
    {% endfor %}
    {% endif %}
    <form method="post" enctype="multipart/form-data" class="space-y-4">
      {% csrf_token %}
      {% for field in form %}
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ field.label }}</label>
        {{ field }}
        {% if field.errors %}<p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}</p>{% endif %}
      </div>
      {% endfor %}
      <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl">Save Changes</button>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Run test**

```bash
python manage.py test apps.organizations.tests.OrgSettingsTest --settings=config.settings.dev
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/organizations/ templates/organizations/settings.html
git commit -m "feat: org settings page — update name, type, contact, logo"
```

---

## Summary

**This plan builds the complete UI layer on top of the Plan 1 foundation:**

| Task | Deliverable |
|------|------------|
| 1 | `apps/organizations/` app scaffold |
| 2 | Hospital self-service signup + pending page |
| 3 | Invite acceptance with email lock + mini-register |
| 4 | Platform owner org review (approve/reject/suspend/needs-info) |
| 5 | Staff management — invite send, list, deactivate |
| 6 | Role-based org dashboards (owner/admin/scheduler/deferred) |
| 7 | Doctor org-aware dashboard + no-org warning |
| 8 | Org switcher for platform staff (session-stored) |
| 9 | Org settings page |

**Deferred to next sprint** (per spec): billing_staff dashboard, compliance_officer audit UI, clinical_staff view, org analytics charts, multi-org switcher for non-platform users.
