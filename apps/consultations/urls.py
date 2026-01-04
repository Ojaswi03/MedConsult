from django.urls import path
from . import views

app_name = 'consultations'

urlpatterns = [
    path('join/<int:appointment_id>/', views.join_consultation, name='join'),
    path('waiting/<int:appointment_id>/', views.waiting_room, name='waiting_room'),
    path('end/<int:appointment_id>/', views.end_consultation_view, name='end'),
    path('status/<int:appointment_id>/', views.consultation_status, name='status'),
]
