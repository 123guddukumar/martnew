from rest_framework import serializers
from .models import Order, OrderItem
from products.models import Product


class OrderItemInputSerializer(serializers.Serializer):
    """Used when creating an order from the React frontend."""
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    """
    Validates order creation request from frontend.
    Expects: { phone: "+91...", items: [{product_id, quantity}, ...] }
    """
    phone = serializers.CharField(max_length=20)
    items = OrderItemInputSerializer(many=True, min_length=1)

    def validate_phone(self, value):
        # Normalize phone: strip spaces, ensure starts with +
        value = value.strip().replace(' ', '')
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone must include country code, e.g. +919876543210")
        return value

    def validate_items(self, items):
        product_ids = [i['product_id'] for i in items]
        existing = Product.objects.filter(id__in=product_ids, is_available=True)
        if existing.count() != len(set(product_ids)):
            raise serializers.ValidationError("One or more products are unavailable.")
        return items


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer_phone', 'customer_name', 'customer_address',
            'alternative_mobile', 'status', 'status_display',
            'total_price', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'total_price', 'created_at', 'updated_at']
