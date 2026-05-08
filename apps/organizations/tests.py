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


class StaffManagementTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Good Clinic', slug='good-clinic', org_type='clinic', status='active',
        )
        self.owner = User.objects.create_user(
            username='owner2', email='owner2@test.com', password='pass1234!', role='org_user',
        )
        OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner', is_active=True,
        )
        self.client.force_login(self.owner)

    def test_staff_list_accessible_to_hospital_owner(self):
        response = self.client.get(f'/org/good-clinic/staff/')
        self.assertEqual(response.status_code, 200)

    def test_send_invite_creates_invite_record(self):
        from apps.accounts.models import OrganizationInvite
        self.client.post(f'/org/good-clinic/staff/invite/', {
            'email': 'newstaff@clinic.com',
            'role': 'scheduler',
        })
        self.assertTrue(
            OrganizationInvite.objects.filter(
                organization=self.org, email='newstaff@clinic.com',
            ).exists()
        )

    def test_send_invite_role_restricted_by_grant_matrix(self):
        from apps.accounts.models import OrganizationInvite
        admin = User.objects.create_user(
            username='hadmin', email='hadmin@test.com', password='pass1234!', role='org_user',
        )
        OrganizationMembership.objects.create(
            user=admin, organization=self.org, role='hospital_admin', is_active=True,
        )
        self.client.force_login(admin)
        self.client.post(f'/org/good-clinic/staff/invite/', {
            'email': 'newowner@clinic.com',
            'role': 'hospital_owner',
        })
        self.assertFalse(OrganizationInvite.objects.filter(email='newowner@clinic.com').exists())

    def test_deactivate_member_removes_them_from_staff(self):
        staff = User.objects.create_user(
            username='staffx', email='staffx@test.com', password='pass1234!', role='org_user',
        )
        membership = OrganizationMembership.objects.create(
            user=staff, organization=self.org, role='scheduler', is_active=True,
        )
        self.client.post(f'/org/good-clinic/staff/{membership.id}/deactivate/')
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)


class OrgSettingsTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Settings Clinic', slug='settings-clinic', org_type='clinic', status='active',
        )
        self.owner = User.objects.create_user(
            username='owner_s', email='owner_s@test.com', password='pass1234!', role='org_user',
        )
        self.owner.is_email_verified = True
        self.owner.save()
        OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role='hospital_owner', is_active=True,
        )
        self.client.force_login(self.owner)

    def test_settings_page_loads(self):
        response = self.client.get('/org/settings-clinic/settings/')
        self.assertEqual(response.status_code, 200)

    def test_can_update_org_name(self):
        self.client.post('/org/settings-clinic/settings/', {
            'name': 'Settings Clinic Updated',
            'org_type': 'clinic',
            'address': '',
            'phone': '',
            'website': '',
        })
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, 'Settings Clinic Updated')

    def test_non_member_cannot_access_settings(self):
        outsider = User.objects.create_user(
            username='outsider_s', email='outsider_s@test.com', password='pass1234!', role='org_user',
        )
        self.client.force_login(outsider)
        response = self.client.get('/org/settings-clinic/settings/')
        self.assertEqual(response.status_code, 403)
