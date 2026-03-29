"""
WhatsApp Webhook Views.

GET  /api/whatsapp/webhook/  → Verification challenge (Meta setup)
POST /api/whatsapp/webhook/  → Incoming messages/events from Meta

Meta requires webhook responses within 5 seconds, so we process
asynchronously where possible.
"""
import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from .chatbot import chatbot

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    """
    Handles both webhook verification (GET) and incoming events (POST).
    """

    def get(self, request):
        """
        Meta webhook verification handshake.
        Meta sends hub.challenge and expects it echoed back.
        """
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            logger.info("WhatsApp webhook verified successfully")
            return HttpResponse(challenge, content_type='text/plain')

        logger.warning(f"Webhook verification failed. Token mismatch.")
        return HttpResponse('Forbidden', status=403)

    def post(self, request):
        """
        Process incoming WhatsApp events.
        Always return 200 quickly — Meta will retry if we don't respond fast.
        """
        try:
            body = json.loads(request.body)
            self._process_webhook(body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook body")
        except Exception as e:
            logger.error(f"Webhook processing error: {e}", exc_info=True)

        # Always return 200 to Meta to acknowledge receipt
        return JsonResponse({'status': 'ok'})

    def _process_webhook(self, body: dict):
        """Parse and route webhook payload."""
        # Navigate the nested Meta webhook structure
        entry_list = body.get('entry', [])
        for entry in entry_list:
            for change in entry.get('changes', []):
                value = change.get('value', {})

                # Process incoming messages
                for message in value.get('messages', []):
                    self._handle_message(message)

                # Process status updates (delivered, read receipts)
                for status_update in value.get('statuses', []):
                    self._handle_status_update(status_update)

    def _handle_message(self, message: dict):
        """Route message to chatbot based on message type."""
        msg_type = message.get('type')
        phone = message.get('from')  # E.164 format
        msg_id = message.get('id')

        if not phone:
            return

        logger.info(f"Incoming {msg_type} from {phone}")

        if msg_type == 'text':
            # Plain text message
            text = message.get('text', {}).get('body', '').strip()
            if text:
                chatbot.handle_message(phone, text, msg_id)

        elif msg_type == 'interactive':
            # Button or list reply
            interactive = message.get('interactive', {})
            interactive_type = interactive.get('type')

            if interactive_type == 'button_reply':
                button = interactive.get('button_reply', {})
                chatbot.handle_button_reply(
                    phone=phone,
                    button_id=button.get('id', ''),
                    button_title=button.get('title', ''),
                )

            elif interactive_type == 'list_reply':
                row = interactive.get('list_reply', {})
                chatbot.handle_button_reply(
                    phone=phone,
                    button_id=row.get('id', ''),
                    button_title=row.get('title', ''),
                )

        else:
            # Unsupported types (image, audio, etc.)
            from .client import whatsapp_client
            whatsapp_client.send_text(
                phone,
                "Sorry, I can only process text messages. Please type your response."
            )

    def _handle_status_update(self, status_update: dict):
        """Log delivery/read status updates (optional: update DB)."""
        status = status_update.get('status')
        msg_id = status_update.get('id')
        logger.debug(f"Message {msg_id} status: {status}")
