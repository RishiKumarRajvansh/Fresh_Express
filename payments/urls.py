from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('methods/', views.payment_methods, name='payment_methods'),
    path('add/', views.add_payment_method, name='add_payment_method'),
    path('delete/<int:method_id>/', views.delete_payment_method, name='delete_payment_method'),
    path('set-default/<int:method_id>/', views.set_default_payment_method, name='set_default_payment_method'),
    path('checkout-options/', views.payment_options_checkout, name='checkout_options'),
    path('razorpay/callback/', views.razorpay_callback, name='razorpay_callback'),
    path('upi/qr/', views.upi_qr_payment, name='upi_qr_payment'),
]
