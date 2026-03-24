"""
MedConsult URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # Authentication
    path('auth/', include('apps.accounts.urls')),

    # Dashboard (role-based home)
    path('app/', include('apps.dashboard.urls')),

    # Scheduling (patient and doctor)
    path('patient/', include(('apps.scheduling.urls', 'scheduling'), namespace='patient')),
    path('doctor/', include(('apps.scheduling.urls', 'scheduling'), namespace='doctor')),

    # Admin panel
    path('internal/', include('apps.adminpanel.urls')),

    # Support
    path('support/', include('apps.support.urls')),

    # Payments
    path('payments/', include('apps.payments.urls')),

    # Messaging
    path('messages/', include('apps.messaging.urls')),

    # Video Consultations
    path('consultation/', include('apps.consultations.urls')),

    # REST API v1
    path('api/v1/', include('apps.api.urls')),

    # Landing page
    path('', include('apps.accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
