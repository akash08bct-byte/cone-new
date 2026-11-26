import smtplib
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from classes.database import fetch_one
import json
from classes.logging import error_log

def get_email_details():
    row = fetch_one("""
        SELECT sender_mail, sender_pwd, recipient_mail, subject, body
        FROM email_details
        LIMIT 1
    """)

    if not row:
        print("❌ No email details found in database")
        return None

    sender_mail, sender_pwd, recipient_mail, subject, body = row

    try:
        recipient_list = json.loads(recipient_mail) if recipient_mail else []
    except Exception as e:
        error_log("Error",e)
        recipient_list = []

    if isinstance(recipient_list, str):
        recipient_list = [recipient_list]

    return {
        "sender_mail": sender_mail,
        "sender_pwd": sender_pwd,
        "recipient_mail": recipient_list,
        "subject": subject,
        "body": body
    }

def send_email_with_attachments(attachments_path, retries=3, wait_seconds=5):
    try:
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        email_config = get_email_details()
        # print(email_config)
        if not email_config:
            print("❌ Email configuration not available")
            return False
        SENDER_EMAIL = email_config.get("sender_mail", '')
        SENDER_PASSWORD = email_config.get("sender_pwd", '')
        RECIPIENT_EMAILS = email_config.get("recipient_mail", '')

        subject = email_config.get('subject', 'Lycra Defect Report')
        body = email_config.get("body", '')

        if not SENDER_EMAIL or not SENDER_PASSWORD or not RECIPIENT_EMAILS:
            print("❌ Missing email sender/password/recipients")
            return False
        
        # SENDER_EMAIL = "dharanidaraerp@gmail.com"
        # SENDER_PASSWORD = "cnym ngvm voiy tqes"
        # RECIPIENT_EMAILS = [
        #     "threadi@texainnovates.com"
        #     # "dsmerp@yahoo.com",
        #     # "dsm_production2019@yahoo.com",
        #     "dharanidaramills@yahoo.in",
        #     # "info@texainnovates.com"
        # ]
        
        # subject = "Lycra Defect Report & Bad Images Report"
        # body = "Dear Team,\n\nPlease find attached the defect report and bad images report for review.\n\nBest Regards,\nTEXA INNOVATES Automated System"
        
        # attachments = ["Lycra_Defect_Report.pdf", "bad_images_report.pdf"]
    
        attachments = [attachments_path]
        

        for attempt in range(retries):
            try:
                msg = MIMEMultipart()
                msg['From'] = SENDER_EMAIL
                msg['To'] = ", ".join(RECIPIENT_EMAILS)
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))

                for file in attachments:
                    if not os.path.exists(file):
                        print(f"❌ Attachment not found: {file}")
                        return False
                    if os.path.exists(file):
                        with open(file, "rb") as attachment:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(file)}")
                            msg.attach(part)

                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
                server.quit()

                time.sleep(3)  # Ensure email delivery flush
                print("✅ Email sent successfully with attachments!")
                return True  # Exit function if success

            except Exception as e:
                error_log("Attempt {attempt+1} failed",e)
                time.sleep(wait_seconds)  # Wait before retry

        print("❌ All attempts failed. Email not sent.")
        return False  # All retries failed
    except Exception as e:
        error_log("Error",e)
        return False

def delete_bad_images(folder_path):
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                if os.path.isfile(file_path) and filename.endswith((".jpg", ".png",".tiff")):
                    os.remove(file_path)
                    print(f"🗑 Deleted: {filename}")
            except Exception as e:
                error_log(f"Error deleting {filename}",e)
        print("✅ All bad images deleted successfully.")
    else:
        print("⚠️ Warning: 'bad_images' folder does not exist.")


# from paths import OUTPUT_PDF
# attachments_path = OUTPUT_PDF
# # ✅ Trigger only if email is sent
# send_email_with_attachments(attachments_path)
#delete_bad_images("bad_images")
