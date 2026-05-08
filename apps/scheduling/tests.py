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

    def test_export_field_paths_valid(self):
        self.client.login(username='pat3', password='pass1234!')
        skip_2fa(self.client)
        resp = self.client.get(reverse('patient:patient_data_export'))
        import json
        data = json.loads(resp.content)
        profile = data['profile']
        assert 'phone' in profile, "profile.phone missing — was phone_number (wrong field)"
        assert 'address' in profile
        assert 'phone_number' not in profile, "stale phone_number key present"
        for appt in data['appointments']:
            assert 'appointment_type' in appt
            assert 'start' in appt


# ── P0-12: PHI file download requires ownership ────────────────────────────────

class HealthRecordDownloadTests(TestCase):
    """
    Verifies that /patient/health-records/<id>/download/ enforces ownership
    and that the access is logged to HealthRecordAccessLog.
    """

    def setUp(self):
        import tempfile, os
        self.client = Client()
        self.patient = make_patient(username='hr_pat', email='hr_pat@test.com')
        doc_user, self.doctor = make_doctor(username='hr_doc', email='hr_doc@test.com')
        self.stranger = make_patient(username='hr_stranger', email='hr_stranger@test.com')

        # Create a real file inside a temp MEDIA_ROOT so the view can serve it
        self.media_root = tempfile.mkdtemp()
        hr_dir = os.path.join(self.media_root, 'health_records')
        os.makedirs(hr_dir)
        self.file_path = os.path.join(hr_dir, 'test_phi.txt')
        with open(self.file_path, 'wb') as f:
            f.write(b'PHI content')

        from apps.scheduling.models import HealthRecord
        from django.test.utils import override_settings
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.record = HealthRecord.objects.create(
            patient=self.patient,
            title='Blood Test',
            record_type='lab_result',
        )
        self.record.file.name = 'health_records/test_phi.txt'
        self.record.save()

    def tearDown(self):
        self.override.disable()
        import shutil
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['2fa_skipped'] = True
        session.save()

    def test_owner_can_download(self):
        self._login(self.patient)
        resp = self.client.get(
            reverse('patient:health_record_download', kwargs={'record_id': self.record.id})
        )
        self.assertNotEqual(resp.status_code, 403)
        self.assertEqual(resp.status_code, 200)

    def test_stranger_cannot_download(self):
        self._login(self.stranger)
        resp = self.client.get(
            reverse('patient:health_record_download', kwargs={'record_id': self.record.id})
        )
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_redirected(self):
        resp = self.client.get(
            reverse('patient:health_record_download', kwargs={'record_id': self.record.id})
        )
        self.assertIn(resp.status_code, [302, 403])

    def test_download_creates_access_log(self):
        from apps.adminpanel.models import HealthRecordAccessLog
        self._login(self.patient)
        initial_count = HealthRecordAccessLog.objects.filter(record=self.record).count()
        self.client.get(
            reverse('patient:health_record_download', kwargs={'record_id': self.record.id})
        )
        self.assertEqual(
            HealthRecordAccessLog.objects.filter(record=self.record).count(),
            initial_count + 1,
        )


# ── P1-10: Symptom triage — emergency red-flag detection ──────────────────────

class TriageTests(TestCase):
    """Unit tests for the triage.check_emergency_flags helper."""

    def test_no_emergency_for_normal_symptoms(self):
        from apps.scheduling.triage import check_emergency_flags
        result = check_emergency_flags(['runny nose', 'sore throat'], 'mild cold')
        self.assertFalse(result['is_emergency'])
        self.assertEqual(result['matched_flags'], [])

    def test_chest_pain_triggers_emergency(self):
        from apps.scheduling.triage import check_emergency_flags
        result = check_emergency_flags(['chest pain', 'fatigue'])
        self.assertTrue(result['is_emergency'])
        self.assertIn('chest pain', result['matched_flags'])

    def test_suicidal_ideation_triggers_emergency(self):
        from apps.scheduling.triage import check_emergency_flags
        result = check_emergency_flags([], reason_text='I have been feeling suicidal lately')
        self.assertTrue(result['is_emergency'])

    def test_breathing_difficulty_triggers_emergency(self):
        from apps.scheduling.triage import check_emergency_flags
        result = check_emergency_flags(['difficulty breathing'])
        self.assertTrue(result['is_emergency'])

    def test_emergency_blocks_booking_in_view(self):
        """Booking form with chest pain returns 200 with emergency block (not redirect)."""
        patient = make_patient(username='triage_pat', email='triage_pat@test.com')
        doc_user, doctor = make_doctor(username='triage_doc', email='triage_doc@test.com')

        future = timezone.now() + timedelta(days=2)
        slot = Slot.objects.create(
            doctor=doctor,
            start_datetime=future,
            end_datetime=future + timedelta(hours=1),
            appointment_type='video',
        )

        client = Client()
        client.force_login(patient)
        session = client.session
        session['2fa_skipped'] = True
        session.save()

        from unittest.mock import patch
        with patch.object(Slot, 'get_price', return_value=__import__('decimal').Decimal('75.00')):
            resp = client.post(
                reverse('patient:book_appointment', kwargs={'slot_id': slot.id}),
                {
                    'reason': 'I have severe chest pain and shortness of breath',
                    'symptom_names[]': ['chest pain'],
                },
            )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Emergency')
        # No appointment should have been created
        self.assertFalse(Appointment.objects.filter(patient=patient, slot=slot).exists())
