import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

logger = logging.getLogger(__name__)

# Enhanced Template for BGV Link Email with Branding
BGV_INVITATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8fafc;
            color: #1e293b;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background-color: #ffffff;
            padding: 0;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background-color: #1e293b;
            padding: 30px;
            text-align: center;
        }}
        .header img {{
            max-height: 50px;
            margin-bottom: 15px;
        }}
        .header h1 {{
            color: #ffffff;
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            padding: 40px;
            line-height: 1.6;
        }}
        .content p {{
            margin-bottom: 20px;
        }}
        .button-container {{
            text-align: center;
            margin: 35px 0;
        }}
        .button {{
            background-color: #2563eb;
            color: #ffffff !important;
            padding: 14px 30px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            display: inline-block;
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
        }}
        .footer {{
            background-color: #f1f5f9;
            padding: 30px;
            text-align: center;
            font-size: 13px;
            color: #64748b;
            border-top: 1px solid #e2e8f0;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        .link-text {{
            color: #2563eb;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            {logo_html}
            <h1>{site_name} Verification</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{candidate_name}</strong>,</p>
            <p>You have been invited to complete your background verification process for <strong>{site_name}</strong>.</p>
            <p>Please click the button below to securely submit your details and required documents.</p>
            
            <div class="button-container">
                <a href="{form_link}" class="button">Start Verification</a>
            </div>
            
            <p>If the button doesn't work, please copy and paste this link into your browser:</p>
            <p class="link-text">{form_link}</p>
            
            <p>Best regards,<br>The {site_name} Team</p>
        </div>
        <div class="footer">
            <p>&copy; {current_year} {site_name}. All rights reserved.</p>
            <p>Need help? Contact us at <a href="mailto:{support_email}">{support_email}</a></p>
            <p>This is an automated security message. Please do not reply.</p>
        </div>
    </div>
</body>
</html>
"""

def send_email_sync(to_email: str, subject: str, html_content: str):
    # Fetch configurations (Mirroring the logic provided by user)
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("EMAIL_USER") or os.getenv("SMTP_USER")
    smtp_password = os.getenv("EMAIL_PASSWORD") or os.getenv("SMTP_PASSWORD")
    from_name = os.getenv("SMTP_FROM_NAME") or os.getenv("SITE_NAME") or "BGVMS"
    
    if not smtp_user or not smtp_password:
        logger.error("SMTP credentials (EMAIL_USER/EMAIL_PASSWORD) are not configured.")
        return False
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{smtp_user}>"
        msg["To"] = to_email

        part = MIMEText(html_content, "html")
        msg.attach(part)

        # Implementation similar to Nodemailer config
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
        server.set_debuglevel(1) # Analogous to logger: true, debug: true
        
        # STARTTLS for Port 587
        if smtp_port == 587:
            server.starttls()
            
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()
        
        logger.info(f"✅ Email Service: Sent to {to_email} via {smtp_server}")
        return True
    except Exception as e:
        logger.error(f"❌ Email Service Error: {str(e)}")
        return False

async def send_bgv_invitation_email(to_email: str, candidate_name: str, form_link: str):
    """
    Sends the BGV form link to the candidate using the premium template.
    """
    import datetime
    site_name = os.getenv("SITE_NAME", "BGVMS")
    logo_url = os.getenv("LOGO_URL")
    support_email = os.getenv("SUPPORT_EMAIL", f"support@{site_name.lower().replace(' ', '')}.com")
    
    logo_html = f'<img src="{logo_url}" alt="{site_name} Logo">' if logo_url else ''
    
    html_content = BGV_INVITATION_TEMPLATE.format(
        candidate_name=candidate_name,
        form_link=form_link,
        site_name=site_name,
        logo_html=logo_html,
        support_email=support_email,
        current_year=datetime.datetime.now().year
    )
    
    subject = f"Action Required: {site_name} Background Verification"
    
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, send_email_sync, to_email, subject, html_content)
