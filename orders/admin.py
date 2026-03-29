from django.contrib import admin
from .models import Order, OrderItem, UserState


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['unit_price', 'subtotal']

    def subtotal(self, obj):
        return f"₹{obj.subtotal}"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer_phone', 'customer_name', 'status', 'total_price', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['customer_phone', 'customer_name']
    readonly_fields = ['created_at', 'updated_at', 'total_price']
    inlines = [OrderItemInline]


@admin.register(UserState)
class UserStateAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'current_step', 'current_order', 'last_activity']
    list_filter = ['current_step']
    search_fields = ['phone_number']
