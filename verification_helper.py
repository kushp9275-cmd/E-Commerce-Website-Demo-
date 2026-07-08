import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def generate_code():
    """Generates a random 6-digit verification code/OTP."""
    return str(random.randint(100000, 999999))

def send_confirmation_email(to_email, username, code):
    """Sends a registration confirmation email with the verification code."""
    subject = "NeoCart - Confirm Your Registration"
    body = f"""Hello {username},

Thank you for registering at NeoCart!

Your registration confirmation code is: {code}

Please enter this code on the verification screen to complete your registration.
If you did not request this, please ignore this email.

Best regards,
The NeoCart Team
Your Future, Delivered.
"""
    
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = os.getenv('SMTP_PORT', '587')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASSWORD')
    
    if not smtp_host or not smtp_user or not smtp_pass:
        print("\n" + "="*70)
        print(f"SMTP NOT CONFIGURED. [SIMULATED EMAIL] To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Code: {code}")
        print(f"Message Body:\n{body}")
        print("="*70 + "\n")
        return True
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Add timeout=10 to prevent Gunicorn worker timeout if Render blocks port 587
        server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.close()
        return True
    except Exception as e:
        print(f"SMTP ERROR: Failed to send email to {to_email}: {e}")
        print(f"\n[FALLBACK] Email content: To: {to_email} | Subject: {subject} | Code: {code}\n")
        # Return True to fall back to simulation mode so registration works on Render (code is logged to console)
        return True

def send_otp_sms(to_mobile, otp):
    """Sends an SMS containing the password reset OTP using Twilio."""
    message = f"Your NeoCart password reset OTP is {otp}. This code is valid for 10 minutes. Do not share it."
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_phone = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not account_sid or not auth_token or not from_phone:
        print("\n" + "="*70)
        print(f"TWILIO NOT CONFIGURED. [SIMULATED SMS] To: {to_mobile}")
        print(f"OTP Code: {otp}")
        print(f"Message: {message}")
        print("="*70 + "\n")
        return True
        
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_=from_phone,
            to=to_mobile
        )
        return True
    except Exception as e:
        print(f"TWILIO ERROR: Failed to send SMS to {to_mobile}: {e}")
        print(f"\n[FALLBACK] SMS content: To: {to_mobile} | OTP: {otp}\n")
        return False
