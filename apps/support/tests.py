from django.test import TestCase, Client
from django.urls import reverse


class SupportViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_faq_page_loads(self):
        resp = self.client.get(reverse('support:faq'))
        assert resp.status_code == 200

    def test_contact_page_loads(self):
        resp = self.client.get(reverse('support:contact'))
        assert resp.status_code == 200
