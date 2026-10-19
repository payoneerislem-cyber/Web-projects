import smtplib

from email.mime.text import MIMEText
from flask import current_app


def send_otp_email(receiver_email, otp_code):
    username = current_app.config["MAIL_USERNAME"]
    password = current_app.config["MAIL_PASSWORD"]
    sender = current_app.config["MAIL_SENDER"] or username

    if not username or not password or not sender:
        return False

    body = f"Verification code: {otp_code}\n\nDo not share this code with anyone."
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = "Budget Tracker - Password Reset Code"
    message["From"] = sender
    message["To"] = receiver_email

    try:
        with smtplib.SMTP(current_app.config["MAIL_SERVER"], current_app.config["MAIL_PORT"], timeout=15) as server:
            if current_app.config["MAIL_USE_TLS"]:
                server.starttls()
            server.login(username, password)
            server.sendmail(sender, receiver_email, message.as_string())
        return True
    except (OSError, smtplib.SMTPException):
        return False
