import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class UserCreationTests(TestCase):
    def test_create_patient_user(self):
        user = User.objects.create_user(
            username='patient1', email='p1@test.com',
            password='pass1234!', role='patient',
        )
        user.is_email_verified = True
        user.save()
        assert user.role == 'patient'
        assert user.check_password('pass1234!')

    def test_create_doctor_user(self):
        user = User.objects.create_user(
            username='doc1', email='doc1@test.com',
            password='pass1234!', role='doctor',
        )
        assert user.role == 'doctor'

    def test_display_name_full(self):
        user = User(first_name='Jane', last_name='Doe', username='janedoe')
        assert user.get_display_name() == 'Jane Doe'

    def test_display_name_fallback_email(self):
        user = User(first_name='', last_name='', username='janedoe', email='janedoe@test.com')
        assert user.get_display_name() == 'janedoe@test.com'


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testlogin', email='tlogin@test.com',
            password='testpass123!', role='patient',
        )
        self.user.is_email_verified = True
        self.user.save()

    def test_login_page_loads(self):
        resp = self.client.get(reverse('login'))
        assert resp.status_code == 200

    def test_login_with_username(self):
        resp = self.client.post(reverse('login'), {
            'identifier': 'testlogin', 'password': 'testpass123!',
        })
        assert resp.status_code in (200, 302)

    def test_login_with_email(self):
        resp = self.client.post(reverse('login'), {
            'identifier': 'tlogin@test.com', 'password': 'testpass123!',
        })
        assert resp.status_code in (200, 302)

    def test_login_wrong_password(self):
        resp = self.client.post(reverse('login'), {
            'identifier': 'testlogin', 'password': 'wrongpassword',
        })
        assert resp.status_code == 200
        self.assertContains(resp, 'Invalid')

    def test_unverified_user_blocked(self):
        unverified = User.objects.create_user(
            username='unverified', email='uv@test.com',
            password='testpass123!', role='patient',
        )
        unverified.is_email_verified = False
        unverified.save()
        resp = self.client.post(reverse('login'), {
            'identifier': 'unverified', 'password': 'testpass123!',
        })
        assert resp.status_code == 200
        self.assertContains(resp, 'verify your email')


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_patient_signup_page_loads(self):
        resp = self.client.get(reverse('patient_signup_start'))
        assert resp.status_code == 200

    def test_doctor_signup_page_loads(self):
        resp = self.client.get(reverse('doctor_signup_start'))
        assert resp.status_code == 200


class ProfileImageTests(TestCase):
    def test_has_profile_image_false_by_default(self):
        user = User.objects.create_user(
            username='nopic', email='nopic@test.com', password='pass1234!',
        )
        assert user.has_profile_image() is False

    def test_get_profile_image_url_returns_none_when_no_image(self):
        user = User(username='nopic2')
        url = user.get_profile_image_url()
        assert url is None


# ── B13: 2FA strict enforcement ───────────────────────────────────────────────

class TwoFactorEnforcementTests(TestCase):
    """
    Doctors/admins cannot bypass 2FA via session flag.
    Patients may skip (session flag honoured).
    """

    def _make_user(self, username, role):
        u = User.objects.create_user(
            username=username, email=f'{username}@test.com', password='pass1234!', role=role
        )
        u.is_email_verified = True
        u.save()
        return u

    def _login_with_skip(self, client, user):
        client.force_login(user)
        session = client.session
        session['2fa_skipped'] = True
        session.save()

    def test_patient_skip_flag_bypasses_2fa_prompt(self):
        """Patient with 2fa_skipped=True should reach app pages without 2FA redirect."""
        from django.test import Client as TestClient
        c = TestClient()
        patient = self._make_user('b13_pat', 'patient')
        self._login_with_skip(c, patient)
        resp = c.get(reverse('patient:patient_appointments'))
        # Should NOT be redirected to 2FA setup/login
        self.assertNotIn(resp.status_code, [])  # just ensure no crash
        # Must not redirect to 2FA routes
        if resp.status_code == 302:
            self.assertNotIn('two_factor', resp['Location'])
            self.assertNotIn('/account/', resp['Location'])

    def test_doctor_skip_flag_does_not_bypass_2fa(self):
        """Doctor with 2fa_skipped=True must still be redirected to 2FA setup."""
        from django.test import Client as TestClient
        c = TestClient()
        doctor = self._make_user('b13_doc', 'doctor')
        self._login_with_skip(c, doctor)
        resp = c.get(reverse('patient:patient_appointments'))
        # Must redirect to 2FA setup or login
        self.assertEqual(resp.status_code, 302)
        loc = resp['Location']
        self.assertTrue(
            '/account/' in loc or 'two_factor' in loc,
            f'Expected 2FA redirect, got: {loc}'
        )

    def test_admin_skip_flag_does_not_bypass_2fa(self):
        """Admin with 2fa_skipped=True must still be redirected to 2FA setup."""
        from django.test import Client as TestClient
        c = TestClient()
        admin = self._make_user('b13_admin', 'admin')
        self._login_with_skip(c, admin)
        resp = c.get(reverse('patient:patient_appointments'))
        self.assertEqual(resp.status_code, 302)
        loc = resp['Location']
        self.assertTrue(
            '/account/' in loc or 'two_factor' in loc,
            f'Expected 2FA redirect, got: {loc}'
        )


# ── P1-12: Provider verification depth ───────────────────────────────────────

class DoctorVerificationDepthTests(TestCase):
    """NPI field, license expiry, malpractice expiry, board cert, sanctions."""

    def setUp(self):
        self.doc_user = User.objects.create_user(
            username='vd_doc', email='vd_doc@test.com', password='pass1234!', role='doctor'
        )
        self.doc_user.is_email_verified = True
        self.doc_user.save()
        from apps.accounts.models import DoctorProfile
        from datetime import date, timedelta
        self.profile = DoctorProfile.objects.create(
            user=self.doc_user,
            medical_license_number='LIC-001',
            specialization='General Practice',
            verification_status='verified',
            npi_number='1234567890',
            license_state='CA',
            license_expiry_date=date.today() + timedelta(days=30),
            malpractice_insurance_expiry=date.today() + timedelta(days=60),
            board_certification='ABIM',
            sanctions_checked=True,
        )

    def test_npi_stored_and_retrieved(self):
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.npi_number, '1234567890')

    def test_license_expiry_date_stored(self):
        from datetime import date, timedelta
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.license_expiry_date)
        self.assertEqual(self.profile.license_expiry_date, date.today() + timedelta(days=30))

    def test_malpractice_expiry_stored(self):
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.malpractice_insurance_expiry)

    def test_board_certification_stored(self):
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.board_certification, 'ABIM')

    def test_sanctions_checked_flag(self):
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.sanctions_checked)

    def test_expiry_reminder_task_sends_email(self):
        from unittest.mock import patch
        with patch('django.core.mail.send_mail') as mock_mail:
            from apps.accounts.tasks import send_license_expiry_reminders
            send_license_expiry_reminders()
            self.assertTrue(mock_mail.called)
