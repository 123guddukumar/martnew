"""
Order API views.
- POST /api/orders/create/    → Create order from frontend cart
- GET  /api/orders/<id>/      → Get order details
- GET  /api/orders/status/?phone=... → Get latest order status by phone
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import Order, OrderItem, UserState
from .serializers import OrderCreateSerializer, OrderSerializer
from products.models import Product
from whatsapp.tasks import send_order_summary_to_customer
import logging

logger = logging.getLogger(__name__)


class CreateOrderView(APIView):
    """
    Creates order from React frontend cart and triggers WhatsApp chatbot.
    POST body: { phone: "+91...", items: [{product_id, quantity}] }
    """

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data['phone']
        items_data = serializer.validated_data['items']

        try:
            with transaction.atomic():
                # Create the order
                order = Order.objects.create(customer_phone=phone)

                # Build order items with current prices
                product_ids = [i['product_id'] for i in items_data]
                products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

                for item_data in items_data:
                    product = products[item_data['product_id']]
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item_data['quantity'],
                        unit_price=product.price,  # Snapshot current price
                    )

                # Calculate total
                order.calculate_total()

                # If the phone is 'PENDING', we wait for the user to message us from WhatsApp
                # to confirm the order. The chatbot will then update the phone number and state.
                if phone.upper() != 'PENDING':
                    # Initialize or update user chatbot state
                    user_state, _ = UserState.objects.get_or_create(phone_number=phone)
                    user_state.current_order = order
                    user_state.current_step = 'awaiting_name'
                    user_state.save()

                    # Trigger async WhatsApp message
                    send_order_summary_to_customer.delay(order.id)
                    logger.info(f"Order #{order.id} created for {phone}")
                else:
                    logger.info(f"Order #{order.id} created with PENDING phone (waiting for WhatsApp message)")
                return Response(
                    {'order_id': order.id, 'message': 'Order placed! Check WhatsApp for confirmation.'},
                    status=status.HTTP_201_CREATED
                )

        except Exception as e:
            logger.error(f"Order creation failed: {e}")
            return Response({'error': 'Order creation failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderDetailView(APIView):
    """GET /api/orders/<id>/ - Fetch single order details."""

    def get(self, request, order_id):
        try:
            order = Order.objects.prefetch_related('items__product').get(id=order_id)
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)


class OrderStatusByPhoneView(APIView):
    """GET /api/orders/status/?phone=+91... - Latest order status for a customer."""

    def get(self, request):
        phone = request.query_params.get('phone', '').strip()
        if not phone:
            return Response({'error': 'phone parameter required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.filter(customer_phone=phone).latest('created_at')
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response({'error': 'No orders found for this number'}, status=status.HTTP_404_NOT_FOUND)
