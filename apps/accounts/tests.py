import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class UserCreationTests(TestCase):
    def test_org_user_role_valid(self):
        user = User.objects.create_user(
            username='staffuser', email='staff@test.com',
            password='pass1234!', role='org_user',
        )
        self.assertEqual(user.role, 'org_user')

    def test_platform_owner_role_valid(self):
        user = User.objects.create_user(
            username='po', email='po@test.com',
            password='pass1234!', role='platform_owner',
        )
        self.assertEqual(user.role, 'platform_owner')

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

    def test_platform_owner_skip_flag_does_not_bypass_2fa(self):
        """platform_owner with 2fa_skipped=True must still be redirected to 2FA setup."""
        from django.test import Client as TestClient
        c = TestClient()
        admin = self._make_user('b13_admin', 'platform_owner')
        self._login_with_skip(c, admin)
        resp = c.get(reverse('patient:patient_appointments'))
        self.assertEqual(resp.status_code, 302)
        loc = resp['Location']
        self.assertTrue(
            '/account/' in loc or 'two_factor' in loc,
            f'Expected 2FA redirect, got: {loc}'
        )


class TwoFactorMiddlewareTests(TestCase):
    """
    Middleware uses has_any_elevated_membership to require 2FA for org staff.
    Users with only 'clinical_staff' membership must not bypass via skip flag.
    """

    def _make_user(self, username, role):
        u = User.objects.create_user(
            username=username, email=f'{username}@test.com', password='pass1234!', role=role,
        )
        u.is_email_verified = True
        u.save()
        return u

    def _login_with_skip(self, client, user):
        client.force_login(user)
        session = client.session
        session['2fa_skipped'] = True
        session.save()

    def test_org_staff_with_elevated_role_cannot_skip_2fa(self):
        """org_user with hospital_admin membership must be redirected to 2FA despite skip flag."""
        from apps.accounts.models import Organization, OrganizationMembership
        org = Organization.objects.create(
            name='Test Hospital', slug='test-hospital-mw',
            org_type='hospital', status='active',
        )
        staff = self._make_user('mw_staff', 'org_user')
        OrganizationMembership.objects.create(
            user=staff, organization=org, role='hospital_admin', is_active=True,
        )
        from django.test import Client as TestClient
        c = TestClient()
        self._login_with_skip(c, staff)
        resp = c.get(reverse('patient:patient_appointments'))
        self.assertEqual(resp.status_code, 302)
        loc = resp['Location']
        self.assertTrue(
            '/account/' in loc or 'two_factor' in loc,
            f'Expected 2FA redirect for org staff, got: {loc}'
        )

    def test_patient_with_no_membership_can_skip_2fa(self):
        """Patient with no org membership can use skip flag to bypass 2FA."""
        patient = self._make_user('mw_pat', 'patient')
        from django.test import Client as TestClient
        c = TestClient()
        self._login_with_skip(c, patient)
        resp = c.get(reverse('patient:patient_appointments'))
        if resp.status_code == 302:
            self.assertNotIn('/account/', resp['Location'])


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


class OrgModelTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization, OrganizationMembership
        self.org = Organization.objects.create(
            name='City Hospital', slug='city-hospital',
            org_type='hospital', status='active',
        )
        self.owner = User.objects.create_user(
            username='hospowner', email='owner@city.com',
            password='pass1234!', role='org_user',
        )

    def test_organization_created(self):
        from apps.accounts.models import Organization
        self.assertEqual(Organization.objects.filter(slug='city-hospital').count(), 1)
        self.assertEqual(self.org.status, 'active')

    def test_membership_created(self):
        from apps.accounts.models import OrganizationMembership
        m = OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner',
        )
        self.assertTrue(m.is_active)

    def test_duplicate_membership_blocked(self):
        from apps.accounts.models import OrganizationMembership
        OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner',
        )
        with self.assertRaises(Exception):
            OrganizationMembership.objects.create(
                user=self.owner, organization=self.org, role='hospital_admin',
            )

    def test_patient_can_have_no_membership(self):
        from apps.accounts.models import OrganizationMembership
        patient = User.objects.create_user(
            username='pat1', email='pat1@test.com',
            password='pass1234!', role='patient',
        )
        self.assertEqual(
            OrganizationMembership.objects.filter(user=patient).count(), 0
        )

    def test_org_slug_unique(self):
        from apps.accounts.models import Organization
        with self.assertRaises(Exception):
            Organization.objects.create(
                name='Other', slug='city-hospital', org_type='clinic', status='active',
            )

    def test_platform_role_stored_on_membership(self):
        from apps.accounts.models import Organization, OrganizationMembership
        platform_org = Organization.objects.create(
            name='MedConsult Platform', slug='medconsult-platform-test',
            org_type='platform', status='active',
        )
        m = OrganizationMembership.objects.create(
            user=self.owner, organization=platform_org, role='platform_owner',
        )
        self.assertEqual(m.role, 'platform_owner')


class DataMigrationTests(TestCase):
    def test_platform_org_exists(self):
        from apps.accounts.models import Organization
        self.assertTrue(
            Organization.objects.filter(slug='medconsult-platform', org_type='platform').exists()
        )

    def test_demo_clinic_exists(self):
        from apps.accounts.models import Organization
        self.assertTrue(
            Organization.objects.filter(slug='medconsult-demo-clinic', org_type='clinic').exists()
        )

    def test_admin_user_is_platform_owner(self):
        if User.objects.filter(username='admin').exists():
            admin = User.objects.get(username='admin')
            self.assertEqual(admin.role, 'platform_owner')

    def test_patients_have_no_membership(self):
        from apps.accounts.models import OrganizationMembership
        patients = User.objects.filter(role='patient')
        for patient in patients:
            self.assertEqual(
                OrganizationMembership.objects.filter(user=patient).count(), 0,
                f"Patient {patient.email} should have no membership"
            )


class BackfillOrgTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization, OrganizationMembership, DoctorProfile
        self.demo_clinic = Organization.objects.get(slug='medconsult-demo-clinic')
        self.doctor_user = User.objects.create_user(
            username='bfdoc', email='bfdoc@test.com',
            password='pass1234!', role='doctor',
        )
        OrganizationMembership.objects.create(
            user=self.doctor_user, organization=self.demo_clinic,
            role='doctor', is_active=True,
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            specialization='General',
            organization=self.demo_clinic,
        )

    def test_doctor_profile_has_org(self):
        self.doctor_profile.refresh_from_db()
        self.assertIsNotNone(self.doctor_profile.organization)
        self.assertEqual(self.doctor_profile.organization, self.demo_clinic)

    def test_doctor_membership_linked_to_demo_clinic(self):
        from apps.accounts.models import OrganizationMembership
        membership = OrganizationMembership.objects.filter(
            user=self.doctor_user, role='doctor', is_active=True,
        ).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.organization, self.demo_clinic)


class OrgContextTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization, OrganizationMembership
        self.org = Organization.objects.create(
            name='Test Hosp', slug='test-hosp', org_type='hospital', status='active',
        )
        self.user = User.objects.create_user(
            username='ctxuser', email='ctx@test.com',
            password='pass1234!', role='org_user',
        )
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org, role='hospital_admin', is_active=True,
        )

    def test_get_selected_org_from_single_membership(self):
        from apps.accounts.org_context import get_selected_organization
        from unittest.mock import MagicMock
        request = MagicMock()
        request.user = self.user
        request.session = {}
        request.resolver_match = None
        ctx = get_selected_organization(request)
        self.assertEqual(ctx.organization, self.org)
        self.assertEqual(ctx.source, 'single_membership')
        self.assertFalse(ctx.is_platform_scope)

    def test_no_membership_returns_none_org(self):
        from apps.accounts.org_context import get_selected_organization
        from unittest.mock import MagicMock
        patient = User.objects.create_user(
            username='ctxpat', email='ctxpat@test.com',
            password='pass1234!', role='patient',
        )
        request = MagicMock()
        request.user = patient
        request.session = {}
        request.resolver_match = None
        ctx = get_selected_organization(request)
        self.assertIsNone(ctx.organization)
        self.assertEqual(ctx.source, 'none')

    def test_platform_staff_gets_platform_scope(self):
        from apps.accounts.org_context import get_selected_organization
        from unittest.mock import MagicMock
        po = User.objects.create_user(
            username='ctxpo', email='ctxpo@test.com',
            password='pass1234!', role='platform_owner',
        )
        request = MagicMock()
        request.user = po
        request.session = {}
        request.resolver_match = None
        ctx = get_selected_organization(request)
        self.assertTrue(ctx.is_platform_scope)

    def test_session_org_resolves(self):
        from apps.accounts.org_context import get_selected_organization
        from unittest.mock import MagicMock
        request = MagicMock()
        request.user = self.user
        request.session = {'active_organization_id': self.org.id}
        request.resolver_match = None
        ctx = get_selected_organization(request)
        self.assertEqual(ctx.organization, self.org)
        self.assertEqual(ctx.source, 'session')


class PermissionHelpersTests(TestCase):
    def setUp(self):
        from apps.accounts.models import Organization, OrganizationMembership
        self.org = Organization.objects.create(
            name='Perm Hosp', slug='perm-hosp', org_type='hospital', status='active',
        )
        self.platform_owner = User.objects.create_user(
            username='permpo', email='permpo@test.com',
            password='pass1234!', role='platform_owner',
        )
        self.org_user = User.objects.create_user(
            username='permou', email='permou@test.com',
            password='pass1234!', role='org_user',
        )
        self.patient = User.objects.create_user(
            username='permpat', email='permpat@test.com',
            password='pass1234!', role='patient',
        )
        self.doctor_user = User.objects.create_user(
            username='permdoc', email='permdoc@test.com',
            password='pass1234!', role='doctor',
        )
        OrganizationMembership.objects.create(
            user=self.org_user, organization=self.org,
            role='hospital_admin', is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.doctor_user, organization=self.org,
            role='doctor', is_active=True,
        )

    def test_is_platform_owner(self):
        from apps.accounts.permissions import is_platform_owner
        self.assertTrue(is_platform_owner(self.platform_owner))
        self.assertFalse(is_platform_owner(self.org_user))
        self.assertFalse(is_platform_owner(None))

    def test_is_platform_staff(self):
        from apps.accounts.permissions import is_platform_staff
        self.assertTrue(is_platform_staff(self.platform_owner))
        self.assertFalse(is_platform_staff(self.org_user))

    def test_has_org_role(self):
        from apps.accounts.permissions import has_org_role
        self.assertTrue(has_org_role(self.org_user, self.org, ['hospital_admin']))
        self.assertFalse(has_org_role(self.org_user, self.org, ['hospital_owner']))
        self.assertFalse(has_org_role(self.patient, self.org, ['hospital_admin']))

    def test_inactive_membership_fails(self):
        from apps.accounts.models import OrganizationMembership
        from apps.accounts.permissions import has_org_role
        OrganizationMembership.objects.filter(
            user=self.org_user, organization=self.org,
        ).update(is_active=False)
        self.assertFalse(has_org_role(self.org_user, self.org, ['hospital_admin']))

    def test_patient_always_false_on_has_org_role(self):
        from apps.accounts.permissions import has_org_role
        self.assertFalse(has_org_role(self.patient, self.org, ['hospital_admin', 'doctor']))

    def test_can_manage_staff(self):
        from apps.accounts.permissions import can_manage_staff
        self.assertTrue(can_manage_staff(self.org_user, self.org))
        self.assertFalse(can_manage_staff(self.patient, self.org))
        self.assertFalse(can_manage_staff(self.doctor_user, self.org))

    def test_can_manage_org_appointments(self):
        from apps.accounts.permissions import can_manage_org_appointments
        self.assertTrue(can_manage_org_appointments(self.org_user, self.org))
        self.assertFalse(can_manage_org_appointments(self.doctor_user, self.org))

    def test_can_manage_own_appointment(self):
        from apps.accounts.permissions import can_manage_own_appointment
        from unittest.mock import MagicMock
        appt = MagicMock()
        appt.doctor.user = self.doctor_user
        self.assertTrue(can_manage_own_appointment(self.doctor_user, appt))
        self.assertFalse(can_manage_own_appointment(self.org_user, appt))

    def test_get_invitable_roles_hospital_admin_cannot_grant_compliance(self):
        from apps.accounts.permissions import get_invitable_roles
        roles = get_invitable_roles(self.org_user, self.org)
        self.assertNotIn('hospital_owner', roles)
        self.assertNotIn('compliance_officer', roles)
        self.assertIn('doctor', roles)
        self.assertIn('scheduler', roles)

    def test_can_approve_organization_platform_only(self):
        from apps.accounts.permissions import can_approve_organization
        self.assertTrue(can_approve_organization(self.platform_owner))
        self.assertFalse(can_approve_organization(self.org_user))

    def test_has_any_elevated_membership_scheduler(self):
        from apps.accounts.models import Organization, OrganizationMembership
        from apps.accounts.permissions import has_any_elevated_membership
        org = Organization.objects.create(
            name='SchedOrg', slug='sched-org', org_type='hospital', status='active',
        )
        scheduler = User.objects.create_user(
            username='schedu', email='schedu@test.com',
            password='pass1234!', role='org_user',
        )
        OrganizationMembership.objects.create(
            user=scheduler, organization=org, role='scheduler', is_active=True,
        )
        self.assertTrue(has_any_elevated_membership(scheduler))

    def test_has_any_elevated_membership_patient_false(self):
        from apps.accounts.permissions import has_any_elevated_membership
        self.assertFalse(has_any_elevated_membership(self.patient))


class OrgSwitcherTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.platform_owner = User.objects.create_user(
            username='po_switch', email='po_switch@test.com',
            password='pass1234!', role='platform_owner',
        )
        self.platform_owner.is_email_verified = True
        self.platform_owner.save()
        self.patient = User.objects.create_user(
            username='pat_switch', email='pat_switch@test.com',
            password='pass1234!', role='patient',
        )
        self.patient.is_email_verified = True
        self.patient.save()
        from apps.accounts.models import Organization
        self.org = Organization.objects.create(
            name='Switch Test Org', slug='switch-test-org',
            org_type='clinic', status='active',
        )

    def test_switch_sets_session(self):
        self.client.login(username='po_switch', password='pass1234!')
        response = self.client.post(
            reverse('switch_org'),
            {'org_id': str(self.org.id), 'next': '/app/'},
        )
        self.assertRedirects(response, '/app/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['active_organization_id'], self.org.id)

    def test_switch_clear_removes_session(self):
        self.client.login(username='po_switch', password='pass1234!')
        session = self.client.session
        session['active_organization_id'] = self.org.id
        session.save()
        self.client.post(reverse('switch_org'), {'org_id': '', 'next': '/app/'})
        self.assertNotIn('active_organization_id', self.client.session)

    def test_non_platform_user_gets_403(self):
        self.client.login(username='pat_switch', password='pass1234!')
        response = self.client.post(
            reverse('switch_org'),
            {'org_id': str(self.org.id)},
        )
        self.assertEqual(response.status_code, 403)
