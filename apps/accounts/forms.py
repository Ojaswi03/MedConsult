"""
Forms for accounts app - signup wizards and login.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from .models import User, PatientProfile, DoctorProfile


# Common input classes for styling
INPUT_CLASS = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
CHECKBOX_CLASS = 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
FILE_INPUT_CLASS = 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'


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

class PatientProfileForm(forms.ModelForm):
    """Patient profile form for editing."""

    class Meta:
        model = PatientProfile
        fields = ['date_of_birth', 'gender', 'gender_other', 'address', 'emergency_contact_name',
                  'emergency_contact_phone', 'medical_history', 'allergies', 'current_medications',
                  'insurance_provider', 'insurance_policy_number']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CLASS}),
            'gender': forms.Select(attrs={'class': INPUT_CLASS}),
            'gender_other': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'address': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'medical_history': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 4}),
            'allergies': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 2}),
            'current_medications': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 2}),
            'insurance_provider': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'insurance_policy_number': forms.TextInput(attrs={'class': INPUT_CLASS}),
        }


class DoctorProfileForm(forms.ModelForm):
    """Doctor profile form for editing."""

    class Meta:
        model = DoctorProfile
        fields = ['medical_license_number', 'specialization', 'years_of_experience',
                  'bio', 'education', 'consultation_fee', 'is_accepting_patients']
        widgets = {
            'medical_license_number': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'specialization': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'years_of_experience': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'bio': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 4}),
            'education': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
            'consultation_fee': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'is_accepting_patients': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }
