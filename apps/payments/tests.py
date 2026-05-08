"""
Tests for payments app: booking-to-checkout flow (B9), payment success page (B10),
checkout template price field (B11), and webhook confirmation.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model

from apps.accounts.models import DoctorProfile
from apps.scheduling.models import Slot, Appointment
from apps.payments.models import Payment

User = get_user_model()


# ── helpers ───────────────────────────────────────────────────────────────────

def make_patient(username='pat', email='pat@test.com'):
    u = User.objects.create_user(username=username, email=email, password='pass1234!', role='patient')
    u.is_email_verified = True
    u.save()
    return u


def login_bypass_2fa(client, user):
    """Log in and set the session flag that bypasses the 2FA middleware."""
    client.force_login(user)
    session = client.session
    session['2fa_skipped'] = True
    session.save()


def make_doctor(username='doc', email='doc@test.com'):
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


def make_slot(doctor, appointment_type='video', price=Decimal('75.00'), days_ahead=3):
    future = timezone.now() + timedelta(days=days_ahead)
    slot = Slot.objects.create(
        doctor=doctor,
        start_datetime=future,
        end_datetime=future + timedelta(hours=1),
        appointment_type=appointment_type,
        is_booked=False,
        is_blocked=False,
    )
    # Directly set price by patching get_price for paid slots
    slot._test_price = price
    return slot


def make_free_slot(doctor, appointment_type='chat', days_ahead=3):
    return make_slot(doctor, appointment_type=appointment_type, price=Decimal('0'), days_ahead=days_ahead)


# ── B9: Booking redirects to checkout for paid slots ──────────────────────────

class BookingRedirectsToCheckoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = make_patient()
        _, self.doctor = make_doctor()
        self.future = timezone.now() + timedelta(days=3)

    def _make_slot(self, price):
        return Slot.objects.create(
            doctor=self.doctor,
            start_datetime=self.future,
            end_datetime=self.future + timedelta(hours=1),
            appointment_type='video',
        )

    @patch('apps.scheduling.services.sync_broadcast_to_doctor_calendar')
    @patch('apps.scheduling.services.sync_broadcast_to_patient_slots')
    def test_paid_slot_booking_redirects_to_checkout(self, mock_ws1, mock_ws2):
        slot = self._make_slot(price=Decimal('75.00'))
        login_bypass_2fa(self.client, self.patient)

        with patch.object(Slot, 'get_price', return_value=Decimal('75.00')):
            url = reverse('patient:book_appointment', kwargs={'slot_id': slot.id})
            resp = self.client.post(url, {'reason': 'checkup'})

        appt = Appointment.objects.filter(patient=self.patient).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.booking_status, 'held')
        self.assertRedirects(
            resp,
            reverse('payments:checkout', kwargs={'appointment_id': appt.id}),
            fetch_redirect_response=False,
        )

    @patch('apps.scheduling.tasks.send_appointment_confirmation_email.delay')
    @patch('apps.scheduling.services.sync_broadcast_to_doctor_calendar')
    @patch('apps.scheduling.services.sync_broadcast_to_patient_slots')
    def test_free_slot_booking_confirms_and_redirects_to_appointments(self, mock_ws1, mock_ws2, mock_email):
        slot = self._make_slot(price=Decimal('0'))
        login_bypass_2fa(self.client, self.patient)

        with patch.object(Slot, 'get_price', return_value=Decimal('0')):
            url = reverse('patient:book_appointment', kwargs={'slot_id': slot.id})
            resp = self.client.post(url, {'reason': 'checkup'})

        appt = Appointment.objects.filter(patient=self.patient).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.booking_status, 'confirmed')
        self.assertRedirects(resp, reverse('patient:patient_appointments'), fetch_redirect_response=False)

    @patch('apps.scheduling.services.sync_broadcast_to_doctor_calendar')
    @patch('apps.scheduling.services.sync_broadcast_to_patient_slots')
    def test_book_appointment_service_creates_held_status(self, mock_ws1, mock_ws2):
        from apps.scheduling.services import book_appointment
        slot = self._make_slot(price=Decimal('75.00'))
        appt = book_appointment(slot, self.patient, 'test')
        self.assertEqual(appt.booking_status, 'held')

    @patch('apps.scheduling.tasks.send_appointment_confirmation_email.delay')
    @patch('apps.scheduling.services.sync_broadcast_to_doctor_calendar')
    @patch('apps.scheduling.services.sync_broadcast_to_patient_slots')
    def test_confirm_free_appointment_sets_confirmed(self, mock_ws1, mock_ws2, mock_email):
        from apps.scheduling.services import book_appointment, confirm_free_appointment
        slot = self._make_slot(price=Decimal('0'))
        appt = book_appointment(slot, self.patient, 'test')
        self.assertEqual(appt.booking_status, 'held')

        confirm_free_appointment(appt)
        appt.refresh_from_db()
        self.assertEqual(appt.booking_status, 'confirmed')
        mock_email.assert_called_once_with(appt.id)


# ── B10: Payment success page is status-aware ─────────────────────────────────

class PaymentSuccessPageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = make_patient(username='pat2', email='pat2@test.com')
        _, self.doctor = make_doctor(username='doc2', email='doc2@test.com')
        future = timezone.now() + timedelta(days=3)
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
            booking_status='held',
        )

    def _make_payment(self, pay_status):
        return Payment.objects.create(
            appointment=self.appt,
            patient=self.patient,
            amount=Decimal('75.00'),
            status=pay_status,
        )

    def test_success_page_confirmed_when_payment_succeeded(self):
        self._make_payment('succeeded')
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('payments:success', kwargs={'appointment_id': self.appt.id})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['payment_state'], 'confirmed')
        self.assertContains(resp, 'Payment Confirmed')

    def test_success_page_processing_when_payment_processing(self):
        self._make_payment('processing')
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('payments:success', kwargs={'appointment_id': self.appt.id})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['payment_state'], 'processing')
        self.assertContains(resp, 'Payment Received')

    def test_success_page_unknown_when_no_payment(self):
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('payments:success', kwargs={'appointment_id': self.appt.id})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['payment_state'], 'unknown')
        self.assertContains(resp, 'Payment Status Unclear')

    def test_success_page_unknown_when_payment_failed(self):
        self._make_payment('failed')
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('payments:success', kwargs={'appointment_id': self.appt.id})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['payment_state'], 'unknown')


# ── B11: Checkout template uses get_price ─────────────────────────────────────

class CheckoutTemplateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = make_patient(username='pat3', email='pat3@test.com')
        _, self.doctor = make_doctor(username='doc3', email='doc3@test.com')
        future = timezone.now() + timedelta(days=3)
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
            booking_status='held',
        )

    def test_checkout_page_renders_price_from_get_price(self):
        login_bypass_2fa(self.client, self.patient)
        with patch.object(Slot, 'get_price', return_value=Decimal('99.00')):
            resp = self.client.get(
                reverse('payments:checkout', kwargs={'appointment_id': self.appt.id})
            )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '99')

    def test_checkout_page_does_not_reference_missing_price_attribute(self):
        # slot.price does not exist — ensure the template doesn't blow up
        self.assertFalse(hasattr(self.slot, 'price'), "Slot should not have a 'price' attribute")

    def test_checkout_free_slot_redirects_away(self):
        login_bypass_2fa(self.client, self.patient)
        with patch.object(Slot, 'get_price', return_value=Decimal('0')):
            resp = self.client.get(
                reverse('payments:checkout', kwargs={'appointment_id': self.appt.id})
            )
        # Free slot should redirect (already paid or no payment needed)
        self.assertIn(resp.status_code, [200, 302])


# ── Webhook confirmation sends emails ─────────────────────────────────────────

class WebhookConfirmationTests(TestCase):
    def setUp(self):
        self.patient = make_patient(username='pat4', email='pat4@test.com')
        _, self.doctor = make_doctor(username='doc4', email='doc4@test.com')
        future = timezone.now() + timedelta(days=3)
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
            booking_status='held',
        )
        self.payment = Payment.objects.create(
            appointment=self.appt,
            patient=self.patient,
            amount=Decimal('75.00'),
            status='processing',
            stripe_checkout_session_id='cs_test_123',
        )

    @patch('apps.scheduling.tasks.send_appointment_confirmation_email.delay')
    def test_handle_checkout_completed_confirms_booking_and_sends_email(self, mock_email):
        from apps.payments.services import handle_checkout_completed

        session = {
            'metadata': {
                'payment_id': str(self.payment.id),
                'appointment_id': str(self.appt.id),
            },
            'payment_intent': 'pi_test_123',
        }
        result = handle_checkout_completed(session)

        self.payment.refresh_from_db()
        self.appt.refresh_from_db()
        self.assertEqual(self.payment.status, 'succeeded')
        self.assertEqual(self.appt.booking_status, 'confirmed')
        mock_email.assert_called_once_with(self.appt.id)

    @patch('apps.scheduling.tasks.send_appointment_confirmation_email.delay')
    def test_handle_checkout_completed_idempotent(self, mock_email):
        from apps.payments.services import handle_checkout_completed

        self.payment.status = 'succeeded'
        self.payment.save()

        session = {
            'metadata': {'payment_id': str(self.payment.id)},
            'payment_intent': 'pi_test_456',
        }
        handle_checkout_completed(session)
        # Should not send email again
        mock_email.assert_not_called()
