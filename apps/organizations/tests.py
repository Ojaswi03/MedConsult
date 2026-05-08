from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import User, Organization, OrganizationMembership


class OrgRegisterTest(TestCase):
    def _post_valid(self):
        return self.client.post(reverse('organizations:org_register'), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@cityhospital.com',
            'password1': 'Str0ng!Pass',
            'password2': 'Str0ng!Pass',
            'org_name': 'City General Hospital',
            'org_type': 'hospital',
            'address': '123 Main St',
            'phone': '555-0100',
        })

    def test_creates_user_with_org_user_role(self):
        self._post_valid()
        user = User.objects.get(email='jane@cityhospital.com')
        self.assertEqual(user.role, 'org_user')

    def test_creates_org_with_pending_status(self):
        self._post_valid()
        org = Organization.objects.get(name='City General Hospital')
        self.assertEqual(org.status, 'pending')

    def test_creates_hospital_owner_membership(self):
        self._post_valid()
        user = User.objects.get(email='jane@cityhospital.com')
        org = Organization.objects.get(name='City General Hospital')
        membership = OrganizationMembership.objects.get(user=user, organization=org)
        self.assertEqual(membership.role, 'hospital_owner')

    def test_redirects_to_pending_page(self):
        response = self._post_valid()
        self.assertRedirects(response, reverse('organizations:org_register_pending'))

    def test_duplicate_email_shows_error(self):
        User.objects.create_user(
            username='existing', email='jane@cityhospital.com',
            password='pass', role='patient',
        )
        response = self._post_valid()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

    def test_mismatched_passwords_shows_error(self):
        response = self.client.post(reverse('organizations:org_register'), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'other@test.com',
            'password1': 'Str0ng!Pass',
            'password2': 'WrongPass',
            'org_name': 'Test Clinic',
            'org_type': 'clinic',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Organization.objects.filter(name='Test Clinic').exists())


class AcceptInviteTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Invite Org', slug='invite-org',
            org_type='clinic', status='active',
        )
        self.inviter = User.objects.create_user(
            username='inviter', email='inviter@test.com',
            password='pass1234!', role='org_user',
        )
        OrganizationMembership.objects.create(
            user=self.inviter, organization=self.org,
            role='hospital_owner', is_active=True,
        )
        self.invitee = User.objects.create_user(
            username='invitee', email='invitee@test.com',
            password='pass1234!', role='org_user',
        )

    def _make_invite(self, role='doctor'):
        import secrets
        from apps.accounts.models import OrganizationInvite
        raw = secrets.token_urlsafe(32)
        invite = OrganizationInvite.objects.create(
            organization=self.org,
            invited_by=self.inviter,
            email=self.invitee.email,
            role=role,
            token_hash=OrganizationInvite.make_token_hash(raw),
        )
        return invite, raw

    def test_accept_creates_membership(self):
        invite, raw = self._make_invite()
        self.client.force_login(self.invitee)
        self.client.post(reverse('organizations:accept_invite', kwargs={'token': raw}))
        self.assertTrue(OrganizationMembership.objects.filter(
            user=self.invitee, organization=self.org, role='doctor', is_active=True,
        ).exists())

    def test_accept_marks_invite_accepted(self):
        from apps.accounts.models import OrganizationInvite
        invite, raw = self._make_invite()
        self.client.force_login(self.invitee)
        self.client.post(reverse('organizations:accept_invite', kwargs={'token': raw}))
        invite.refresh_from_db()
        self.assertEqual(invite.status, 'accepted')

    def test_invalid_token_returns_404(self):
        self.client.force_login(self.invitee)
        response = self.client.get(
            reverse('organizations:accept_invite', kwargs={'token': 'bogustoken'})
        )
        self.assertEqual(response.status_code, 404)
