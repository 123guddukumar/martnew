"""
Celery configuration for async WhatsApp message sending.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('whatsapp_ordering')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
