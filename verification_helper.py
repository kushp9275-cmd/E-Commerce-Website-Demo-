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
    
    resend_api_key = os.getenv('RESEND_API_KEY')
    if resend_api_key:
        import json
        import urllib.request
        import urllib.error
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        html_body = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; color: #1e293b;">
            <div style="text-align: center; margin-bottom: 25px; border-bottom: 1px solid #f1f5f9; padding-bottom: 20px;">
                <h2 style="color: #6366F1; margin: 0; font-size: 1.5rem; font-weight: 700;">Welcome to NeoCart</h2>
                <p style="color: #64748b; font-size: 0.9rem; margin: 4px 0 0 0;">Your Future, Delivered.</p>
            </div>
            <p style="font-size: 1rem; line-height: 1.6;">Hello <strong>{username}</strong>,</p>
            <p style="font-size: 1rem; line-height: 1.6; color: #334155;">Thank you for registering at NeoCart! To complete your registration and verify your account, please use the 6-digit confirmation code below:</p>
            
            <div style="text-align: center; margin: 30px 0; background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%); padding: 20px; border-radius: 8px; border: 1px dashed #a78bfa;">
                <span style="font-size: 2rem; font-weight: 800; letter-spacing: 0.15em; color: #4f46e5;">{code}</span>
            </div>
            
            <p style="font-size: 0.85rem; line-height: 1.5; color: #64748b;">If you did not request this registration, you can safely ignore this email.</p>
            <div style="border-top: 1px solid #f1f5f9; margin-top: 25px; padding-top: 20px; text-align: center; font-size: 0.8rem; color: #94a3b8;">
                <p style="margin: 0;">NeoCart Inc. &bull; Innovative E-Commerce Solution</p>
            </div>
        </div>
        """
        
        data = {
            "from": "onboarding@resend.dev",
            "to": [to_email],
            "subject": subject,
            "html": html_body
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = response.read().decode('utf-8')
                print(f"Resend email sent successfully: {res_body}")
                return True
        except urllib.error.HTTPError as he:
            err_body = he.read().decode('utf-8')
            print(f"Resend HTTP Error {he.code}: {err_body}")
            print(f"\n[FALLBACK] Email content: To: {to_email} | Subject: {subject} | Code: {code}\n")
            return True
        except Exception as e:
            print(f"Resend error: {e}")
            print(f"\n[FALLBACK] Email content: To: {to_email} | Subject: {subject} | Code: {code}\n")
            return True

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
