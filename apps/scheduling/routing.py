"""
WebSocket URL routing for scheduling app.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # Doctor calendar updates
    re_path(r'ws/doctor/(?P<doctor_id>\d+)/calendar/$', consumers.DoctorCalendarConsumer.as_asgi()),
    # Patient slot availability updates
    re_path(r'ws/patient/doctor/(?P<doctor_id>\d+)/slots/$', consumers.PatientSlotsConsumer.as_asgi()),
]
