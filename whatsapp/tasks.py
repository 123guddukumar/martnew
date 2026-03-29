"""
Celery async tasks for WhatsApp messaging.
Using Celery ensures webhook responses are fast (< 5s) as required by Meta.
"""
from celery import shared_task
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_summary_to_customer(self, order_id: int):
    """
    Send initial order summary + ask for name.
    Triggered immediately after order creation from frontend.
    Retries up to 3 times on failure.
    """
    try:
        from orders.models import Order
        from .client import whatsapp_client

        order = Order.objects.prefetch_related('items__product').get(id=order_id)

        summary = order.get_order_summary_text()
        message = (
            f"{summary}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"To complete your order, please reply with your *FULL NAME* 👇"
        )

        whatsapp_client.send_text(order.customer_phone, message)

        # Update order status
        order.status = 'awaiting_details'
        order.save(update_fields=['status'])

        logger.info(f"Order summary sent for Order #{order_id}")

    except Exception as exc:
        logger.error(f"Failed to send order summary for #{order_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_whatsapp_text_async(self, to: str, message: str):
    """Generic async text sender for non-critical notifications."""
    try:
        from .client import whatsapp_client
        whatsapp_client.send_text(to, message)
    except Exception as exc:
        logger.error(f"Async text failed to {to}: {exc}")
        raise self.retry(exc=exc)
