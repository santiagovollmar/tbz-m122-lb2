import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from .config import config
from .templating import render_mail


def send_mail(invoice, zip):
    c = config().email
    message = render_mail(invoice)

    with smtplib.SMTP_SSL(c.hostname, c.port, context=ssl.create_default_context()) as server:
        server.login(c.username, c.password)

        mail = MIMEMultipart()
        mail['From'] = f"Santiago Gabriel Vollmar <m122_vollmer@mail.ch>"
        mail['To'] = f"{invoice.recipient.human} <{invoice.recipient.email}>"
        mail['Subject'] = f"Erfolgte Verarbeitung Rechnung {invoice.id}"
        mail.attach(MIMEText(message, 'plain'))

        zip_attachment = MIMEBase('application', "octet-stream")
        zip_attachment.set_payload(zip[1])
        encoders.encode_base64(zip_attachment)
        zip_attachment.add_header('Content-Disposition', f'attachment; filename="{zip[0]}"')

        mail.attach(zip_attachment)

        logger.debug(f'Mail contents: {mail}')
        server.sendmail('m122_vollmer@mail.ch', invoice.recipient.email, mail.as_string())