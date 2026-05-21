"""
SMTP service for sending emails
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from open_notebook.database.repository import repo_query


class SMTPService:
    """Service for sending emails via SMTP"""

    @staticmethod
    async def get_config() -> Optional[dict]:
        """Get SMTP configuration from database"""
        query = "SELECT * FROM smtp_config WHERE id = 'default' AND is_active = 1"
        results = await repo_query(query)

        if not results:
            return None

        return results[0]

    @staticmethod
    async def send_email(to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        """
        Send an email using configured SMTP settings

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            is_html: Whether body is HTML

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            await SMTPService.send_email_strict(to_email, subject, body, is_html)
            return True
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False

    @staticmethod
    async def send_email_strict(to_email: str, subject: str, body: str, is_html: bool = False) -> None:
        """Send email and raise the underlying exception on failure.

        Use this when callers need the real reason for failure (e.g. invalid
        recipient, auth failure, connection refused) instead of a generic bool.
        """
        config = await SMTPService.get_config()

        if not config:
            raise RuntimeError("SMTP not configured. Add SMTP settings under Settings → SMTP.")

        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{config.get('smtp_from_name', 'Open Notebook')} <{config['smtp_from_email']}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        mime_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, mime_type))

        # Connect
        if config.get("smtp_use_ssl"):
            server = smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"])
        else:
            server = smtplib.SMTP(config["smtp_host"], config["smtp_port"])
            if config.get("smtp_use_tls"):
                server.starttls()

        try:
            server.login(config["smtp_username"], config["smtp_password"])
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass

        print(f"✅ Email sent to {to_email}")

    @staticmethod
    async def send_otp_email(to_email: str, otp_code: str, microsite_title: str) -> bool:
        """
        Send OTP code email for microsite access

        Args:
            to_email: Recipient email address
            otp_code: 6-digit OTP code
            microsite_title: Title of the microsite

        Returns:
            True if email sent successfully
        """
        subject = f"Access Code for {microsite_title}"

        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
                .otp-code {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; text-align: center; background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0; color: #4F46E5; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Your Access Code</h1>
                </div>
                <div class="content">
                    <p>You requested access to <strong>{microsite_title}</strong>.</p>
                    <p>Use the following code to verify your access:</p>
                    <div class="otp-code">{otp_code}</div>
                    <p><strong>This code will expire in 15 minutes.</strong></p>
                    <p>If you didn't request this code, you can safely ignore this email.</p>
                </div>
                <div class="footer">
                    <p>Open Notebook - Privacy-focused research platform</p>
                </div>
            </div>
        </body>
        </html>
        """

        body_text = f"""
        Your Access Code for {microsite_title}

        You requested access to {microsite_title}.

        Your verification code is: {otp_code}

        This code will expire in 15 minutes.

        If you didn't request this code, you can safely ignore this email.

        ---
        Open Notebook - Privacy-focused research platform
        """

        # Try HTML first, fallback to plain text
        success = await SMTPService.send_email(to_email, subject, body_html, is_html=True)

        if not success:
            # Fallback to plain text
            success = await SMTPService.send_email(to_email, subject, body_text, is_html=False)

        return success
