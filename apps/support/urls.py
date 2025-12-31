from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    path('help/', views.help_page, name='help'),
    path('contact/', views.contact_page, name='contact'),
    path('faq/', views.faq_page, name='faq'),
]
