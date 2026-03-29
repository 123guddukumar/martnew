"""
Meta WhatsApp Business Cloud API client.
Handles all outbound message sending: text, interactive buttons, etc.
Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """
    Thin wrapper around Meta WhatsApp Cloud API.
    All methods raise on HTTP errors so callers can handle gracefully.
    """

    def __init__(self):
        self.base_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict) -> dict:
        """Execute POST to WhatsApp API and return parsed JSON."""
        try:
            resp = requests.post(self.base_url, json=payload, headers=self.headers, timeout=10)
            resp.raise_for_status()
            logger.info(f"WhatsApp API success: {resp.json()}")
            return resp.json()
        except requests.HTTPError as e:
            logger.error(f"WhatsApp API HTTP error: {e.response.text}")
            raise
        except requests.RequestException as e:
            logger.error(f"WhatsApp API network error: {e}")
            raise

    def send_text(self, to: str, message: str) -> dict:
        """
        Send a plain text message.
        :param to: E.164 phone number, e.g. +919876543210
        :param message: Text body (supports *bold* and _italic_ markdown)
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message,
            },
        }
        return self._post(payload)

    def send_interactive_buttons(self, to: str, body: str, buttons: list[dict]) -> dict:
        """
        Send a message with up to 3 interactive reply buttons.
        :param buttons: List of {"id": "btn_id", "title": "Button Text"}
        """
        formatted_buttons = [
            {
                "type": "reply",
                "reply": {"id": btn["id"], "title": btn["title"]},
            }
            for btn in buttons[:3]  # Max 3 buttons per WhatsApp spec
        ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": formatted_buttons},
            },
        }
        return self._post(payload)

    def send_list_message(self, to: str, body: str, button_text: str, sections: list[dict]) -> dict:
        """
        Send a list/menu message (for showing order options menu).
        :param sections: [{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "action": {
                    "button": button_text,
                    "sections": sections,
                },
            },
        }
        return self._post(payload)

    def mark_as_read(self, message_id: str) -> dict:
        """Mark an incoming message as read (shows blue ticks)."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return self._post(payload)


# Singleton instance
whatsapp_client = WhatsAppClient()
