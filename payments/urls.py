from django.urls import path
from .views import initiate_stk_push, mpesa_callback, WhitelistUser

urlpatterns = [
    path('initiate-stk-push/', initiate_stk_push, name='initiate-stk-push'),
    path('payment-callback/', mpesa_callback, name='mpesa-callback'),
    path('whitelist/', WhitelistUser.as_view(), name='whitelist-user'),
]
