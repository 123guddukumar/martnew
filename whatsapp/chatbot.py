"""
WhatsApp Chatbot State Machine.

Handles the full conversation flow:
  idle → awaiting_name → awaiting_address → awaiting_alt_mobile → order_complete

Also handles the "menu" flow when user sends free text mid-session.
"""
import logging
import re
from django.conf import settings
from orders.models import Order, UserState
from .client import whatsapp_client

logger = logging.getLogger(__name__)


class ChatbotStateMachine:
    """
    Processes incoming WhatsApp messages and drives the order collection flow.
    Each method corresponds to a state transition.
    """

    def handle_message(self, phone: str, message_text: str, message_id: str = None):
        """
        Entry point. Route message based on current user state.
        :param phone: Sender's E.164 phone number
        :param message_text: Raw text from user
        :param message_id: WhatsApp message ID (for read receipts)
        """
        # Mark as read immediately for good UX
        if message_id:
            try:
                whatsapp_client.mark_as_read(message_id)
            except Exception:
                pass  # Non-critical

        # Get or create user state
        user_state, _ = UserState.objects.get_or_create(phone_number=phone)
        text = message_text.strip()

        logger.info(f"[{phone}] Step={user_state.current_step} | Message={text[:50]}")

        # Check for order confirmation from website (e.g. "Order #123")
        match = re.search(r'order\s*#?(\d+)', text, re.IGNORECASE)
        if match:
            order_id = int(match.group(1))
            if self._handle_initial_confirmation(phone, order_id):
                return

        # Route to correct handler based on current step
        if user_state.current_step == 'awaiting_name':
            self._handle_name(user_state, text)

        elif user_state.current_step == 'awaiting_address':
            self._handle_address(user_state, text)

        elif user_state.current_step == 'awaiting_alt_mobile':
            self._handle_alt_mobile(user_state, text)

        else:
            # idle or order_complete → show main menu
            self._show_menu(phone)

    def handle_button_reply(self, phone: str, button_id: str, button_title: str):
        """
        Handle interactive button clicks from rider or customer.
        button_id patterns:
          - rider_confirm_<order_id>
          - rider_reject_<order_id>
          - rider_delivered_<order_id>
          - menu_check_status
          - menu_order_again
        """
        logger.info(f"[{phone}] Button: {button_id}")

        if button_id.startswith('rider_confirm_'):
            order_id = int(button_id.replace('rider_confirm_', ''))
            self._rider_confirm(phone, order_id)

        elif button_id.startswith('rider_reject_'):
            order_id = int(button_id.replace('rider_reject_', ''))
            self._rider_reject(phone, order_id)

        elif button_id.startswith('rider_delivered_'):
            order_id = int(button_id.replace('rider_delivered_', ''))
            self._rider_delivered(phone, order_id)

        elif button_id == 'menu_check_status':
            self._check_status(phone)

        elif button_id == 'menu_order_again':
            self._order_again(phone)

        else:
            whatsapp_client.send_text(phone, "Sorry, I didn't understand that. Please try again.")

    # ─────────────────────────────────────────────────
    # State handlers
    # ─────────────────────────────────────────────────

    def _handle_initial_confirmation(self, phone: str, order_id: int) -> bool:
        """
        Handle the first message from a user who just clicked "Confirm order" on web.
        Updates the order with their real phone number and starts the collection flow.
        """
        try:
            order = Order.objects.get(id=order_id)
            
            # Update order with the sender's real phone
            order.customer_phone = phone
            order.save(update_fields=['customer_phone'])

            # Set user state
            user_state, _ = UserState.objects.get_or_create(phone_number=phone)
            user_state.current_order = order
            user_state.current_step = 'awaiting_name'
            user_state.save()

            # Greeting + ask for name
            summary = order.get_order_summary_text()
            msg = (
                f"👋 *Welcome to FreshMart!*\n\n"
                f"We received your request for:\n{summary}\n\n"
                "To complete your order, please reply with your *FULL NAME* 👇"
            )
            whatsapp_client.send_text(phone, msg)
            return True
            
        except Order.DoesNotExist:
            logger.warning(f"Order #{order_id} not found for phone {phone}")
            return False

    def _handle_name(self, user_state: UserState, text: str):
        """Step 1: Collect customer name."""
        if len(text) < 2:
            whatsapp_client.send_text(
                user_state.phone_number,
                "Please enter your full name (at least 2 characters)."
            )
            return

        # Save name to order
        order = user_state.current_order
        if not order:
            whatsapp_client.send_text(user_state.phone_number, "Session expired. Please order again from the website.")
            user_state.current_step = 'idle'
            user_state.save()
            return

        order.customer_name = text
        order.save(update_fields=['customer_name'])

        # Advance to address step
        user_state.current_step = 'awaiting_address'
        user_state.save()

        whatsapp_client.send_text(
            user_state.phone_number,
            f"Thanks, *{text}*! 🙏\n\nNow please enter your *delivery address*:"
        )

    def _handle_address(self, user_state: UserState, text: str):
        """Step 2: Collect delivery address."""
        if len(text) < 5:
            whatsapp_client.send_text(
                user_state.phone_number,
                "Please enter a complete delivery address."
            )
            return

        order = user_state.current_order
        order.customer_address = text
        order.save(update_fields=['customer_address'])

        user_state.current_step = 'awaiting_alt_mobile'
        user_state.save()

        whatsapp_client.send_text(
            user_state.phone_number,
            "Got it! 📍\n\nFinally, please share an *alternative mobile number* (or type SAME if same number):"
        )

    def _handle_alt_mobile(self, user_state: UserState, text: str):
        """Step 3: Collect alternative mobile, then send to rider."""
        order = user_state.current_order

        # Accept "SAME" as shorthand
        alt_mobile = user_state.phone_number if text.upper() == 'SAME' else text
        order.alternative_mobile = alt_mobile
        order.status = 'awaiting_rider'
        order.save(update_fields=['alternative_mobile', 'status'])

        user_state.current_step = 'order_complete'
        user_state.save()

        # Confirm to customer
        whatsapp_client.send_text(
            user_state.phone_number,
            "✅ *All details collected!*\n\nYour order is being sent to our rider. We'll update you shortly!"
        )

        # Notify rider with confirm/reject buttons
        self._notify_rider(order)

    def _show_menu(self, phone: str):
        """Show the main menu (check status / order again)."""
        whatsapp_client.send_interactive_buttons(
            to=phone,
            body="👋 Welcome! What would you like to do?",
            buttons=[
                {"id": "menu_check_status", "title": "📦 Check Status"},
                {"id": "menu_order_again", "title": "🛒 Order Again"},
            ]
        )

    def _check_status(self, phone: str):
        """Fetch latest order and report status."""
        try:
            order = Order.objects.filter(customer_phone=phone).latest('created_at')
            status_emojis = {
                'pending': '⏳',
                'awaiting_details': '📝',
                'awaiting_rider': '🚴',
                'confirmed': '✅',
                'delivered': '📦',
                'rejected': '❌',
            }
            emoji = status_emojis.get(order.status, '❓')
            msg = (
                f"📋 *Order #{order.id} Status*\n\n"
                f"{emoji} Status: *{order.get_status_display()}*\n"
                f"💰 Total: ₹{order.total_price}\n"
                f"🕐 Placed: {order.created_at.strftime('%d %b %Y, %I:%M %p')}"
            )
            whatsapp_client.send_text(phone, msg)
        except Order.DoesNotExist:
            whatsapp_client.send_text(phone, "No orders found. Visit our website to place your first order!")

    def _order_again(self, phone: str):
        """Send website link for reordering."""
        msg = (
            f"🛒 *Order Again*\n\n"
            f"Visit our store to place a new order:\n"
            f"{settings.WEBSITE_URL}\n\n"
            f"We look forward to serving you! 😊"
        )
        whatsapp_client.send_text(phone, msg)

    # ─────────────────────────────────────────────────
    # Rider notification and response handlers
    # ─────────────────────────────────────────────────

    def _notify_rider(self, order: Order):
        """Send order details to rider with Confirm/Reject buttons."""
        rider_phone = settings.RIDER_PHONE_NUMBER

        body = (
            f"🔔 *New Order #{order.id}*\n\n"
            f"{order.get_order_summary_text()}\n\n"
            f"👤 Name: {order.customer_name}\n"
            f"📍 Address: {order.customer_address}\n"
            f"📱 Mobile: {order.alternative_mobile}\n"
            f"📞 WhatsApp: {order.customer_phone}"
        )

        whatsapp_client.send_interactive_buttons(
            to=rider_phone,
            body=body,
            buttons=[
                {"id": f"rider_confirm_{order.id}", "title": "✅ Confirm"},
                {"id": f"rider_reject_{order.id}", "title": "❌ Reject"},
            ]
        )
        logger.info(f"Rider notified for Order #{order.id}")

    def _rider_confirm(self, rider_phone: str, order_id: int):
        """Rider confirmed order → update DB + notify customer + show Delivered button."""
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            whatsapp_client.send_text(rider_phone, f"Order #{order_id} not found.")
            return

        order.status = 'confirmed'
        order.save(update_fields=['status'])

        # Notify customer
        whatsapp_client.send_text(
            order.customer_phone,
            f"🎉 *Your order has been confirmed!*\n\n"
            f"Order #{order.id} is on its way. Our rider will deliver soon.\n"
            f"Total: ₹{order.total_price}"
        )

        # Show rider the "Delivered" button
        whatsapp_client.send_interactive_buttons(
            to=rider_phone,
            body=f"✅ Order #{order.id} confirmed. Mark as delivered when done.",
            buttons=[
                {"id": f"rider_delivered_{order.id}", "title": "📦 Delivered"},
            ]
        )
        logger.info(f"Order #{order_id} confirmed by rider")

    def _rider_reject(self, rider_phone: str, order_id: int):
        """Rider rejected order → update DB + notify customer."""
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            whatsapp_client.send_text(rider_phone, f"Order #{order_id} not found.")
            return

        order.status = 'rejected'
        order.save(update_fields=['status'])

        # Notify customer
        whatsapp_client.send_text(
            order.customer_phone,
            f"😔 *Your order has been rejected.*\n\n"
            f"We're sorry, Order #{order.id} could not be fulfilled at this time.\n"
            f"Please visit our store to try again or contact support."
        )

        whatsapp_client.send_text(rider_phone, f"❌ Order #{order_id} rejected. Customer has been notified.")
        logger.info(f"Order #{order_id} rejected by rider")

    def _rider_delivered(self, rider_phone: str, order_id: int):
        """Rider marked as delivered → update DB + notify customer."""
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            whatsapp_client.send_text(rider_phone, f"Order #{order_id} not found.")
            return

        order.status = 'delivered'
        order.save(update_fields=['status'])

        # Notify customer
        whatsapp_client.send_text(
            order.customer_phone,
            f"🎊 *Your order has been delivered!*\n\n"
            f"Order #{order.id} has been successfully delivered.\n"
            f"Thank you for ordering with us! 🙏\n\n"
            f"Rate your experience or order again: {settings.WEBSITE_URL}"
        )

        whatsapp_client.send_text(rider_phone, f"✅ Order #{order_id} marked as delivered. Great work!")
        logger.info(f"Order #{order_id} delivered")


# Singleton instance used across the app
chatbot = ChatbotStateMachine()
