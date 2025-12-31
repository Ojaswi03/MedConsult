from django.urls import path
from . import views

app_name = 'adminpanel'

urlpatterns = [
    path('verify/', views.doctor_verification_queue, name='verification_queue'),
    path('verify/<int:doctor_id>/approve/', views.verify_doctor, name='verify_doctor'),
    path('verify/<int:doctor_id>/reject/', views.reject_doctor, name='reject_doctor'),
    path('users/', views.users_overview, name='users'),
    path('appointments/', views.appointments_audit, name='appointments_audit'),
]
