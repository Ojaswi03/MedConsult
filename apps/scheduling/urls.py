from django.urls import path
from . import views

# This URLconf will be included with namespaces 'patient' and 'doctor' in config/urls.py
# Patient routes: /patient/* -> namespace='patient'
# Doctor routes: /doctor/* -> namespace='doctor'

urlpatterns = [
    # Patient URLs
    path('doctors/', views.patient_doctors_list, name='patient_doctors_list'),
    path('doctors/<int:doctor_id>/', views.patient_doctor_detail, name='doctor_detail'),
    path('book/<int:slot_id>/', views.patient_book_appointment, name='book_appointment'),
    path('appointments/', views.patient_appointments_list, name='patient_appointments'),
    path('appointments/<int:appointment_id>/cancel/', views.patient_cancel_appointment, name='cancel_appointment'),

    # Doctor URLs
    path('availability/', views.doctor_availability_view, name='doctor_availability'),
    path('schedule/', views.doctor_schedule_view, name='doctor_schedule'),
    path('generate-slots/', views.doctor_generate_slots, name='generate_slots'),
]
