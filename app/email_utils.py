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
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 0; }}
        .container { max-width: 600px; margin: 40px auto; background-color: #ffffff; padding: 0; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
        .header { padding: 30px 40px 10px 40px; text-align: left; }
        .header img { max-height: 45px; }
        .content { padding: 10px 40px 40px 40px; line-height: 1.8; font-size: 16px; color: #374151; }
        .content p { margin: 0 0 18px 0; line-height: 1.8; }
        .content ul {{ margin: 16px 0 16px 28px; list-style-type: disc; }}
        .content ol {{ margin: 16px 0 16px 28px; list-style-type: decimal; }}
        .content h1 {{ font-size: 24px; font-weight: 800; margin: 24px 0 16px 0; }}
        .content h2 {{ font-size: 20px; font-weight: 700; margin: 24px 0 16px 0; }}
        .content h3 {{ font-size: 18px; font-weight: 700; margin: 24px 0 16px 0; }}
        .content a {{ color: #2563eb; text-decoration: underline; }}
        .content blockquote {{ border-left: 3px solid #e2e8f0; padding-left: 12px; color: #64748b; margin: 16px 0; }}
        .checks-box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin: 25px 0; }}
        .checks-box h4 {{ margin: 0 0 15px 0; font-size: 14px; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; }}
        .checks-list { list-style-type: none; padding: 0; margin: 0; }
        .checks-list li { display: flex; align-items: center; margin-bottom: 12px; color: #1e293b; font-weight: 500; }
        .checks-list li:last-child { margin-bottom: 0; }
        .checks-list li span.check-icon { background: #dcfce7; color: #166534; width: 22px; height: 22px; min-width: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 12px; font-weight: bold; line-height: 1; }
        .button-container {{ text-align: center; margin: 35px 0; }}
        .button {{ background-color: #2563eb; color: #ffffff !important; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2); }}
        .fallback-text {{ font-size: 13px; color: #64748b; text-align: center; margin-bottom: 5px; }}
        .footer {{ background-color: #f1f5f9; padding: 30px; text-align: center; font-size: 13px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        .footer p {{ margin: 5px 0; }}
        .link-text {{ color: #2563eb; word-break: break-all; font-size: 12px; text-align: center; background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px dashed #cbd5e1; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            {logo_html}
        </div>
        <div class="content">
            {custom_email_body}
            
            <div class="button-container">
                <a href="{form_link}" class="button">Complete Verification</a>
            </div>
            
            <p class="fallback-text">If the button doesn't work, please copy and paste this link into your browser:</p>
            <div class="link-text">{form_link}</div>
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

# Template for Insufficiency Notification
INSUFFICIENCY_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; padding: 0; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
        .header {{ background-color: #ef4444; padding: 30px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 40px; line-height: 1.6; }}
        .content p {{ margin-bottom: 20px; }}
        .message-box {{ background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .details {{ font-size: 14px; color: #64748b; margin-bottom: 20px; }}
        .button-container {{ text-align: center; margin: 35px 0; }}
        .button {{ background-color: #ef4444; color: #ffffff !important; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; }}
        .footer {{ background-color: #f1f5f9; padding: 30px; text-align: center; font-size: 13px; color: #64748b; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Action Required: Insufficiency Reported</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{candidate_name}</strong>,</p>
            <p>During our verification process for your application (Case: {case_ref}), an insufficiency was noted for the following check:</p>
            <div class="details">
                <strong>Check Type:</strong> {check_name}<br>
                <strong>Reference ID:</strong> {case_ref}
            </div>
            <p><strong>Message from our verification team:</strong></p>
            <div class="message-box">
                {custom_message}
            </div>
            <p>Please click the button below to securely upload the requested documents or provide further information.</p>
            <div class="button-container">
                <a href="{upload_link}" class="button">Upload Documents</a>
            </div>
            <p>Best regards,<br>The {site_name} Team</p>
        </div>
        <div class="footer">
            <p>&copy; {current_year} {site_name}. All rights reserved.</p>
            <p>Need help? Contact us at {support_email}</p>
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

async def send_insufficiency_email(to_email: str, candidate_name: str, case_ref: str, check_name: str, custom_message: str, upload_link: str):
    """
    Sends an insufficiency notification email to the candidate.
    """
    import datetime
    site_name = os.getenv("SITE_NAME", "BGVMS")
    support_email = os.getenv("SUPPORT_EMAIL", f"support@{site_name.lower().replace(' ', '')}.com")
    
    html_content = INSUFFICIENCY_EMAIL_TEMPLATE.format(
        candidate_name=candidate_name,
        case_ref=case_ref,
        check_name=check_name,
        custom_message=custom_message,
        upload_link=upload_link,
        site_name=site_name,
        support_email=support_email,
        current_year=datetime.datetime.now().year
    )
    
    subject = f"Urgent: Action Required for your {site_name} Verification"
    
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, send_email_sync, to_email, subject, html_content)

async def send_bgv_invitation_email(to_email: str, candidate_name: str, form_link: str, checks: list = None, custom_subject: str = None, custom_body: str = None, case_ref: str = None, client_name: str = None):
    """
    Sends the BGV form link to the candidate using the premium template, supporting dynamic rich text and selected checks.
    """
    import datetime
    site_name = os.getenv("SITE_NAME", "BGVMS")
    logo_url = os.getenv("LOGO_URL", "https://checklinetech.com/wp-content/uploads/2023/12/logo-checkline.png") # Fallback to Checkline logo
    support_email = os.getenv("SUPPORT_EMAIL", f"support@{site_name.lower().replace(' ', '')}.com")
    support_phone = os.getenv("SUPPORT_PHONE", "+91 99999 99999")
    
    logo_html = f'<img src="{logo_url}" alt="{site_name} Logo">' if logo_url else ''
    current_year = datetime.datetime.now().year
    
    # Generate Checks HTML dynamically (Removed as per requirements)
    checks_html = ""

    # Parse body
    if not custom_body:
        custom_body = f"<p>Dear <strong>{{candidate_name}}</strong>,</p><p>You have been invited to complete your background verification process for <strong>{{site_name}}</strong>.</p><p>Please click the button below to securely submit your details and required documents.</p>"

    # Replace variables in body
    body_rendered = custom_body
    body_rendered = body_rendered.replace('{{candidate_name}}', candidate_name)
    body_rendered = body_rendered.replace('{{case_reference}}', case_ref or '')
    body_rendered = body_rendered.replace('{{verification_link}}', form_link)
    body_rendered = body_rendered.replace('{{company_name}}', site_name)
    body_rendered = body_rendered.replace('{{client_name}}', client_name or site_name)
    body_rendered = body_rendered.replace('{{support_email}}', support_email)
    body_rendered = body_rendered.replace('{{support_phone}}', support_phone)
    body_rendered = body_rendered.replace('{{site_name}}', site_name)

    html_content = BGV_INVITATION_TEMPLATE.format(
        logo_html=logo_html,
        site_name=site_name,
        custom_email_body=body_rendered,
        form_link=form_link,
        support_email=support_email,
        current_year=current_year
    )
    
    subject = custom_subject if custom_subject else f"Background Verification Invitation - {site_name}"
    
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, send_email_sync, to_email, subject, html_content)


DIGITAL_ADDRESS_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; padding: 0; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
        .header {{ background-color: #7c3aed; padding: 30px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 40px; line-height: 1.6; }}
        .content p {{ margin-bottom: 20px; }}
        .button-container {{ text-align: center; margin: 35px 0; }}
        .button {{ background-color: #7c3aed; color: #ffffff !important; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; box-shadow: 0 4px 6px -1px rgba(124, 58, 237, 0.2); }}
        .footer {{ background-color: #f1f5f9; padding: 30px; text-align: center; font-size: 13px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        .link-text {{ color: #7c3aed; word-break: break-all; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Digital Address Verification</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{candidate_name}</strong>,</p>
            <p>A digital address verification has been initiated for your application.</p>
            <p>This process requires a live location check and a geotagged camera capture using your smartphone/device. Please ensure you are physically present at the registered residence address to complete this verification.</p>
            <div class="button-container">
                <a href="{verification_link}" class="button">Start Address Verification</a>
            </div>
            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <p class="link-text">{verification_link}</p>
            <p>Best regards,<br>The Verification Team</p>
        </div>
        <div class="footer">
            <p>This verification link is secure and will expire in 24 hours.</p>
        </div>
    </div>
</body>
</html>
"""

async def send_digital_address_verification_email(to_email: str, candidate_name: str, verification_link: str):
    """
    Sends the digital address verification link to the candidate.
    """
    site_name = os.getenv("SITE_NAME", "BGVMS")
    html_content = DIGITAL_ADDRESS_EMAIL_TEMPLATE.format(
        candidate_name=candidate_name,
        verification_link=verification_link
    )
    subject = f"Action Required: Digital Address Verification for {site_name}"
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, send_email_sync, to_email, subject, html_content)


# Template for Submission Notification
SUBMISSION_NOTIFICATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; padding: 0; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
        .header {{ background-color: #2563eb; padding: 30px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 40px; line-height: 1.6; }}
        .content p {{ margin-bottom: 20px; }}
        .details-box {{ background-color: #f1f5f9; padding: 20px; border-radius: 8px; margin: 20px 0; border-top: 4px solid #2563eb; }}
        .details-row {{ margin-bottom: 10px; font-size: 14px; }}
        .details-row strong {{ color: #1e293b; width: 120px; display: inline-block; }}
        .footer {{ background-color: #f1f5f9; padding: 30px; text-align: center; font-size: 13px; color: #64748b; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Documents Submitted</h1>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p>This is to notify you that a candidate has successfully submitted their verification documents via the BGV portal.</p>
            
            <div class="details-box">
                <div class="details-row"><strong>Candidate:</strong> {candidate_name}</div>
                <div class="details-row"><strong>Case Ref:</strong> {case_ref}</div>
                <div class="details-row"><strong>Status:</strong> Documents Submitted</div>
                <div class="details-row"><strong>Date:</strong> {submission_date}</div>
            </div>
            
            <p>We will start the Verification Process Soon</p>
        </div>
        <div class="footer">
            <p>&copy; {current_year} {site_name}. All rights reserved.</p>
            <p>This is an automated system notification.</p>
        </div>
    </div>
</body>
</html>
"""

async def send_submission_notification_email(to_email: str, candidate_name: str, case_ref: str):
    """
    Sends a notification email to the stakeholder (Admin/Customer) when a candidate submits documents.
    """
    import datetime
    site_name = os.getenv("SITE_NAME", "BGVMS")
    
    html_content = SUBMISSION_NOTIFICATION_TEMPLATE.format(
        candidate_name=candidate_name,
        case_ref=case_ref,
        submission_date=datetime.datetime.now().strftime("%d-%m-%Y %H:%M"),
        site_name=site_name,
        current_year=datetime.datetime.now().year
    )
    
    subject = f"Notification: Documents Submitted - {candidate_name} ({case_ref})"
    
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, send_email_sync, to_email, subject, html_content)

async def send_custom_email(to_email: str, subject: str, html_content: str):
    """
    Sends a custom email with pre-rendered HTML content.
    """
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, send_email_sync, to_email, subject, html_content)

async def send_custom_sms(phone: str, message: str):
    """
    Mock sending SMS. In production, integrate with Twilio or equivalent SMS provider.
    """
    logger.info(f"Mock sending SMS to {phone}: {message}")
    # Return true for now
    return True
