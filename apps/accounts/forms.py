"""
Forms for accounts app - signup wizards and login.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from .models import User, PatientProfile, DoctorProfile


# Common input classes for styling
INPUT_CLASS = 'w-full px-4 py-2 border border-gray-300 rounded-lg bg-white dark:bg-gray-700/50 dark:border-gray-600 dark:text-white dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:focus:ring-blue-400 transition-colors'
CHECKBOX_CLASS = 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded'
FILE_INPUT_CLASS = 'block w-full text-sm text-gray-500 dark:text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 dark:file:bg-blue-900/30 file:text-blue-700 dark:file:text-blue-300 hover:file:bg-blue-100 dark:hover:file:bg-blue-900/50'


# ============ LOGIN FORM ============

class LoginForm(forms.Form):
    """Login form for username OR email authentication."""

    identifier = forms.CharField(
        label='Username or Email',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Enter username or email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Enter your password'
        })
    )


# ============ PATIENT SIGNUP WIZARD FORMS ============

class PatientStep1Form(forms.Form):
    """Step 1: Account Information"""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Choose a username'
        }),
        help_text='Letters, digits and @/./+/-/_ only.'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'your@email.com'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Create a strong password'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Confirm your password'
        })
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')

        if password:
            validate_password(password)

        return cleaned_data


class PatientStep2Form(forms.Form):
    """Step 2: Personal Details"""

    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'First name'
        })
    )
    middle_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Middle name (optional)'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Last name'
        })
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': INPUT_CLASS,
            'type': 'text',
            'placeholder': 'MM/DD/YYYY',
            'id': 'date_of_birth'
        }),
        input_formats=['%m/%d/%Y', '%Y-%m-%d']
    )
    gender = forms.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        widget=forms.RadioSelect(attrs={'class': 'form-radio text-blue-600'})
    )
    gender_other = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Please specify your gender'
        })
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '(555) 123-4567',
            'id': 'phone'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        gender = cleaned_data.get('gender')
        gender_other = cleaned_data.get('gender_other')

        if gender == 'other' and not gender_other:
            self.add_error('gender_other', 'Please specify your gender.')

        return cleaned_data


class PatientStep3Form(forms.Form):
    """Step 3: Health History"""

    medical_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': INPUT_CLASS,
            'rows': 4,
            'placeholder': 'List any medical conditions, past surgeries, chronic illnesses, etc.'
        })
    )
    current_medications = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': INPUT_CLASS,
            'rows': 3,
            'placeholder': 'List current medications and dosages'
        })
    )
    allergies = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': INPUT_CLASS,
            'rows': 3,
            'placeholder': 'List any allergies (medications, food, environmental)'
        })
    )


class PatientStep4Form(forms.Form):
    """Step 4: Insurance Information"""

    insurance_provider = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'e.g., Blue Cross Blue Shield, Aetna, United Healthcare'
        })
    )
    insurance_policy_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Policy/Member ID number'
        })
    )


class PatientStep5Form(forms.Form):
    """Step 5: Verification & Terms"""

    email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS})
    )
    phone_notifications = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS})
    )
    camera_mic_tested = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        error_messages={'required': 'Please complete the camera/microphone test.'}
    )
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        error_messages={'required': 'You must accept the terms and conditions.'}
    )


# ============ DOCTOR SIGNUP WIZARD FORMS ============

class DoctorStep1Form(PatientStep1Form):
    """Step 1: Account Information (same as patient)"""
    pass


class DoctorStep2Form(PatientStep2Form):
    """Step 2: Personal Details (same as patient)"""
    pass


class DoctorStep3Form(forms.Form):
    """Step 3: Professional Credentials"""

    medical_license_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Medical License Number'
        })
    )
    medical_license_document = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': FILE_INPUT_CLASS,
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text='Upload a scan or photo of your medical license (PDF, JPG, PNG - max 10MB)'
    )
    education = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': INPUT_CLASS,
            'rows': 3,
            'placeholder': 'e.g., MD from Harvard Medical School, 2015\nResidency at Johns Hopkins, 2019'
        })
    )
    specialization = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'e.g., Cardiology, Family Medicine, Pediatrics'
        })
    )
    years_of_experience = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Years of practice'
        })
    )

    def clean_medical_license_document(self):
        document = self.cleaned_data.get('medical_license_document')
        if document:
            # Validate file size (max 10MB)
            if document.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB.')
            # Validate file type
            valid_types = ['application/pdf', 'image/jpeg', 'image/png']
            if hasattr(document, 'content_type') and document.content_type not in valid_types:
                raise forms.ValidationError('File must be PDF, JPG, or PNG.')
        return document


class DoctorStep4Form(forms.Form):
    """Step 4: Bank Information"""

    bank_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Bank name (e.g., Chase, Bank of America)'
        })
    )
    account_holder_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Name as it appears on account'
        })
    )
    account_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Account number'
        })
    )
    routing_number = forms.CharField(
        max_length=9,
        min_length=9,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '9-digit routing number'
        }),
        validators=[RegexValidator(
            regex=r'^\d{9}$',
            message='Routing number must be exactly 9 digits.'
        )]
    )


class DoctorStep5Form(forms.Form):
    """Step 5: Identity Verification"""

    government_id_document = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': FILE_INPUT_CLASS,
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text='Upload a government-issued ID (passport, driver license) - max 10MB'
    )

    def clean_government_id_document(self):
        document = self.cleaned_data.get('government_id_document')
        if document:
            if document.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB.')
            valid_types = ['application/pdf', 'image/jpeg', 'image/png']
            if hasattr(document, 'content_type') and document.content_type not in valid_types:
                raise forms.ValidationError('File must be PDF, JPG, or PNG.')
        return document


class DoctorStep6Form(forms.Form):
    """Step 6: Terms & Compliance"""

    hipaa_acknowledged = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        error_messages={'required': 'You must acknowledge HIPAA compliance requirements.'}
    )
    camera_mic_tested = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        error_messages={'required': 'Please complete the camera/microphone test.'}
    )
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        error_messages={'required': 'You must accept the terms and conditions.'}
    )


# ============ PROFILE FORMS (for editing existing profiles) ============

class UserInfoForm(forms.ModelForm):
    """Editable user-level fields for all roles."""

    class Meta:
        model = User
        fields = ['first_name', 'middle_name', 'last_name', 'username', 'email', 'phone',
                  'email_notifications', 'phone_notifications']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'middle_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'username': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': '(555) 123-4567'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'phone_notifications': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        qs = User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class PatientProfileForm(forms.ModelForm):
    """Patient profile form for editing."""

    class Meta:
        model = PatientProfile
        fields = ['date_of_birth', 'gender', 'gender_other', 'address', 'emergency_contact_name',
                  'emergency_contact_phone', 'medical_history', 'allergies', 'current_medications',
                  'insurance_provider', 'insurance_policy_number', 'preferred_language']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CLASS}),
            'gender': forms.Select(attrs={'class': INPUT_CLASS}),
            'gender_other': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Please specify'}),
            'address': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'medical_history': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 4,
                'placeholder': 'List any medical conditions, past surgeries, chronic illnesses, etc.'}),
            'allergies': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 2,
                'placeholder': 'List any allergies (medications, food, environmental)'}),
            'current_medications': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 2,
                'placeholder': 'List current medications and dosages'}),
            'insurance_provider': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'e.g., Blue Cross Blue Shield, Aetna'}),
            'insurance_policy_number': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'Policy/Member ID number'}),
            'preferred_language': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'e.g., English, Spanish'}),
        }


class DoctorProfileForm(forms.ModelForm):
    """Doctor profile form for editing."""

    class Meta:
        model = DoctorProfile
        fields = [
            # Personal
            'date_of_birth', 'gender', 'gender_other',
            # Professional
            'specialization', 'years_of_experience', 'bio', 'education',
            'languages', 'consultation_fee', 'is_accepting_patients', 'offers_second_opinions',
            # Credentials
            'medical_license_number', 'npi_number',
            # Banking
            'bank_name', 'account_holder_name', 'account_number', 'routing_number',
        ]
        labels = {
            'medical_license_number': 'Medical License Number',
            'npi_number': 'NPI Number (National Provider Identifier)',
            'offers_second_opinions': 'Offer Second Opinion Consultations',
        }
        help_texts = {
            'medical_license_number': (
                'State-specific credential that legally authorizes you to practice medicine. '
                'Issued by your state medical board. Must be renewed periodically.'
            ),
            'npi_number': (
                'Permanent 10-digit federal identifier (HIPAA-mandated) used for billing, '
                'claims, and administrative transactions nationwide. Issued once by CMS - '
                'it never changes even if you move states.'
            ),
            'languages': 'Comma-separated list, e.g.: English, Spanish, French',
            'routing_number': 'Must be exactly 9 digits.',
        }
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CLASS}),
            'gender': forms.Select(attrs={'class': INPUT_CLASS}),
            'gender_other': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Please specify'}),
            'specialization': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'e.g., Cardiology, Family Medicine, Pediatrics'}),
            'years_of_experience': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'bio': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 4,
                'placeholder': 'Brief professional biography visible to patients'}),
            'education': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3,
                'placeholder': 'e.g., MD from Harvard Medical School, 2015\nResidency at Johns Hopkins, 2019'}),
            'languages': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'e.g., English, Spanish, French'}),
            'consultation_fee': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01'}),
            'is_accepting_patients': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'offers_second_opinions': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'medical_license_number': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'State-issued license number'}),
            'npi_number': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': '10-digit NPI number', 'maxlength': '10', 'pattern': r'\d{10}'}),
            'bank_name': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'e.g., Chase, Bank of America'}),
            'account_holder_name': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': 'Name as it appears on account'}),
            'account_number': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'routing_number': forms.TextInput(attrs={'class': INPUT_CLASS,
                'placeholder': '9-digit routing number', 'maxlength': '9'}),
        }

    def clean_npi_number(self):
        npi = self.cleaned_data.get('npi_number', '').strip()
        if npi and (not npi.isdigit() or len(npi) != 10):
            raise forms.ValidationError('NPI must be exactly 10 digits.')
        return npi

    def clean_routing_number(self):
        routing = self.cleaned_data.get('routing_number', '').strip()
        if routing and (not routing.isdigit() or len(routing) != 9):
            raise forms.ValidationError('Routing number must be exactly 9 digits.')
        return routing
