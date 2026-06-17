# test_smtp.py - local-ல் run பண்ணுங்க
import smtplib
import ssl
from email.mime.text import MIMEText

SMTP_HOST = 'smtp.hostinger.com'
SMTP_PORT = 465
SMTP_USER = 'mithun.r@miim.co.in'
SMTP_PASS = 'Mithun@0711'  # உங்க actual password

msg = MIMEText('Test mail from MIIM HRM')
msg['Subject'] = 'MIIM SMTP Test'
msg['From'] = SMTP_USER
msg['To'] = SMTP_USER  # உங்களுக்கே send பண்றோம்

try:
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context(), timeout=30) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [SMTP_USER], msg.as_string())
    print("✅ Mail sent successfully!")
except smtplib.SMTPAuthenticationError:
    print("❌ Wrong password!")
except Exception as e:
    print(f"❌ Error: {e}")