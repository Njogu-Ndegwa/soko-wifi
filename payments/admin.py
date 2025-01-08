from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'phone_number', 
        'amount', 
        'status', 
        'checkout_request_id', 
        'mpesa_receipt_number', 
        'transaction_date',
        'created_at',
        'updated_at'
    )
    list_filter = (
        'status', 
        'created_at', 
        'transaction_date'
    )
    search_fields = (
        'phone_number', 
        'mpesa_receipt_number', 
        'checkout_request_id'
    )
