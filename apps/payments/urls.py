from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Checkout flow
    path('checkout/<int:appointment_id>/', views.checkout, name='checkout'),
    path('success/<int:appointment_id>/', views.payment_success, name='success'),
    path('cancel/<int:appointment_id>/', views.payment_cancel, name='cancel'),

    # Webhook
    path('webhook/', views.stripe_webhook, name='webhook'),

    # History
    path('history/', views.payment_history, name='history'),
]
