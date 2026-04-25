"""
URL patterns for MedConsult REST API v1.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views
from apps.knowledge_graph.views import KnowledgeGraphAPIView

urlpatterns = [
    # Authentication
    path('auth/token/', TokenObtainPairView.as_view(), name='api_token_obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),

    # Doctors
    path('doctors/', views.DoctorListAPIView.as_view(), name='api_doctors_list'),
    path('doctors/<int:doctor_id>/slots/', views.DoctorSlotsAPIView.as_view(), name='api_doctor_slots'),

    # Slots / Booking
    path('slots/<int:slot_id>/book/', views.book_appointment_api, name='api_book_appointment'),

    # Appointments
    path('appointments/', views.PatientAppointmentsAPIView.as_view(), name='api_appointments'),

    # Notifications
    path('notifications/', views.NotificationListAPIView.as_view(), name='api_notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read_api, name='api_notif_read'),

    # Knowledge Graph
    path('knowledge-graph/', KnowledgeGraphAPIView.as_view(), name='api_knowledge_graph'),
]
