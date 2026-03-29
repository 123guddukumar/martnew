from django.urls import path
from .views import CreateOrderView, OrderDetailView, OrderStatusByPhoneView

urlpatterns = [
    path('create/', CreateOrderView.as_view(), name='order-create'),
    path('<int:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('status/', OrderStatusByPhoneView.as_view(), name='order-status'),
]
