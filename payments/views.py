import base64
import datetime
import requests

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings
from .models import Payment
from .mpesa_utils import get_mpesa_access_token, generate_password


@api_view(['POST'])
def initiate_stk_push(request):
    """
    Initiates an STK push to the customer's phone.
    Expects JSON: {
       "phone_number": "2547XXXXXXX",
       "amount": "10",
       "reference": "PaymentRef"
    }
    """
    phone_number = request.data.get('phone_number')
    amount = request.data.get('amount', 1)
    reference = request.data.get('reference', 'TestPayment')

    if not phone_number:
        return Response({"error": "phone_number is required"}, 
                        status=status.HTTP_400_BAD_REQUEST)

    # Create a Payment record in "Pending" status
    payment = Payment.objects.create(
        phone_number=phone_number,
        amount=amount,
        reference=reference
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
        "Amount": amount,
        "PartyA": phone_number,          # Phone number paying
        "PartyB": settings.MPESA_SHORTCODE,  # Business shortcode
        "PhoneNumber": phone_number,
        "CallBackURL": "https://5edb-105-163-158-143.ngrok-free.app/api/payment-callback/",  # update with your actual endpoint
        "AccountReference": reference,   # reference used for the transaction
        "TransactionDesc": "Payment via STK push"
    }
    response_data = requests.post(api_url, json=payload, headers=headers)
    response_json = response_data.json()

    # M-Pesa returns several fields, including CheckoutRequestID if success
    if response_data.status_code == 200 and "ResponseCode" in response_json and response_json["ResponseCode"] == "0":
        checkout_request_id = response_json.get("CheckoutRequestID")
        payment.checkout_request_id = checkout_request_id
        payment.save(update_fields=['checkout_request_id'])
        return Response({"message": "STK Push initiated", "CheckoutRequestID": checkout_request_id}, 
                        status=status.HTTP_200_OK)
    else:
        return Response({"error": response_json}, 
                        status=status.HTTP_400_BAD_REQUEST)


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
        
        return Response({"ResultDesc": result_desc, "ResultCode": result_code}, status=status.HTTP_200_OK)
    else:
        # Transaction failed
        payment.status = "Failed"
        payment.save()
        return Response({"ResultDesc": result_desc, "ResultCode": result_code}, status=status.HTTP_200_OK)
