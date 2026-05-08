import secrets
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from django_cryptography.fields import encrypt


class UserManager(BaseUserManager):
    """Custom user manager for username/email-based authentication."""

    def create_user(self, email, password=None, username=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        if not username:
            raise ValueError(_('The Username field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, username=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, username=username, **extra_fields)


class User(AbstractUser):
    """Custom user model with username/email authentication and role-based access."""

    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('admin', 'Admin'),
    ]

    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'System'),
    ]

    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[AbstractUser.username_validator],
        error_messages={
            'unique': _('A user with that username already exists.'),
        },
    )
    email = models.EmailField(_('email address'), unique=True)
    middle_name = models.CharField(_('middle name'), max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')
    phone = models.CharField(max_length=20, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    email_notifications = models.BooleanField(default=True)
    phone_notifications = models.BooleanField(default=False)
    theme_preference = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default='light',
        help_text='User interface theme preference'
    )
    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        null=True,
        help_text='Profile picture (PNG, JPG, JPEG)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.email

    def get_display_name(self):
        """Return full name or email."""
        parts = [self.first_name, self.middle_name, self.last_name]
        full_name = ' '.join(filter(None, parts))
        return full_name if full_name else self.email

    def get_initials(self):
        """Return user initials for avatar."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        elif self.first_name:
            return self.first_name[0].upper()
        return self.email[0].upper()

    def get_profile_image_url(self):
        """Return profile image URL or None."""
        if self.profile_image:
            return self.profile_image.url
        return None

    def has_profile_image(self):
        """Check if user has a profile image."""
        return bool(self.profile_image)


class PatientProfile(models.Model):
    """Extended profile for patients."""

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    gender_other = models.CharField(max_length=50, blank=True, help_text='Specify if gender is Other')
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    medical_history = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)
    insurance_provider = models.CharField(max_length=200, blank=True)
    insurance_policy_number = models.CharField(max_length=100, blank=True)
    preferred_language = models.CharField(max_length=50, blank=True, help_text='Patient preferred language for consultations')
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'patient_profiles'

    def __str__(self):
        return f"Patient Profile: {self.user.get_display_name()}"


class DoctorProfile(models.Model):
    """Extended profile for doctors."""

    VERIFICATION_STATUS = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')

    # Personal details
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    gender_other = models.CharField(max_length=50, blank=True, help_text='Specify if gender is Other')

    # Professional credentials
    medical_license_number = encrypt(models.CharField(max_length=100, blank=True, null=True))
    medical_license_document = models.FileField(
        upload_to='documents/licenses/',
        blank=True,
        null=True,
        help_text='Upload medical license document (PDF, JPG, PNG)'
    )
    specialization = models.CharField(max_length=100)
    years_of_experience = models.IntegerField(default=0)
    bio = models.TextField(blank=True)
    education = models.TextField(blank=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Identity verification
    government_id_document = models.FileField(
        upload_to='documents/government_ids/',
        blank=True,
        null=True,
        help_text='Upload government ID (passport, driver license)'
    )

    # Bank information
    bank_name = models.CharField(max_length=200, blank=True)
    account_holder_name = models.CharField(max_length=200, blank=True)
    account_number = encrypt(models.CharField(max_length=50, blank=True, null=True))
    routing_number = encrypt(models.CharField(max_length=50, blank=True, null=True))

    # Verification status
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='pending'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    is_accepting_patients = models.BooleanField(default=True)

    languages = models.CharField(max_length=200, blank=True, help_text='Comma-separated languages spoken (e.g., English, Spanish)')
    npi_number = models.CharField(max_length=20, blank=True, help_text='National Provider Identifier (10-digit NPI)')
    offers_second_opinions = models.BooleanField(default=False, help_text='Whether doctor offers second opinion consultations')

    # Verification depth (P1-12)
    license_state = models.CharField(max_length=50, blank=True, help_text='State where license was issued')
    license_expiry_date = models.DateField(null=True, blank=True, help_text='Medical license expiry date')
    malpractice_insurance_expiry = models.DateField(null=True, blank=True, help_text='Malpractice insurance expiry date')
    board_certification = models.CharField(max_length=200, blank=True, help_text='Board certification(s)')
    sanctions_checked = models.BooleanField(default=False, help_text='Admin confirmed sanctions/exclusions check performed')

    # Compliance
    hipaa_acknowledged = models.BooleanField(default=False)
    hipaa_acknowledged_at = models.DateTimeField(null=True, blank=True)
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'doctor_profiles'

    def __str__(self):
        return f"Dr. {self.user.get_display_name()} - {self.specialization}"

    @property
    def average_rating(self):
        """Calculate average rating from all visible reviews."""
        from django.db.models import Avg
        result = self.reviews.filter(is_visible=True).aggregate(Avg('rating'))
        return result['rating__avg'] or 0

    @property
    def review_count(self):
        """Count of all visible reviews."""
        return self.reviews.filter(is_visible=True).count()

    @property
    def rating_distribution(self):
        """Get count of reviews for each rating (1-5 stars)."""
        from django.db.models import Count
        distribution = {i: 0 for i in range(1, 6)}
        counts = self.reviews.filter(is_visible=True).values('rating').annotate(count=Count('rating'))
        for item in counts:
            distribution[item['rating']] = item['count']
        return distribution

    @property
    def onboarding_score(self):
        """Return 0-100 completion score across 8 profile dimensions."""
        score = 0
        if self.bio and len(self.bio) >= 50:
            score += 15
        if self.education:
            score += 10
        if self.user.has_profile_image():
            score += 15
        if self.languages:
            score += 10
        if self.npi_number:
            score += 10
        if self.availability_windows.filter(is_active=True).exists():
            score += 20
        if self.appointment_type_configs.filter(is_enabled=True).exists():
            score += 10
        if self.consultation_fee and self.consultation_fee > 0:
            score += 10
        return score


class Notification(models.Model):
    """In-app notification for users."""
    NOTIF_TYPES = [
        ('appointment_booked', 'Appointment Booked'),
        ('appointment_cancelled', 'Appointment Cancelled'),
        ('appointment_reminder', 'Appointment Reminder'),
        ('appointment_rescheduled', 'Appointment Rescheduled'),
        ('doctor_verified', 'Doctor Verified'),
        ('doctor_rejected', 'Doctor Rejected'),
        ('new_review', 'New Review'),
        ('prescription_ready', 'Prescription Ready'),
        ('waitlist_slot_available', 'Slot Available'),
        ('referral_received', 'Referral Received'),
        ('health_record_shared', 'Health Record Shared'),
        ('patient_waiting', 'Patient in Waiting Room'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=50, choices=NOTIF_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read', 'created_at'], name='notif_user_read_idx')]

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class EmailVerificationToken(models.Model):
    """Token for email verification."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verification_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'email_verification_tokens'

    def __str__(self):
        return f"Verification token for {self.user.email}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired


class PasswordResetToken(models.Model):
    """Token for password reset."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'password_reset_tokens'

    def __str__(self):
        return f"Password reset token for {self.user.email}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired
