from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Conversation list
    path('', views.conversation_list, name='conversations'),

    # Individual conversation
    path('<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),

    # Start conversation for appointment
    path('start/<int:appointment_id>/', views.start_conversation, name='start_conversation'),

    # Start direct (no appointment) conversation
    path('direct/doctor/<int:doctor_id>/', views.start_direct_message, name='start_direct_doctor'),
    path('direct/patient/<int:patient_id>/', views.start_direct_message, name='start_direct_patient'),

    # Delete (soft) conversation
    path('<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),

    # AJAX endpoints
    path('<int:conversation_id>/send/', views.send_message_view, name='send_message'),
    path('<int:conversation_id>/messages/', views.get_messages, name='get_messages'),
    path('unread-count/', views.unread_count, name='unread_count'),
]
