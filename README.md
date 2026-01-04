# MedConsult - Telehealth Platform

A Django-based telehealth platform connecting patients with verified doctors through an intuitive slot-based appointment system.

Built with **modularity** and **clean architecture** for easy feature additions and modifications.

---

## Features

- **User Authentication**: Username/email login with role-based access (Patient, Doctor, Admin)
- **Multi-Step Signup Wizards**: Comprehensive onboarding for patients (5 steps) and doctors (6 steps)
- **Camera/Mic Testing**: Built-in telehealth readiness verification during signup
- **Doctor Profiles**: Comprehensive profiles with specializations, experience, and verification status
- **Slot-Based Scheduling**: Clean appointment system with availability windows and generated time slots
- **Doctor Availability Management**: Full self-service UI for doctors to manage their schedules
  - Visual weekly calendar with color-coded slots (available/booked/blocked/urgent)
  - Infinite calendar scrolling with arrow key navigation
  - Create/edit/delete recurring availability windows
  - Multi-type appointments per window with individual pricing
  - Buffer times before/after appointments
  - Manual/urgent slot creation
  - Block/unblock individual slots
- **Appointment Types & Pricing**: Video, Chat, Phone consultations with customizable pricing per availability window
- **Real-time Updates**: HTMX polling + WebSocket (Django Channels) for instant synchronization
- **Patient Booking**: Easy doctor discovery, live availability updates, price display, reason for visit
- **Dark Mode**: Full dark theme support with light/dark/auto preferences
- **Admin Panel**: Doctor verification queue and system oversight
- **Document Uploads**: Medical license and government ID verification for doctors
- **Responsive UI**: Built with Tailwind CSS (CDN) with dark mode support and HTMX for dynamic updates
- **WebSocket Support**: Django Channels with Redis for real-time calendar updates
- **Modular Architecture**: Services/Selectors pattern for clean code organization
- **Template Inheritance**: 4-layer system with reusable components

---

## 📁 Project Structure

```
MedConsult/
├── .github/
│   └── workflows/          # GitHub Actions CI/CD
│       ├── django-ci.yml   # Automated testing workflow
│       └── README.md
├── apps/                   # Django applications (domain isolation)
│   ├── accounts/           # User authentication & profiles
│   │   ├── models.py       # User, PatientProfile, DoctorProfile
│   │   ├── services.py     # create_user(), create_patient_from_wizard()
│   │   ├── selectors.py    # get_verified_doctors()
│   │   ├── backends.py     # EmailOrUsernameBackend (custom auth)
│   │   ├── views.py        # login, signup wizard, profile views
│   │   ├── forms.py        # Wizard forms, LoginForm
│   │   ├── urls.py         # /auth/* routes
│   │   ├── admin.py
│   │   ├── context_processors.py
│   │   └── templates/
│   │       └── accounts/
│   │           ├── wizard/     # Modular wizard components
│   │           │   ├── _progress.html
│   │           │   ├── _camera_mic_test.html
│   │           │   └── _form_field.html
│   │           ├── signup_wizard.html
│   │           └── signup_role_select.html
│   ├── scheduling/         # Appointments & availability
│   │   ├── models.py       # AvailabilityWindow, Slot, Appointment, AppointmentTypeConfig
│   │   ├── services.py     # book_appointment(), create_availability_window()
│   │   ├── selectors.py    # get_available_slots(), get_doctor_slots_for_calendar()
│   │   ├── forms.py        # AvailabilityWindowForm, ManualSlotForm
│   │   ├── views.py        # Patient & doctor views (HTMX-enabled)
│   │   ├── urls.py         # /patient/*, /doctor/* routes
│   │   └── templates/
│   │       └── scheduling/
│   │           ├── patient/
│   │           │   └── partials/     # HTMX partials for real-time updates
│   │           └── doctor/
│   │               └── partials/     # Calendar, window forms, slot cards
│   ├── dashboard/          # Role-based home pages
│   ├── adminpanel/         # Comprehensive admin panel
│   │   ├── models.py       # AdminActivityLog (audit trail)
│   │   ├── services.py     # Admin actions with logging
│   │   ├── selectors.py    # Analytics queries
│   │   ├── views.py        # 15 admin views
│   │   ├── context_processors.py  # Pending verification count
│   │   └── templates/
│   │       └── adminpanel/
│   │           ├── dashboard.html
│   │           ├── users_list.html
│   │           ├── doctors_list.html
│   │           ├── doctor_verification.html
│   │           ├── appointments_list.html
│   │           ├── financial_overview.html
│   │           ├── audit_logs.html
│   │           └── partials/     # HTMX partials for modals/tables
│   └── support/            # Help, FAQ, contact
├── config/                 # Django configuration
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py         # Common settings
│   │   ├── dev.py          # Development settings
│   │   └── prod.py         # Production settings
│   ├── urls.py             # URL routing
│   ├── wsgi.py
│   └── asgi.py
├── templates/              # Shared templates
│   ├── base.html           # Root template (Tailwind CDN)
│   ├── layouts/
│   │   ├── public.html     # Non-authenticated layout
│   │   └── app.html        # Authenticated layout (navbar + footer)
│   ├── partials/
│   │   ├── navbar.html     # Role-based navigation
│   │   ├── footer.html
│   │   └── messages.html
│   └── components/
│       ├── avatar.html     # User initials circle
│       └── dropdown.html   # Profile dropdown menu
├── static/
│   ├── css/
│   │   └── custom.css
│   └── js/
│       ├── dropdown.js           # Dropdown interactions
│       ├── signup_wizard.js      # Camera/mic test, form enhancements
│       └── availability_calendar.js # Doctor availability calendar (HTMX events)
├── manage.py               # Django management script
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── docker-compose.yml      # PostgreSQL + Redis services
├── init.sh                 # Quick start script
└── README.md
```

---

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

Run the initialization script from the project root:

```bash
./init.sh
```

This script will:
- ✅ Start PostgreSQL & Redis (Docker)
- ✅ Create Python virtual environment
- ✅ Install dependencies from requirements.txt
- ✅ Run database migrations
- ✅ Create superuser (admin@medconsult.com / admin123)

Then start the development server:

```bash
source venv/bin/activate
python manage.py runserver --settings=config.settings.dev
```

Visit: **http://127.0.0.1:8000**

---

### Option 2: Manual Setup

#### 1. Start Docker Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Verify services are running
docker-compose ps
```

#### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env if needed (default values work for local development)
```

#### 4. Run Migrations

```bash
python manage.py migrate --settings=config.settings.dev
```

#### 5. Create Superuser

```bash
python manage.py createsuperuser --settings=config.settings.dev
```

#### 6. Run Development Server

```bash
python manage.py runserver --settings=config.settings.dev
```

Visit: **http://127.0.0.1:8000**

---

## 🎯 Initial Setup & Test Data

### Create Test Data

1. **Access Django Admin**: http://127.0.0.1:8000/admin
   - Login with superuser credentials

2. **Create Doctor Account**:
   - Sign up at http://127.0.0.1:8000/auth/signup/
   - Choose "Doctor" role
   - Fill in profile details

3. **Verify Doctor** (Admin Panel):
   - Go to Admin → Doctor Profiles
   - Set verification status to "Verified"

4. **Create Availability Windows** (Django Admin):
   - Add availability windows for the doctor
   - Example: Monday 9:00 AM - 5:00 PM, 30-minute slots

5. **Generate Slots** (Doctor Dashboard):
   - Login as doctor
   - Navigate to Availability
   - Click "Generate Slots" button

6. **Book Appointment** (Patient):
   - Sign up as a patient
   - Browse doctors
   - Select available slot and book

---

## 🗺️ URL Structure

```
Public Routes:
/                           Landing page
/auth/login/                User login (username or email)
/auth/signup/               Role selection (Patient or Doctor)
/auth/signup/patient/       Patient signup wizard (5 steps)
/auth/signup/patient/<step>/ Patient wizard step
/auth/signup/doctor/        Doctor signup wizard (6 steps)
/auth/signup/doctor/<step>/ Doctor wizard step
/support/help/              Help center
/support/faq/               Frequently asked questions
/support/contact/           Contact form

Authenticated Routes:
/app/                       Role-based dashboard (auto-redirects)

Patient Routes:
/patient/doctors/           Browse verified doctors
/patient/doctors/<id>/      Doctor detail with available slots
/patient/doctors/<id>/slots/ Real-time slot updates (HTMX polling)
/patient/book/<slot_id>/    Book appointment
/patient/appointments/      My appointments

Doctor Routes:
/doctor/schedule/           My schedule (upcoming appointments)
/doctor/availability/       Manage availability (calendar + windows)
/doctor/availability/windows/create/     Create availability window
/doctor/availability/windows/<id>/update/ Update availability window
/doctor/availability/windows/<id>/delete/ Delete availability window
/doctor/availability/slots/create/       Create manual/urgent slot
/doctor/availability/slots/<id>/block/   Block a slot
/doctor/availability/slots/<id>/unblock/ Unblock a slot
/doctor/availability/slots/<id>/delete/  Delete a slot
/doctor/availability/calendar/           Calendar partial (HTMX)
/doctor/availability/types/              Configure appointment types & pricing
/doctor/generate-slots/     Generate time slots

Admin Routes:
/internal/                  Admin dashboard (analytics, metrics, charts)
/internal/verify/           Doctor verification queue
/internal/verify/<id>/approve/  Approve doctor
/internal/verify/<id>/reject/   Reject doctor with reason
/internal/users/            User management (search, filter, export)
/internal/users/<id>/       User detail view
/internal/users/<id>/toggle-active/  Activate/deactivate user
/internal/users/export/     Export users to CSV
/internal/doctors/          Doctor management with statistics
/internal/doctors/<id>/     Doctor detail with stats
/internal/doctors/<id>/document/<type>/  View doctor documents
/internal/appointments/     Appointments list (filter, search)
/internal/appointments/export/  Export appointments to CSV
/internal/financial/        Financial overview (revenue, pricing)
/internal/audit/            Audit logs (admin actions, slot changes)

System:
/admin/                     Django admin panel
```

---

## 🛠️ Development Commands

All commands should be run from the project root with the `--settings` flag:

```bash
# Database
python manage.py makemigrations --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev

# User management
python manage.py createsuperuser --settings=config.settings.dev

# Development server
python manage.py runserver --settings=config.settings.dev

# Django shell
python manage.py shell --settings=config.settings.dev

# Check for issues
python manage.py check --settings=config.settings.dev

# Create new app
python manage.py startapp <app_name> apps/<app_name>
```

### Common Tasks

```bash
# Stop Docker services
docker-compose down

# View Docker logs
docker-compose logs postgres
docker-compose logs redis

# Access PostgreSQL shell
docker-compose exec postgres psql -U medconsult_user -d medconsult

# Access Redis CLI
docker-compose exec redis redis-cli
```

---

## 💻 Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| **Backend** | Django | 5.2 |
| **WebSocket** | Django Channels | 4.0.0 |
| **ASGI Server** | Daphne | 4.0.0 |
| **Database** | PostgreSQL | 16 |
| **Cache/Channel Layer** | Redis | 7 |
| **Frontend** | Tailwind CSS | CDN (with dark mode) |
| **Dynamic UI** | HTMX | 1.9.10 |
| **JavaScript** | Vanilla JS | - |
| **Container** | Docker & Docker Compose | - |

---

## 🏗️ Modular Architecture

### Core Design Principles

MedConsult follows a **clean, modular architecture** that makes it easy to add, modify, or remove features:

1. **Domain-Driven Apps** - Each app handles one business domain
2. **Services/Selectors Pattern** - Clear separation of read/write operations
3. **Template Inheritance** - DRY principle with 4-layer template system
4. **Reusable Components** - Build once, use everywhere
5. **URL Namespacing** - No route conflicts
6. **Role-Based Architecture** - Easy to add new user roles

### App Structure (Consistent Pattern)

Every app follows this structure:

```
apps/<app_name>/
├── __init__.py
├── apps.py                 # App configuration
├── models.py               # Database models
├── services.py             # WRITE operations (create, update, delete)
├── selectors.py            # READ operations (queries, filters)
├── views.py                # HTTP request handlers
├── urls.py                 # URL routing
├── forms.py                # Django forms (optional)
├── admin.py                # Django admin configuration
├── migrations/             # Database migrations
└── templates/
    └── <app_name>/         # App-specific templates
```

**Benefits:**
- ✅ Predictable structure - know where everything is
- ✅ Easy to replicate for new apps
- ✅ Clear separation of concerns
- ✅ Independent testing

---

## 🔧 Services/Selectors Pattern

### Services (Write Operations)

Handle **creating, updating, deleting** data. All write logic lives here.

```python
# apps/scheduling/services.py

@transaction.atomic
def book_appointment(slot, patient, reason=''):
    """Book an appointment for a patient."""
    if slot.is_booked:
        raise ValueError('This slot is already booked.')

    if slot.start_datetime <= timezone.now():
        raise ValueError('Cannot book a slot in the past.')

    # Mark slot as booked
    slot.is_booked = True
    slot.save()

    # Create appointment
    appointment = Appointment.objects.create(
        slot=slot,
        patient=patient,
        doctor=slot.doctor,
        reason=reason,
        status='scheduled'
    )

    return appointment


def cancel_appointment(appointment):
    """Cancel an appointment and free the slot."""
    if not appointment.can_cancel():
        raise ValueError('This appointment cannot be cancelled.')

    # Free up the slot
    appointment.slot.is_booked = False
    appointment.slot.save()

    # Update appointment status
    appointment.status = 'cancelled'
    appointment.save()

    return appointment
```

### Selectors (Read Operations)

Handle **querying and filtering** data. All read logic lives here.

```python
# apps/scheduling/selectors.py

def get_available_slots_for_doctor(doctor_profile, start_date=None, end_date=None):
    """Get all available slots for a doctor."""
    query = Q(doctor=doctor_profile, is_booked=False, start_datetime__gt=timezone.now())

    if start_date:
        query &= Q(start_datetime__date__gte=start_date)
    if end_date:
        query &= Q(start_datetime__date__lte=end_date)

    return Slot.objects.filter(query).order_by('start_datetime')


def get_patient_appointments(patient, status=None):
    """Get all appointments for a patient."""
    query = Q(patient=patient)

    if status:
        query &= Q(status=status)

    return Appointment.objects.filter(query).select_related(
        'slot', 'doctor__user'
    ).order_by('-slot__start_datetime')
```

**Why This Pattern?**

| Benefit | Description |
|---------|-------------|
| **Centralized Logic** | Business rules in one place, not scattered across views |
| **Reusable** | Use same service from views, APIs, management commands, tests |
| **Testable** | Test logic without HTTP layer |
| **Clear Intent** | Function names reveal what they do |
| **Transaction Safety** | Easy to wrap in `@transaction.atomic` |

---

## 🎨 Template System (4 Layers)

### Layer 1: Base Template

The root template with Tailwind CDN and JavaScript includes.

```django
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}MedConsult{% endblock %}</title>

    <!-- Tailwind CSS CDN (Phase 1) -->
    <script src="https://cdn.tailwindcss.com"></script>

    {% block extra_css %}{% endblock %}
</head>
<body class="bg-gray-50">
    {% block body %}{% endblock %}

    <!-- JavaScript -->
    <script src="/static/js/dropdown.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Layer 2: Layouts

Layouts extend base and add structure (navbar, footer, etc.)

**Public Layout** (non-authenticated):
```django
<!-- templates/layouts/public.html -->
{% extends "base.html" %}

{% block body %}
<div class="min-h-screen flex flex-col">
    <header class="bg-white shadow-sm">
        <!-- Simple header with logo + login/signup -->
    </header>

    {% include 'partials/messages.html' %}

    <main class="flex-grow">
        {% block content %}{% endblock %}
    </main>

    {% include 'partials/footer.html' %}
</div>
{% endblock %}
```

**App Layout** (authenticated):
```django
<!-- templates/layouts/app.html -->
{% extends "base.html" %}

{% block body %}
<div class="min-h-screen flex flex-col">
    {% include 'partials/navbar.html' %}
    {% include 'partials/messages.html' %}

    <main class="flex-grow">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {% block content %}{% endblock %}
        </div>
    </main>

    {% include 'partials/footer.html' %}
</div>
{% endblock %}
```

### Layer 3: App-Specific Pages

Individual pages extend layouts and provide content.

```django
<!-- apps/scheduling/templates/scheduling/patient/doctors_list.html -->
{% extends "layouts/app.html" %}

{% block title %}Find Doctors - MedConsult{% endblock %}

{% block content %}
<h1 class="text-3xl font-bold text-gray-900 mb-8">Find a Doctor</h1>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    {% for doctor in doctors %}
        {% include 'components/doctor_card.html' with doctor=doctor %}
    {% endfor %}
</div>
{% endblock %}
```

### Layer 4: Reusable Components

Small, reusable pieces used across the application.

```django
<!-- templates/components/avatar.html -->
<div class="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold">
    {{ user_initials }}
</div>
```

```django
<!-- templates/components/dropdown.html -->
<div class="relative" data-dropdown>
    <button data-dropdown-trigger>
        {% include 'components/avatar.html' %}
    </button>

    <div data-dropdown-menu class="hidden absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg">
        <!-- Dropdown menu items -->
        <a href="{% url 'profile' %}">Profile</a>
        <a href="{% url 'settings' %}">Settings</a>
        <a href="{% url 'logout' %}">Log Out</a>
    </div>
</div>
```

**Usage:**
```django
{% include 'components/dropdown.html' %}
```

---

## ➕ How to Extend the Platform

### Example 1: Add a New Feature Domain

**Scenario**: Add a "Payments" feature for processing consultation fees.

**Step 1**: Create the app
```bash
python manage.py startapp payments apps/payments
```

**Step 2**: Register in settings
```python
# config/settings/base.py
INSTALLED_APPS = [
    # ...
    'apps.payments',
]
```

**Step 3**: Create models
```python
# apps/payments/models.py
from django.db import models
from apps.accounts.models import User
from apps.scheduling.models import Appointment

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_payment_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
```

**Step 4**: Create services
```python
# apps/payments/services.py
import stripe
from django.db import transaction

@transaction.atomic
def process_payment(user, appointment, amount, payment_method):
    """Process a payment via Stripe."""
    payment = Payment.objects.create(
        user=user,
        appointment=appointment,
        amount=amount,
        status='pending'
    )

    try:
        charge = stripe.Charge.create(
            amount=int(amount * 100),
            currency='usd',
            source=payment_method,
            description=f'Appointment {appointment.id}'
        )

        payment.stripe_payment_id = charge.id
        payment.status = 'completed'
        payment.save()

        return payment
    except Exception as e:
        payment.status = 'failed'
        payment.save()
        raise
```

**Step 5**: Create selectors
```python
# apps/payments/selectors.py

def get_user_payments(user):
    """Get all payments for a user."""
    return Payment.objects.filter(user=user).order_by('-created_at')

def get_payment_by_appointment(appointment):
    """Get payment for a specific appointment."""
    return Payment.objects.filter(appointment=appointment).first()
```

**Step 6**: Add views
```python
# apps/payments/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .services import process_payment

@login_required
def checkout(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)

    if request.method == 'POST':
        payment = process_payment(
            user=request.user,
            appointment=appointment,
            amount=appointment.doctor.consultation_fee,
            payment_method=request.POST.get('payment_method')
        )
        return redirect('payments:success')

    return render(request, 'payments/checkout.html', {'appointment': appointment})
```

**Step 7**: Add URLs
```python
# apps/payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/<int:appointment_id>/', views.checkout, name='checkout'),
    path('success/', views.payment_success, name='success'),
    path('history/', views.payment_history, name='history'),
]

# config/urls.py - add this line
path('payments/', include('apps.payments.urls')),
```

**Step 8**: Create templates
```django
<!-- apps/payments/templates/payments/checkout.html -->
{% extends "layouts/app.html" %}

{% block content %}
<h1>Payment Checkout</h1>
<!-- Payment form -->
{% endblock %}
```

**Step 9**: Run migrations
```bash
python manage.py makemigrations --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
```

**Done!** You've added a complete payments feature following the modular pattern.

---

### Example 2: Add a New User Role

**Scenario**: Add a "Nurse" role with specific permissions.

**Step 1**: Update User model
```python
# apps/accounts/models.py
ROLE_CHOICES = [
    ('patient', 'Patient'),
    ('doctor', 'Doctor'),
    ('nurse', 'Nurse'),  # ← Add here
    ('admin', 'Admin'),
]
```

**Step 2**: Create profile model
```python
# apps/accounts/models.py
class NurseProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nurse_profile')
    department = models.CharField(max_length=100)
    license_number = models.CharField(max_length=100)
    shift_schedule = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'nurse_profiles'
```

**Step 3**: Update navbar
```django
<!-- templates/partials/navbar.html -->
{% elif user.role == 'nurse' %}
<div class="hidden md:flex space-x-4">
    <a href="{% url 'nurse:patients' %}">My Patients</a>
    <a href="{% url 'nurse:schedule' %}">Schedule</a>
    <a href="{% url 'nurse:tasks' %}">Tasks</a>
</div>
```

**Step 4**: Create dashboard view
```python
# apps/dashboard/views.py
@login_required
def nurse_dashboard(request):
    if request.user.role != 'nurse':
        return redirect('dashboard:home')

    # Nurse-specific data
    assigned_patients = get_nurse_patients(request.user.nurse_profile)
    tasks = get_nurse_tasks(request.user.nurse_profile)

    context = {
        'patients': assigned_patients,
        'tasks': tasks,
    }
    return render(request, 'dashboard/nurse_home.html', context)
```

**Step 5**: Update dashboard router
```python
# apps/dashboard/views.py
def dashboard_home(request):
    """Route to appropriate dashboard based on role."""
    if request.user.role == 'patient':
        return patient_dashboard(request)
    elif request.user.role == 'doctor':
        return doctor_dashboard(request)
    elif request.user.role == 'nurse':
        return nurse_dashboard(request)  # ← Add here
    elif request.user.role == 'admin':
        return admin_dashboard(request)
    return redirect('landing')
```

**Step 6**: Run migrations
```bash
python manage.py makemigrations --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
```

---

### Example 3: Add a Reusable Component

**Scenario**: Create a card component for displaying information consistently.

**Step 1**: Create component template
```django
<!-- templates/components/card.html -->
<div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
    {% if icon %}
    <div class="text-{{ color|default:'blue' }}-600 mb-4">
        {{ icon|safe }}
    </div>
    {% endif %}

    <h3 class="text-xl font-semibold text-gray-900 mb-2">{{ title }}</h3>

    {% if description %}
    <p class="text-gray-600 mb-4">{{ description }}</p>
    {% endif %}

    {% if action_url %}
    <a href="{{ action_url }}"
       class="inline-block bg-{{ color|default:'blue' }}-600 text-white px-4 py-2 rounded-lg hover:bg-{{ color|default:'blue' }}-700 transition-colors">
        {{ action_text|default:'Learn More' }}
    </a>
    {% endif %}
</div>
```

**Step 2**: Use in any template
```django
<!-- Usage example -->
{% include 'components/card.html' with
    title="Book Appointment"
    description="Find and book with verified doctors in your area"
    action_url="/patient/doctors/"
    action_text="Find Doctors"
    color="blue"
%}

{% include 'components/card.html' with
    title="My Schedule"
    description="View your upcoming appointments"
    action_url="/doctor/schedule/"
    action_text="View Schedule"
    color="green"
%}
```

---

## 📋 Common Modification Examples

### Add "Favorite Doctors" Feature

**Time: ~20 minutes | Lines of code: ~35**

**1. Model (5 lines):**
```python
# apps/scheduling/models.py
class FavoriteDoctor(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_doctors')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['patient', 'doctor']
```

**2. Service (8 lines):**
```python
# apps/scheduling/services.py
def toggle_favorite_doctor(patient, doctor_profile):
    """Add or remove doctor from favorites."""
    favorite, created = FavoriteDoctor.objects.get_or_create(
        patient=patient, doctor=doctor_profile
    )
    if not created:
        favorite.delete()
        return False  # Removed
    return True  # Added
```

**3. Selector (5 lines):**
```python
# apps/scheduling/selectors.py
def get_favorite_doctors(patient):
    """Get patient's favorite doctors."""
    return FavoriteDoctor.objects.filter(
        patient=patient
    ).select_related('doctor__user')
```

**4. View (8 lines):**
```python
# apps/scheduling/views.py
@login_required
def toggle_favorite(request, doctor_id):
    if request.user.role != 'patient':
        return HttpResponseForbidden()

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    toggle_favorite_doctor(request.user, doctor)
    messages.success(request, 'Favorites updated!')
    return redirect('patient:doctor_detail', doctor_id=doctor_id)
```

**5. URL (1 line):**
```python
# apps/scheduling/urls.py
path('doctors/<int:doctor_id>/favorite/', views.toggle_favorite, name='toggle_favorite'),
```

**6. Template (8 lines):**
```django
<!-- apps/scheduling/templates/scheduling/patient/doctor_detail.html -->
<form method="post" action="{% url 'patient:toggle_favorite' doctor.id %}">
    {% csrf_token %}
    <button class="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600">
        ⭐ Favorite
    </button>
</form>
```

---

## 🎯 Best Practices

### Do's ✅

- **Keep apps focused** - One domain per app (auth, scheduling, payments)
- **Use services/selectors** - Don't put business logic in views
- **Leverage template inheritance** - Extend layouts, don't duplicate
- **Create reusable components** - Build once, use everywhere
- **Follow naming conventions** - `<verb>_<noun>()` for functions
- **Use URL namespaces** - Prevent route conflicts
- **Add docstrings** - Explain what services/selectors do
- **Run migrations** - After every model change
- **Use transactions** - Wrap multi-step operations in `@transaction.atomic`

### Don'ts ❌

- **Don't cross app boundaries excessively** - Import models sparingly
- **Don't duplicate templates** - Use `{% include %}` or `{% extends %}`
- **Don't put logic in templates** - Keep templates dumb, logic in views/services
- **Don't hardcode URLs** - Always use `{% url 'namespace:name' %}`
- **Don't skip migrations** - Always run `makemigrations` after model changes
- **Don't mix read/write** - Keep services and selectors separate
- **Don't use SELECT * queries** - Use `.select_related()` and `.prefetch_related()`

---

## 📊 Feature Status

### Authentication & User Management

| Feature | Status | Description |
|---------|--------|-------------|
| Username/Email Login | ✅ Done | Login accepts either username or email |
| Patient Signup Wizard | ✅ Done | 5-step wizard (Account → Personal → Health → Insurance → Terms) |
| Doctor Signup Wizard | ✅ Done | 6-step wizard (Account → Personal → Credentials → Bank → ID → Terms) |
| Camera/Mic Testing | ✅ Done | Cross-browser compatible telehealth readiness check |
| Gender Selection | ✅ Done | Male/Female/Other with custom text input |
| Document Uploads | ✅ Done | Medical license and government ID for doctors |
| Insurance Information | ✅ Done | Provider and policy number collection |
| Bank Information | ✅ Done | Full bank details for doctor payments |
| HIPAA Acknowledgment | ✅ Done | Compliance tracking for doctors |
| Role-based Access | ✅ Done | Patient, Doctor, Admin roles |
| Email Verification | ❌ Pending | Actual email verification flow |
| Phone Verification | ❌ Pending | SMS verification via Twilio |
| Password Reset | ❌ Pending | Forgot password functionality |
| Two-Factor Auth | ❌ Pending | 2FA for enhanced security |

### Scheduling & Appointments

| Feature | Status | Description |
|---------|--------|-------------|
| Availability Windows | ✅ Done | Doctors set available time ranges |
| Availability Management UI | ✅ Done | Full self-service UI for doctors to manage availability |
| Visual Weekly Calendar | ✅ Done | Color-coded slots (available/booked/blocked/urgent) |
| Infinite Calendar Scrolling | ✅ Done | Arrow key navigation for seamless week browsing |
| Editable Availability Windows | ✅ Done | Full edit capability with slot regeneration |
| Multi-Type Pricing | ✅ Done | Individual pricing per appointment type per window |
| Buffer Times | ✅ Done | Configure buffer before/after appointments |
| Manual/Urgent Slots | ✅ Done | Create ad-hoc urgent slots |
| Block/Unblock Slots | ✅ Done | Temporarily disable specific slots |
| Appointment Types | ✅ Done | Video, Chat, Phone consultations |
| Appointment Type Pricing | ✅ Done | Customizable pricing per availability window |
| Real-time Patient Updates | ✅ Done | HTMX polling + WebSocket for live availability |
| Smart Change Detection | ✅ Done | Notifications only when content actually changes |
| Price Display | ✅ Done | Slot prices shown on cards and booking page |
| Slot Generation | ✅ Done | Auto-generate bookable time slots per type |
| Appointment Booking | ✅ Done | Patients book with reason for visit |
| Appointment Cancellation | ✅ Done | Cancel and free up slots |
| Doctor Discovery | ✅ Done | Browse and search verified doctors |
| Appointment History | ✅ Done | View past appointments |
| Appointment Reminders | ❌ Pending | Email/SMS reminders |
| Recurring Appointments | ✅ Done | Recurring availability windows with end dates |
| Waitlist | ❌ Pending | Join waitlist for busy doctors |

### Admin & Verification

| Feature | Status | Description |
|---------|--------|-------------|
| Admin Dashboard | ✅ Done | Real-time metrics, charts, activity feeds |
| Doctor Verification Queue | ✅ Done | Enhanced with document viewer and rejection reasons |
| User Management | ✅ Done | Search/filter, activate/deactivate, CSV export |
| Doctor Management | ✅ Done | Statistics, document viewer, verification |
| Appointments Management | ✅ Done | Filter by status/type, CSV export |
| Financial Overview | ✅ Done | Revenue tracking, pricing overview |
| Audit Logging | ✅ Done | Admin actions and slot change logs |
| Document Review | ✅ Done | View medical license and government ID |
| Analytics Charts | ✅ Done | Chart.js visualizations (user growth, appointments) |

### Telehealth Features

| Feature | Status | Description |
|---------|--------|-------------|
| Camera/Mic Test | ✅ Done | Pre-consultation device check |
| Video Consultation | ❌ Pending | WebRTC video calls |
| Chat/Messaging | ❌ Pending | In-app messaging |
| Screen Sharing | ❌ Pending | Share medical images |
| Session Recording | ❌ Pending | Record consultations |

### UI/UX Features

| Feature | Status | Description |
|---------|--------|-------------|
| Dark Mode | ✅ Done | Light/dark/auto theme with user preference |
| Theme Toggle | ✅ Done | Settings page toggle with instant preview |
| WebSocket Updates | ✅ Done | Django Channels for real-time sync |
| Smart Notifications | ✅ Done | Only notify on actual content changes |
| Responsive Design | ✅ Done | Mobile-friendly with Tailwind CSS |

### Payments & Billing

| Feature | Status | Description |
|---------|--------|-------------|
| Bank Info Collection | ✅ Done | Doctor payment details |
| Insurance Info | ✅ Done | Patient insurance details |
| Payment Processing | ❌ Pending | Stripe integration |
| Invoicing | ❌ Pending | Generate invoices |
| Refunds | ❌ Pending | Process refunds |

---

## 🚀 Roadmap

### Phase 2: Core Enhancements

#### Performance & Production

- [ ] Tailwind CLI build process (purge unused CSS)
- [ ] Static file optimization and CDN
- [ ] Database query optimization
- [ ] Redis caching strategy
- [ ] Celery for background tasks

#### Features

- [ ] Video consultation (WebRTC/Twilio)
- [ ] Payment gateway (Stripe integration)
- [ ] Email notifications (appointment reminders)
- [ ] SMS notifications (Twilio)
- [ ] Prescription management
- [ ] Medical records upload
- [ ] Doctor ratings & reviews
- [ ] Advanced search & filters

#### Developer Experience

- [ ] API layer (Django REST Framework)
- [ ] API documentation (Swagger/OpenAPI)
- [ ] Comprehensive test suite
- [ ] CI/CD pipeline enhancements
- [ ] Docker production configuration
- [ ] Monitoring & logging (Sentry)

---

## 🔒 Default Credentials

**Admin:**
- Username: `admin`
- Email: `admin@medconsult.com`
- Password: `admin123`

**Test Doctor:**
- Username: `testdoctor`
- Email: `doctor@test.com`
- Password: `testpass123`

**Test Patient:**
- Username: `testpatient`
- Email: `patient@test.com`
- Password: `testpass123`

**⚠️ Change these in production!**

---

## 📊 Project Stats

| Metric | Count |
|--------|-------|
| Django Apps | 5 |
| Models | 13+ |
| Templates | 55+ |
| Python Files | 60+ |
| Lines of Code | ~8,000 |
| User Roles | 3 (Patient, Doctor, Admin) |
| HTMX Endpoints | 15+ |
| Admin Views | 15 |

---

## 🤝 Contributing

This is a proprietary project. For modifications:

1. Create a feature branch from `main`
2. Follow existing code patterns (services/selectors)
3. Add tests for new features
4. Update this README if adding major features
5. Submit pull request for review

---

## 📝 License

Proprietary - All rights reserved

---

## 🆘 Support

For issues or questions:
- Check the code comments and docstrings
- Review this README
- Check Django admin at `/admin/`
- Review server logs

---

**Built with ❤️ using Django, PostgreSQL, Redis, and Tailwind CSS**
