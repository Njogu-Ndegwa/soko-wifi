import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
from django.core.cache import cache
import datetime
import base64
from django.conf import settings
def get_mpesa_access_token():
    """
    Returns a valid access token from Safaricom Daraja.
    Caches it for 1 hour to avoid re-generating unnecessarily.
    """
    token = cache.get('mpesa_access_token')
    if token:
        return token
    
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET

    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    if r.status_code == 200:
        token = r.json().get('access_token')
        # Cache it for 3500 seconds (slightly less than 3600 to be safe)
        cache.set('mpesa_access_token', token, timeout=3500)
        return token
    else:
        # handle error
        raise Exception("Failed to generate M-Pesa access token")
    

def generate_password(short_code, pass_key):
    """
    Generate the M-Pesa password by concatenating ShortCode + PassKey + Timestamp,
    then base64-encoding the result.

    Returns:
        (password, timestamp) as a tuple
    """
    # 1) Generate current timestamp in 'YYYYMMDDHHmmss' format
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    # 2) Concatenate ShortCode + PassKey + Timestamp
    data_to_encode = short_code + pass_key + timestamp

    # 3) Base64 encode the data_to_encode
    encoded_string = base64.b64encode(data_to_encode.encode()).decode('utf-8')

    return encoded_string, timestamp

# Usage example:
short_code = settings.MPESA_SHORTCODE
pass_key = settings.MPESA_PASSKEY
password, current_timestamp = generate_password(short_code, pass_key)

print("Password:", password)
print("Timestamp:", current_timestamp)

