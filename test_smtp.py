import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Try to load local .env file if present
load_dotenv()

def test_smtp_configuration():
    print("=" * 70)
    print("NEOCART SMTP CONFIGURATION DIAGNOSTIC")
    print("=" * 70)
    
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = os.getenv('SMTP_PORT', '587')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASSWORD')
    
    print(f"SMTP_HOST:     {smtp_host if smtp_host else '[NOT SET]'}")
    print(f"SMTP_PORT:     {smtp_port} (Default is 587)")
    print(f"SMTP_USER:     {smtp_user if smtp_user else '[NOT SET]'}")
    print(f"SMTP_PASSWORD: {'*' * len(smtp_pass) if smtp_pass else '[NOT SET]'}")
    print("-" * 70)
    
    if not smtp_host or not smtp_user or not smtp_pass:
        print("ERROR: One or more required environment variables are missing.")
        print("Please ensure SMTP_HOST, SMTP_USER, and SMTP_PASSWORD are set.")
        print("Without these, the live application runs in SIMULATION MODE and only logs OTPs.")
        print("=" * 70)
        return False
        
    print("Attempting to connect to SMTP server...")
    try:
        port = int(smtp_port)
    except ValueError:
        print(f"ERROR: Invalid port number '{smtp_port}'. Must be an integer.")
        return False
        
    try:
        # Connect to server
        print(f"1. Connecting to {smtp_host}:{port}...")
        server = smtplib.SMTP(smtp_host, port, timeout=10)
        
        # Start TLS
        print("2. Sending STARTTLS...")
        server.starttls()
        
        # Login
        print(f"3. Logging in as {smtp_user}...")
        server.login(smtp_user, smtp_pass)
        
        # Compose test email
        print("4. Composing test email...")
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = smtp_user
        msg['Subject'] = "NeoCart SMTP Diagnostics - Test Email"
        body = "If you are reading this, your NeoCart SMTP email configuration is working perfectly!"
        msg.attach(MIMEText(body, 'plain'))
        
        # Send
        print(f"5. Sending test email to {smtp_user}...")
        server.sendmail(smtp_user, smtp_user, msg.as_string())
        server.close()
        
        print("-" * 70)
        print("SUCCESS! SMTP connection, authentication, and transmission succeeded.")
        print(f"A test email has been sent to {smtp_user}. Please check your inbox.")
        print("=" * 70)
        return True
        
    except smtplib.SMTPAuthenticationError as auth_err:
        print("-" * 70)
        print("ERROR: SMTP Authentication Failed!")
        print(f"Details: {auth_err}")
        print("\nCommon Causes:")
        print("1. If using Gmail (smtp.gmail.com): You must use an App Password, NOT your regular password.")
        print("   To generate one, go to: Google Account -> Security -> 2-Step Verification -> App Passwords.")
        print("2. Double-check that your SMTP_USER matches your username and contains the correct email address.")
        print("=" * 70)
        return False
    except Exception as e:
        print("-" * 70)
        print("ERROR: Failed to establish SMTP connection or send email.")
        print(f"Details: {type(e).__name__}: {e}")
        print("\nCommon Causes:")
        print("1. The mail server port or host is incorrect.")
        print("2. The host/network blocks outgoing connections on this port (e.g., Render blocking port 25).")
        print("=" * 70)
        return False

if __name__ == "__main__":
    test_smtp_configuration()
