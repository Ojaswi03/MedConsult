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

    def test_display_name_fallback_username(self):
        user = User(first_name='', last_name='', username='janedoe')
        assert user.get_display_name() == 'janedoe'


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
        resp = self.client.get(reverse('patient_signup'))
        assert resp.status_code == 200

    def test_doctor_signup_page_loads(self):
        resp = self.client.get(reverse('doctor_signup'))
        assert resp.status_code == 200


class ProfileImageTests(TestCase):
    def test_has_profile_image_false_by_default(self):
        user = User.objects.create_user(
            username='nopic', email='nopic@test.com', password='pass1234!',
        )
        assert user.has_profile_image() is False

    def test_get_profile_image_url_default(self):
        user = User(username='nopic2')
        url = user.get_profile_image_url()
        assert url is not None
