from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class OrgReviewTest(TestCase):
    def setUp(self):
        self.platform_owner = User.objects.create_user(
            username='po', email='po@test.com',
            password='pass1234!', role='platform_owner',
        )
        from apps.accounts.models import Organization
        self.org = Organization.objects.create(
            name='Test Hospital', slug='test-hospital-review',
            org_type='hospital', status='pending',
        )

    def test_org_list_requires_login(self):
        response = self.client.get('/internal/organizations/')
        self.assertEqual(response.status_code, 302)

    def test_org_list_visible_to_platform_owner(self):
        self.client.force_login(self.platform_owner)
        response = self.client.get('/internal/organizations/')
        self.assertEqual(response.status_code, 200)

    def test_approve_org_sets_status_active(self):
        self.client.force_login(self.platform_owner)
        self.client.post(f'/internal/organizations/{self.org.id}/approve/')
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'active')

    def test_reject_org_stores_reason(self):
        self.client.force_login(self.platform_owner)
        self.client.post(f'/internal/organizations/{self.org.id}/reject/', {'reason': 'Incomplete docs'})
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'rejected')
        self.assertIn('Incomplete docs', self.org.rejected_reason)

    def test_suspend_org(self):
        self.org.status = 'active'
        self.org.save()
        self.client.force_login(self.platform_owner)
        self.client.post(f'/internal/organizations/{self.org.id}/suspend/')
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'suspended')

    def test_non_platform_user_forbidden_from_org_list(self):
        patient = User.objects.create_user(
            username='patsec', email='patsec@test.com',
            password='pass1234!', role='patient',
        )
        self.client.force_login(patient)
        response = self.client.get('/internal/organizations/')
        self.assertEqual(response.status_code, 403)
