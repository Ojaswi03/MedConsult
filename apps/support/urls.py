from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    path('help/', views.help_page, name='help'),
    path('contact/', views.contact_page, name='contact'),
    path('faq/', views.faq_page, name='faq'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
]
