from django.urls import path
from . import views

app_name = 'adminpanel'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('charts/', views.dashboard_charts_data, name='dashboard_charts'),

    # Users
    path('users/', views.users_list, name='users_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/export/', views.users_export, name='users_export'),

    # Doctors
    path('doctors/', views.doctors_list, name='doctors_list'),
    path('doctors/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'),
    path('doctors/<int:doctor_id>/document/<str:doc_type>/', views.doctor_document_view, name='doctor_document'),

    # Verification
    path('verify/', views.doctor_verification_queue, name='verification_queue'),
    path('verify/<int:doctor_id>/approve/', views.verify_doctor, name='verify_doctor'),
    path('verify/<int:doctor_id>/reject/', views.reject_doctor, name='reject_doctor'),

    # Appointments
    path('appointments/', views.appointments_list, name='appointments_list'),
    path('appointments/export/', views.appointments_export, name='appointments_export'),

    # Financial
    path('financial/', views.financial_overview, name='financial_overview'),

    # Audit
    path('audit/', views.audit_logs, name='audit_logs'),
]
