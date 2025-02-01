import base64
import datetime
import requests

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings
from .models import Payment
from .mpesa_utils import get_mpesa_access_token, generate_password
from django.utils import timezone
from datetime import timedelta
from .routermanager import RouterManager
from internetplans.models import InternetPlan
from rest_framework.views import APIView
import threading
import routeros_api  # Make sure to install this package: pip install routeros-api
@api_view(['POST'])
def initiate_stk_push(request):
    """
    Initiates an STK push to the customer's phone.
    Expects JSON: {
        "phone_number": "2547XXXXXXX",
        "plan_id": 1,
        "reference": "PaymentRef"
    }
    """
    phone_number = request.data.get('phone_number')
    plan_id = request.data.get('plan_id')
    reference = request.data.get('reference', 'TestPayment')

    # Validate required fields
    if not phone_number:
        return Response(
            {"error": "phone_number is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not plan_id:
        return Response(
            {"error": "plan_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get the selected plan
    try:
        plan = InternetPlan.objects.get(id=plan_id, is_active=True)
    except InternetPlan.DoesNotExist:
        return Response(
            {"error": "Invalid or inactive plan selected"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create a Payment record in "Pending" status
    payment = Payment.objects.create(
        phone_number=phone_number,
        amount=plan.price,
        reference=reference,
        plan=plan  # Link the payment to the selected plan
    )

    access_token = get_mpesa_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    # Generate timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    # Generate base64 encoded password
    data_to_encode = settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp
    encoded_string = base64.b64encode(data_to_encode.encode()).decode('utf-8')

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": encoded_string,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",  # Or "CustomerBuyGoodsOnline"
        "Amount": int(plan.price),  # Convert decimal to integer for M-Pesa
        "PartyA": phone_number,  # Phone number paying
        "PartyB": settings.MPESA_SHORTCODE,  # Business shortcode
        "PhoneNumber": phone_number,
        "CallBackURL": "https://soko.ufundi.co.ke/api/payment-callback/",
        "AccountReference": reference,
        "TransactionDesc": f"Payment for {plan.name} plan"
    }

    response_data = requests.post(api_url, json=payload, headers=headers)
    response_json = response_data.json()

    if response_data.status_code == 200 and "ResponseCode" in response_json and response_json["ResponseCode"] == "0":
        checkout_request_id = response_json.get("CheckoutRequestID")
        payment.checkout_request_id = checkout_request_id
        payment.save(update_fields=['checkout_request_id'])
        
        return Response({
            "message": "STK Push initiated",
            "CheckoutRequestID": checkout_request_id,
            "plan": {
                "name": plan.name,
                "duration": plan.duration_hours,
                "price": str(plan.price)
            }
        }, status=status.HTTP_200_OK)
    else:
        return Response(
            {"error": response_json},
            status=status.HTTP_400_BAD_REQUEST
        )

# @api_view(['POST'])
# def initiate_stk_push(request):
#     """
#     Initiates an STK push to the customer's phone.
#     Expects JSON: {
#        "phone_number": "2547XXXXXXX",
#        "amount": "10",
#        "reference": "PaymentRef"
#     }
#     """
#     phone_number = request.data.get('phone_number')
#     amount = request.data.get('amount', 1)
#     reference = request.data.get('reference', 'TestPayment')

#     if not phone_number:
#         return Response({"error": "phone_number is required"}, 
#                         status=status.HTTP_400_BAD_REQUEST)

#     # Create a Payment record in "Pending" status
#     payment = Payment.objects.create(
#         phone_number=phone_number,
#         amount=amount,
#         reference=reference
#     )

#     access_token = get_mpesa_access_token()
#     api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
#     # Generate timestamp
#     timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

#     # Generate base64 encoded password
#     data_to_encode = settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp
#     encoded_string = base64.b64encode(data_to_encode.encode()).decode('utf-8')

#     headers = {
#         "Authorization": f"Bearer {access_token}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "BusinessShortCode": settings.MPESA_SHORTCODE,
#         "Password": encoded_string,
#         "Timestamp": timestamp,
#         "TransactionType": "CustomerPayBillOnline",  # Or "CustomerBuyGoodsOnline"
#         "Amount": amount,
#         "PartyA": phone_number,          # Phone number paying
#         "PartyB": settings.MPESA_SHORTCODE,  # Business shortcode
#         "PhoneNumber": phone_number,
#         "CallBackURL": "https://soko.ufundi.co.ke/api/payment-callback/",  # update with your actual endpoint
#         "AccountReference": reference,   # reference used for the transaction
#         "TransactionDesc": "Payment via STK push"
#     }
#     response_data = requests.post(api_url, json=payload, headers=headers)
#     response_json = response_data.json()

#     # M-Pesa returns several fields, including CheckoutRequestID if success
#     if response_data.status_code == 200 and "ResponseCode" in response_json and response_json["ResponseCode"] == "0":
#         checkout_request_id = response_json.get("CheckoutRequestID")
#         payment.checkout_request_id = checkout_request_id
#         payment.save(update_fields=['checkout_request_id'])
#         return Response({"message": "STK Push initiated", "CheckoutRequestID": checkout_request_id}, 
#                         status=status.HTTP_200_OK)
#     else:
#         return Response({"error": response_json}, 
#                         status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def mpesa_callback(request):
    """
    Handles the M-Pesa STK push callback.
    Safaricom will send transaction details in the request body.
    """
    data = request.data
    # The exact structure can vary, but typically we have:
    # data["Body"]["stkCallback"] -> contains resultCode, resultDesc, and CallbackMetadata (if success)
    
    stk_callback = data.get("Body", {}).get("stkCallback", {})
    checkout_request_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc")
    
    # Find the Payment object by checkout_request_id
    try:
        payment = Payment.objects.get(checkout_request_id=checkout_request_id)
    except Payment.DoesNotExist:
        return Response({"error": "Payment record not found"}, status=status.HTTP_404_NOT_FOUND)
    
    if result_code == 0:
        # Transaction is successful
        callback_metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        
        # Extract fields from CallbackMetadata
        mpesa_receipt_number = None
        transaction_date = None
        amount = None
        
        for item in callback_metadata:
            name = item.get("Name")
            if name == "MpesaReceiptNumber":
                mpesa_receipt_number = item.get("Value")
            elif name == "TransactionDate":
                # Convert YYYYMMDDHHmmss to datetime
                raw_date = str(item.get("Value"))
                transaction_date = datetime.datetime.strptime(raw_date, "%Y%m%d%H%M%S")
            elif name == "Amount":
                amount = item.get("Value")
            elif name == "PhoneNumber":
                # Could also cross-check phone number if you want
                pass
        
        payment.mpesa_receipt_number = mpesa_receipt_number
        payment.transaction_date = transaction_date
        payment.status = "Success"
        if amount:
            payment.amount = amount  # update with actual deducted amount
        payment.save()

         # Calculate session end time
        end_time = timezone.now() + timedelta(hours=payment.plan.duration_hours)
        router_manager = RouterManager(
            router_ip="192.168.1.1",  # Your router's IP
            username="admin",         # Your router's username
            password="password" 
        )

                # Add MAC to router whitelist
        if router_manager.add_mac_to_whitelist(payment.mac_address):
            # Schedule removal of MAC address
            
          delay = (end_time - timezone.now()).total_seconds()
          router_manager.remove_mac_from_whitelist(payment.mac_address, schedule=delay)


        return Response({"ResultDesc": result_desc, "ResultCode": result_code}, status=status.HTTP_200_OK)
    else:
        # Transaction failed
        payment.status = "Failed"
        payment.save()
        return Response({"ResultDesc": result_desc, "ResultCode": result_code}, status=status.HTTP_200_OK)

# ---------------------Testing Code ------------------------


# --- Helper Functions for Mikrotik API Interaction ---

def add_whitelist_rule(mikrotik_ip, username, password, mac, ip):
    """
    Connects to the Mikrotik router and adds a rule (for example, to an address list called 'whitelist')
    that permits the given IP address (with a comment containing the MAC) access.
    """
    connection = routeros_api.RouterOsApiPool(
        host=mikrotik_ip, 
        username=username, 
        password=password, 
        port=8728,            # Use the correct API port (default is 8728)
        plaintext_login=True  # Set to False if you use TLS
    )
    api = connection.get_api()
    try:
        resource = api.get_resource('/ip/firewall/address-list')
        # This example adds an entry to an address-list named "whitelist".
        resource.add(list="whitelist", address=ip, comment=mac)
    finally:
        connection.disconnect()


def remove_whitelist_rule(mikrotik_ip, username, password, mac, ip):
    """
    Connects to the Mikrotik router and removes the whitelist rule matching the given IP and MAC.
    """
    connection = routeros_api.RouterOsApiPool(
        host=mikrotik_ip, 
        username=username, 
        password=password, 
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()
    try:
        resource = api.get_resource('/ip/firewall/address-list')
        # Find rules matching our criteria
        rules = resource.get(filter={'list': 'whitelist', 'address': ip, 'comment': mac})
        for rule in rules:
            resource.remove(id=rule['.id'])
    finally:
        connection.disconnect()


# --- DRF View ---

class WhitelistUser(APIView):
    """
    API endpoint that, when called via POST with 'ip' and 'mac', will whitelist the user on the Mikrotik router.
    The rule is automatically removed after one minute.
    """
    def post(self, request):
        ip = request.data.get('ip')
        mac = request.data.get('mac')

        print(ip, "------IP-------")
        print(mac, "Mac--------------")
        if not ip or not mac:
            return Response(
                {'error': 'Both "ip" and "mac" are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mikrotik connection details.
        # In production, move these values into your Django settings and secure them appropriately.
        mikrotik_ip = "105.163.2.223"  # e.g., "203.0.113.1"
        mikrotik_username = "admin"              # Replace with your router's username
        mikrotik_password = "12345678"           # Replace with your router's password

        # Attempt to whitelist the user.
        try:
            add_whitelist_rule(mikrotik_ip, mikrotik_username, mikrotik_password, mac, ip)
        except Exception as e:
            return Response(
                {'error': f'Failed to add whitelist rule: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Define a function for delayed removal.
        def delayed_removal():
            try:
                remove_whitelist_rule(mikrotik_ip, mikrotik_username, mikrotik_password, mac, ip)
            except Exception as e:
                # In production, use proper logging.
                print("Error removing whitelist rule:", e)

        # Schedule removal of the whitelist rule in 60 seconds.
        timer = threading.Timer(60.0, delayed_removal)
        timer.start()

        return Response(
            {'status': 'User whitelisted for 1 minute'},
            status=status.HTTP_200_OK
        )
