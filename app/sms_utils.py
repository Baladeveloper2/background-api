import os
import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Config from environment
SMS_GATEWAY = os.getenv("SMS_GATEWAY", "MOCK") # MOCK, MSG91, TEXTLOCAL, etc.
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
DLT_PEID = os.getenv("JIO_DLT_PEID", "")
DLT_TEMPLATE_ID = os.getenv("JIO_DLT_TEMPLATE_ID", "")
SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "CHKLIN") # 6-character registered header

async def send_otp_sms(phone: str, otp: str) -> bool:
    """
    Sends an OTP SMS using Jio DLT compliant SMS gateway.
    Falls back to mock logging if gateway is not configured or set to MOCK.
    """
    message = f"Your OTP for login to Checkline is {otp}. Please do not share this with anyone."
    
    logger.info(f"Attempting to send OTP SMS to {phone}. Gateway: {SMS_GATEWAY}")
    
    if SMS_GATEWAY == "MOCK" or not SMS_API_KEY:
        # Write to log file for easy local debugging
        log_path = r"d:\project\backend\scratch\sent_otps.log"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] TO: {phone} | OTP: {otp} | MESSAGE: {message} (Jio DLT Template: {DLT_TEMPLATE_ID})\n")
        
        # Also print to stdout/stderr so it shows in fastAPI dev console
        print(f"\n🚀 [Jio DLT SMS OTP] Phone: {phone} | OTP: {otp} | Msg: {message}\n", flush=True)
        
        logger.info(f"🤖 [MOCK SMS] OTP {otp} logged to scratch/sent_otps.log for {phone}")
        return True
        
    try:
        # Clean phone number (get last 10 digits)
        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) >= 10:
            clean_phone = clean_phone[-10:]
        else:
            logger.error(f"Invalid phone number length: {phone}")
            return False
            
        if SMS_GATEWAY.upper() == "MSG91":
            # MSG91 DLT compliant API
            url = "https://control.msg91.com/api/v5/flow/"
            headers = {
                "authkey": SMS_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "template_id": DLT_TEMPLATE_ID,
                "sender": SMS_SENDER_ID,
                "mobiles": f"91{clean_phone}", # Indian country code prefix
                "otp": otp,
                "VAR1": otp # msg91 template variable mapping
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    resp_data = response.json()
                    if resp_data.get("type") == "success":
                        logger.info(f"SMS successfully dispatched via MSG91 to {phone}")
                        return True
                    else:
                        logger.error(f"MSG91 API error response: {resp_data}")
                else:
                    logger.error(f"MSG91 returned status code {response.status_code}: {response.text}")
                    
        elif SMS_GATEWAY.upper() == "TEXTLOCAL":
            # Textlocal DLT compliant API
            url = "https://api.textlocal.in/send/"
            params = {
                "apikey": SMS_API_KEY,
                "numbers": f"91{clean_phone}",
                "sender": SMS_SENDER_ID,
                "message": message,
                "custom": DLT_PEID,
                "dlt_template_id": DLT_TEMPLATE_ID
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=params)
                if response.status_code == 200:
                    resp_data = response.json()
                    if resp_data.get("status") == "success":
                        logger.info(f"SMS successfully dispatched via Textlocal to {phone}")
                        return True
                    else:
                        logger.error(f"Textlocal API error response: {resp_data}")
                else:
                    logger.error(f"Textlocal returned status code {response.status_code}")
                    
        else:
            logger.warning(f"Unsupported SMS gateway: {SMS_GATEWAY}. Falling back to logging.")
            
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone} due to exception: {str(e)}")
        
    return False
