from django import forms

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
