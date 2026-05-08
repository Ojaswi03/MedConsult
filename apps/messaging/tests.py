"""
Tests for messaging app:
- P0-10: Chat XSS - escapeHtml/safeUrl present in template; send_message API sanitizes inputs
- P0-11: Direct messaging consent - doctor cannot start chat with arbitrary patient
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from apps.accounts.models import DoctorProfile
from apps.scheduling.models import Slot, Appointment
from apps.messaging.models import Conversation, Message

User = get_user_model()


# ── helpers ───────────────────────────────────────────────────────────────────

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


# ── P0-10: Chat XSS ───────────────────────────────────────────────────────────

class ChatXSSTemplateTests(TestCase):
    """Verify escapeHtml and safeUrl helpers exist in the chat template source."""

    def setUp(self):
        self.client = Client()
        self.patient = make_user('xss_pat', 'xss_pat@test.com', role='patient')
        doc_user = make_user('xss_doc', 'xss_doc@test.com', role='doctor')
        self.doctor = make_doctor_profile(doc_user)
        self.conversation = Conversation.objects.create(
            patient=self.patient,
            doctor=doc_user,
            is_direct=True,
        )

    def test_template_contains_escapeHtml_function(self):
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('messaging:conversation_detail', kwargs={'conversation_id': self.conversation.id})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'escapeHtml')

    def test_template_contains_safeUrl_function(self):
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('messaging:conversation_detail', kwargs={'conversation_id': self.conversation.id})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'safeUrl')

    def test_template_does_not_interpolate_raw_content(self):
        """message.content must always be wrapped in escapeHtml(), never bare."""
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('messaging:conversation_detail', kwargs={'conversation_id': self.conversation.id})
        )
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Bare ${message.content} without escapeHtml wrapper must not appear
        self.assertNotIn('${message.content}', content)
        self.assertNotIn('${message.attachment_name}', content)

    def test_server_side_message_content_is_auto_escaped(self):
        """Django template auto-escaping protects server-rendered messages."""
        doc_user = User.objects.get(username='xss_doc')
        Message.objects.create(
            conversation=self.conversation,
            sender=doc_user,
            content='<script>alert("xss")</script>',
            message_type='text',
        )
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.get(
            reverse('messaging:conversation_detail', kwargs={'conversation_id': self.conversation.id})
        )
        self.assertNotContains(resp, '<script>alert("xss")</script>')
        self.assertContains(resp, '&lt;script&gt;')


class SendMessageViewTests(TestCase):
    """send_message_view returns content correctly; does not execute injected HTML."""

    def setUp(self):
        self.client = Client()
        self.patient = make_user('send_pat', 'send_pat@test.com', role='patient')
        doc_user = make_user('send_doc', 'send_doc@test.com', role='doctor')
        self.doctor = make_doctor_profile(doc_user)
        self.conversation = Conversation.objects.create(
            patient=self.patient,
            doctor=doc_user,
            is_direct=True,
        )

    def test_send_text_message_returns_raw_content_in_json(self):
        """JSON response contains raw content; escaping is the JS layer's job."""
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.post(
            reverse('messaging:send_message', kwargs={'conversation_id': self.conversation.id}),
            {'content': 'Hello world'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['message']['content'], 'Hello world')

    def test_send_message_with_xss_payload_stores_raw_content(self):
        """The raw payload is stored - the frontend escapeHtml prevents execution."""
        login_bypass_2fa(self.client, self.patient)
        xss_payload = '<img src=x onerror=alert(1)>'
        resp = self.client.post(
            reverse('messaging:send_message', kwargs={'conversation_id': self.conversation.id}),
            {'content': xss_payload},
        )
        self.assertEqual(resp.status_code, 200)
        msg = Message.objects.filter(conversation=self.conversation, sender=self.patient).last()
        self.assertIsNotNone(msg)
        # Content is stored as-is (escaping in JS, not DB)
        self.assertEqual(msg.content, xss_payload)

    def test_empty_message_returns_error(self):
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.post(
            reverse('messaging:send_message', kwargs={'conversation_id': self.conversation.id}),
            {'content': ''},
        )
        self.assertEqual(resp.status_code, 400)


# ── P0-11: Direct messaging consent ───────────────────────────────────────────

class DirectMessagingConsentTests(TestCase):
    """
    A doctor should not be able to start a direct chat with an arbitrary patient
    who has no prior appointment relationship.
    """

    def setUp(self):
        self.client = Client()
        self.patient = make_user('dm_pat', 'dm_pat@test.com', role='patient')
        doc_user = make_user('dm_doc', 'dm_doc@test.com', role='doctor')
        self.doctor = make_doctor_profile(doc_user)
        self.doc_user = doc_user

        # A second patient with NO relationship to this doctor
        self.stranger = make_user('dm_stranger', 'dm_stranger@test.com', role='patient')

    def _make_appointment(self, patient):
        """Create a completed appointment between patient and doctor."""
        future = timezone.now() - timedelta(days=1)  # past = completed
        slot = Slot.objects.create(
            doctor=self.doctor,
            start_datetime=future,
            end_datetime=future + timedelta(hours=1),
            appointment_type='video',
        )
        return Appointment.objects.create(
            slot=slot,
            patient=patient,
            doctor=self.doctor,
            status='completed',
            booking_status='confirmed',
        )

    def test_doctor_can_message_patient_with_prior_appointment(self):
        self._make_appointment(self.patient)
        login_bypass_2fa(self.client, self.doc_user)
        resp = self.client.post(
            reverse('messaging:start_direct_patient', kwargs={'patient_id': self.patient.id}),
        )
        # Should allow: redirect to conversation or 200
        self.assertIn(resp.status_code, [200, 302])
        # Should NOT return 403
        self.assertNotEqual(resp.status_code, 403)

    def test_doctor_cannot_message_stranger_patient(self):
        """No prior appointment → doctor should be blocked (403 or redirect)."""
        login_bypass_2fa(self.client, self.doc_user)
        resp = self.client.post(
            reverse('messaging:start_direct_patient', kwargs={'patient_id': self.stranger.id}),
        )
        # Must not allow freely opening a chat - expect 403 or redirect to safe page
        self.assertNotEqual(resp.status_code, 200,
            "Doctor should not be able to start chat with a patient they've never seen")
        self.assertIn(resp.status_code, [403, 302])

    def test_patient_can_always_initiate_chat_with_doctor(self):
        """Patient-initiated contact is allowed regardless of appointment history."""
        login_bypass_2fa(self.client, self.patient)
        resp = self.client.post(
            reverse('messaging:start_direct_doctor', kwargs={'doctor_id': self.doctor.id}),
        )
        self.assertIn(resp.status_code, [200, 302])
        self.assertNotEqual(resp.status_code, 403)
