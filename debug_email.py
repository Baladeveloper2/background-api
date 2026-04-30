import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load .env
load_dotenv()

def test_email():
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASSWORD")
    site_name = os.getenv("SITE_NAME", "BGVMS")
    
    print(f"--- Debugging Email Config ---")
    print(f"SMTP Server: {smtp_server}")
    print(f"SMTP Port: {smtp_port}")
    print(f"Email User: {email_user}")
    print(f"Email Pass Length: {len(email_pass) if email_pass else 0}")
    
    if not all([smtp_server, smtp_port, email_user, email_pass]):
        print("❌ ERROR: Missing environment variables!")
        return

    try:
        print("\nConnecting to server...")
        server = smtplib.SMTP(smtp_server, int(smtp_port), timeout=10)
        server.set_debuglevel(1)
        
        print("Starting TLS...")
        server.starttls()
        
        print(f"Logging in as {email_user}...")
        server.login(email_user, email_pass)
        
        print("Creating message...")
        msg = MIMEMultipart()
        msg["From"] = f"{site_name} <{email_user}>"
        msg["To"] = email_user # Send to self for test
        msg["Subject"] = "BGVMS Email Debug Test"
        msg.attach(MIMEText("This is a test email to verify your SMTP configuration works correctly.", "plain"))
        
        print("Sending test email to yourself...")
        server.sendmail(email_user, email_user, msg.as_string())
        
        server.quit()
        print("\n✅ SUCCESS! Email sent successfully.")
        
    except Exception as e:
        print(f"\n❌ FAILED to send email: {str(e)}")

if __name__ == "__main__":
    test_email()
