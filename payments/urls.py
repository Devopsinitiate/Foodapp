from django.urls import path, re_path
from . import views

urlpatterns = [
    path('initialize/<int:order_id>/', views.initialize_payment_view, name='initialize_payment'),
    path('verify/<str:reference>/', views.verify_payment_view, name='verify_payment'),
    # Webhook endpoint - support both with and without trailing slash
    path('webhook/', views.paystack_webhook, name='paystack_webhook'),
    re_path(r'^webhook$', views.paystack_webhook, name='paystack_webhook_no_slash'),
]