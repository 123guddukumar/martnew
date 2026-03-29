"""
Order models: Order, OrderItem, UserState (chatbot flow tracking).
"""
from django.db import models
from products.models import Product


class Order(models.Model):
    """
    Represents a customer order. 
    Status progresses: pending → confirmed → delivered (or rejected).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('awaiting_details', 'Awaiting Customer Details'),
        ('awaiting_rider', 'Awaiting Rider Confirmation'),
        ('confirmed', 'Confirmed by Rider'),
        ('delivered', 'Delivered'),
        ('rejected', 'Rejected'),
    ]

    # Customer info (collected via WhatsApp chatbot)
    customer_phone = models.CharField(max_length=20, db_index=True)
    customer_name = models.CharField(max_length=255, blank=True)
    customer_address = models.TextField(blank=True)
    alternative_mobile = models.CharField(max_length=20, blank=True)

    # Order status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', db_index=True)

    # Financial
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer_phone', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.customer_phone} - {self.status}"

    def calculate_total(self):
        """Recalculate total from order items."""
        total = sum(item.subtotal for item in self.items.all())
        self.total_price = total
        self.save(update_fields=['total_price'])
        return total

    def get_order_summary_text(self):
        """Generate human-readable order summary for WhatsApp."""
        lines = ["🛒 *Order Summary*\n"]
        for item in self.items.select_related('product').all():
            lines.append(f"• {item.product.name} x{item.quantity} = ₹{item.subtotal}")
        lines.append(f"\n💰 *Total: ₹{self.total_price}*")
        return "\n".join(lines)


class OrderItem(models.Model):
    """Line item within an order."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # Snapshot at order time

    class Meta:
        unique_together = ['order', 'product']

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"


class UserState(models.Model):
    """
    Tracks chatbot conversation state per phone number.
    Used as a state machine to guide users through the order flow.
    """
    STEP_CHOICES = [
        ('idle', 'Idle'),
        ('awaiting_name', 'Awaiting Name'),
        ('awaiting_address', 'Awaiting Address'),
        ('awaiting_alt_mobile', 'Awaiting Alternative Mobile'),
        ('order_complete', 'Order Complete'),
    ]

    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    current_step = models.CharField(max_length=30, choices=STEP_CHOICES, default='idle')
    current_order = models.ForeignKey(
        Order, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='user_states'
    )
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} → {self.current_step}"

    class Meta:
        indexes = [
            models.Index(fields=['phone_number', 'current_step']),
        ]
