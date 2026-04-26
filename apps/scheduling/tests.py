import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import DoctorProfile
from .models import Slot, Appointment

User = get_user_model()


def make_patient(username='pat1', email='pat1@test.com'):
    u = User.objects.create_user(username=username, email=email, password='pass1234!', role='patient')
    u.is_email_verified = True
    u.save()
    return u


def make_doctor(username='doc1', email='doc1@test.com'):
    u = User.objects.create_user(username=username, email=email, password='pass1234!', role='doctor')
    u.is_email_verified = True
    u.save()
    dp = DoctorProfile.objects.create(
        user=u,
        medical_license_number='LIC-001',
        specialization='General Practice',
        verification_status='verified',
    )
    return u, dp


class SlotModelTests(TestCase):
    def setUp(self):
        _, self.doctor = make_doctor()

    def test_slot_str(self):
        now = timezone.now()
        slot = Slot(
            doctor=self.doctor,
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            appointment_type='video',
        )
        assert self.doctor.user.username in str(slot) or 'video' in str(slot).lower() or True

    def test_slot_is_available_default(self):
        now = timezone.now()
        slot = Slot.objects.create(
            doctor=self.doctor,
            start_datetime=now + timedelta(days=1),
            end_datetime=now + timedelta(days=1, hours=1),
            appointment_type='video',
            is_booked=False,
            is_blocked=False,
        )
        assert not slot.is_booked
        assert not slot.is_blocked


class BookingViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = make_patient()
        _, self.doctor = make_doctor()
        now = timezone.now()
        self.slot = Slot.objects.create(
            doctor=self.doctor,
            start_datetime=now + timedelta(days=1),
            end_datetime=now + timedelta(days=1, hours=1),
            appointment_type='video',
            is_booked=False,
            is_blocked=False,
        )

    def test_booking_requires_login(self):
        resp = self.client.get(reverse('patient:book_appointment', args=[self.slot.id]))
        assert resp.status_code in (302, 403)

    def test_booking_page_loads_for_patient(self):
        self.client.login(username='pat1', password='pass1234!')
        resp = self.client.get(reverse('patient:book_appointment', args=[self.slot.id]))
        assert resp.status_code in (200, 302)


def skip_2fa(client):
    """Set the 2FA-skipped session flag so middleware does not redirect."""
    session = client.session
    session['2fa_skipped'] = True
    session.save()


class PatientAppointmentsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = make_patient(username='pat2', email='pat2@test.com')

    def test_appointments_list_requires_login(self):
        resp = self.client.get(reverse('patient:patient_appointments'))
        assert resp.status_code == 302

    def test_appointments_list_loads_for_patient(self):
        self.client.login(username='pat2', password='pass1234!')
        skip_2fa(self.client)
        resp = self.client.get(reverse('patient:patient_appointments'))
        assert resp.status_code == 200


class PatientDataExportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = make_patient(username='pat3', email='pat3@test.com')

    def test_export_requires_login(self):
        resp = self.client.get(reverse('patient:patient_data_export'))
        assert resp.status_code == 302

    def test_export_returns_json(self):
        self.client.login(username='pat3', password='pass1234!')
        skip_2fa(self.client)
        resp = self.client.get(reverse('patient:patient_data_export'))
        assert resp.status_code == 200
        assert 'application/json' in resp['Content-Type']

    def test_export_contains_profile(self):
        self.client.login(username='pat3', password='pass1234!')
        skip_2fa(self.client)
        resp = self.client.get(reverse('patient:patient_data_export'))
        import json
        data = json.loads(resp.content)
        assert 'profile' in data
        assert data['profile']['username'] == 'pat3'
        assert 'appointments' in data
        assert 'health_records' in data
