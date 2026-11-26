from django.contrib import admin
from .models import AvailabilityRequest, Notification

@admin.register(AvailabilityRequest)
class AvailabilityRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'pharmacy', 'medicine', 'quantity_requested', 'status',
                    'available_quantity', 'cancel_reason', 'created_at')
    list_filter = ('status', 'cancel_reason', 'pharmacy__city')
    search_fields = ('customer__username', 'pharmacy__pharmacy_name', 'medicine__medicine_name')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('user__username', 'message')
