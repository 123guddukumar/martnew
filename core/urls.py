"""
Main URL configuration for WhatsApp Ordering System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # API routes
    path('api/products/', include('products.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/whatsapp/', include('whatsapp.urls')),

    # Direct webhook alias (as requested by user configuration)
    path('webhook/', include('whatsapp.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
