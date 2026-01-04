from django.contrib import admin
from .models import Payment, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'amount', 'currency', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['patient__email', 'stripe_payment_intent_id', 'stripe_checkout_session_id']
    readonly_fields = ['stripe_payment_intent_id', 'stripe_checkout_session_id', 'created_at', 'updated_at']


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'payment', 'amount', 'reason', 'status', 'created_at']
    list_filter = ['status', 'reason', 'created_at']
    search_fields = ['stripe_refund_id', 'payment__stripe_payment_intent_id']
    readonly_fields = ['stripe_refund_id', 'created_at', 'processed_at']
