"""
Tests for consultations app:
- P1-11: Pre-visit readiness check — GET renders checklist, POST with
  confirmation redirects to join, POST without confirmation re-shows form.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from apps.accounts.models import DoctorProfile
from apps.scheduling.models import Slot, Appointment

User = get_user_model()


def make_user(username, email, role='patient'):
    u = User.objects.create_user(username=username, email=email, password='pass1234!', role=role)
    u.is_email_verified = True
    u.save()
    return u


def make_doctor_profile(user):
    return DoctorProfile.objects.create(
        user=user,
        medical_license_number='LIC-001',
        specialization='General Practice',
        verification_status='verified',
    )


def login_bypass_2fa(client, user):
    client.force_login(user)
    session = client.session
    session['2fa_skipped'] = True
    session.save()


class PreVisitReadinessTests(TestCase):
    """P1-11: Pre-visit readiness check page."""

    def setUp(self):
        self.client = Client()
        self.patient = make_user('rv_pat', 'rv_pat@test.com', role='patient')
        doc_user = make_user('rv_doc', 'rv_doc@test.com', role='doctor')
        self.doctor = make_doctor_profile(doc_user)
        self.doc_user = doc_user

        future = timezone.now() + timedelta(hours=1)
        self.slot = Slot.objects.create(
            doctor=self.doctor,
            start_datetime=future,
            end_datetime=future + timedelta(hours=1),
            appointment_type='video',
        )
        self.appt = Appointment.objects.create(
            slot=self.slot,
            patient=self.patient,
            doctor=self.doctor,
            status='scheduled',
            booking_status='confirmed',
        )

    def _url(self):
        return reverse('consultations:pre_visit_readiness', kwargs={'appointment_id': self.appt.id})

    def test_get_renders_checklist(self):
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'private location')
        self.assertContains(resp, 'camera and microphone')
        self.assertContains(resp, 'consent')

    def test_post_confirmed_redirects_to_join(self):
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.post(self._url(), {
            'readiness_confirmed': '1',
            'check_privacy': 'on',
            'check_device': 'on',
            'check_internet': 'on',
            'check_consent': 'on',
        })
        self.assertRedirects(
            resp,
            reverse('consultations:join', kwargs={'appointment_id': self.appt.id}),
            fetch_redirect_response=False,
        )

    def test_post_unconfirmed_re_renders_form(self):
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.post(self._url(), {})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'private location')

    def test_stranger_cannot_access(self):
        stranger = make_user('rv_stranger', 'rv_stranger@test.com', role='patient')
        login_bypass_2fa(self.client, stranger)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('private location', resp.content.decode())

    def test_unauthenticated_redirected(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 302)
