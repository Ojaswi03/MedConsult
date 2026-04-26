"""
MedConsult URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from two_factor.urls import urlpatterns as tf_urlpatterns
from apps.accounts.views import landing_page

urlpatterns = [
    # Landing page
    path('', landing_page, name='landing'),

    # Django admin
    path('admin/', admin.site.urls),

    # Two-factor authentication (library routes live under /account/)
    path('', include(tf_urlpatterns)),

    # Authentication (login, signup, profile, settings, password reset)
    path('auth/', include('apps.accounts.urls')),

    # Dashboard (role-based home)
    path('app/', include('apps.dashboard.urls')),

    # Scheduling - patient flows (/patient/...)
    path('patient/', include(('apps.scheduling.patient_urls', 'scheduling'), namespace='patient')),

    # Scheduling - doctor flows (/doctor/...)
    path('doctor/', include(('apps.scheduling.doctor_urls', 'scheduling'), namespace='doctor')),

    # Admin panel
    path('internal/', include('apps.adminpanel.urls')),

    # Support
    path('support/', include('apps.support.urls')),

    # Payments
    path('payments/', include('apps.payments.urls')),

    # Messaging
    path('messages/', include('apps.messaging.urls')),

    # Video consultations
    path('consultation/', include('apps.consultations.urls')),

    # Knowledge graph (UI under /internal/, API under /api/v1/)
    path('internal/knowledge-graph/', include('apps.knowledge_graph.urls')),

    # REST API v1
    path('api/v1/', include('apps.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
