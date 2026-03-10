"""Payments app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PriceViewSet, PaymentViewSet, InvoiceViewSet

router = DefaultRouter()
router.register(r"prices", PriceViewSet, basename="price")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("", include(router.urls)),
]
