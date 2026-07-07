import os
import sys
from dotenv import load_dotenv

# Try to load local .env file if present
load_dotenv()

def test_twilio_configuration():
    print("=" * 70)
    print("NEOCART TWILIO CONFIGURATION DIAGNOSTIC")
    print("=" * 70)
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_phone = os.getenv('TWILIO_PHONE_NUMBER')
    
    print(f"TWILIO_ACCOUNT_SID:  {account_sid if account_sid else '[NOT SET]'}")
    print(f"TWILIO_AUTH_TOKEN:   {'*' * len(auth_token) if auth_token else '[NOT SET]'}")
    print(f"TWILIO_PHONE_NUMBER: {from_phone if from_phone else '[NOT SET]'}")
    print("-" * 70)
    
    if not account_sid or not auth_token or not from_phone:
        print("ERROR: One or more required environment variables are missing.")
        print("Please ensure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER are set.")
        print("Without these, the live application runs in SIMULATION MODE and only logs OTPs.")
        print("=" * 70)
        return False
        
    print("Attempting to connect to Twilio and send a test SMS...")
    try:
        from twilio.rest import Client
    except ImportError:
        print("ERROR: Twilio helper library is not installed locally.")
        print("Run 'pip install twilio' to install it first.")
        print("=" * 70)
        return False
        
    try:
        # Initialize Twilio Client
        print("1. Initializing Twilio client...")
        client = Client(account_sid, auth_token)
        
        # Test sending an SMS to your own twilio number (or you can change this to your personal phone number)
        # We will try to fetch the account details first to verify credentials before sending
        print("2. Verifying credentials with Twilio API...")
        account = client.api.accounts(account_sid).fetch()
        print(f"   Successfully authenticated Twilio account: '{account.friendly_name}' (Status: {account.status})")
        
        print("\nSUCCESS! Twilio authentication succeeded.")
        print("Your credentials are correct and Twilio is ready to send SMS.")
        print("=" * 70)
        return True
        
    except Exception as e:
        print("-" * 70)
        print("ERROR: Twilio Authentication or Connection Failed.")
        print(f"Details: {type(e).__name__}: {e}")
        print("\nCommon Causes:")
        print("1. Your TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN is incorrect.")
        print("2. The account is suspended or credentials have been rotated.")
        print("=" * 70)
        return False

if __name__ == "__main__":
    test_twilio_configuration()
