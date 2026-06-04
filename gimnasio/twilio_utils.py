from django.conf import settings
from django.core.mail import send_mail

try:
    from twilio.rest import Client
except ImportError:  # pragma: no cover - la librería se instala en el entorno real
    Client = None


def _get_twilio_client():
    """
    Crea el cliente de Twilio usando variables de entorno / settings.
    Si falta configuración o la librería, devuelve None.
    """
    if Client is None:
        return None
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    if not account_sid or not auth_token:
        return None
    return Client(account_sid, auth_token)


def send_sms(to_number: str, body: str) -> bool:
    """
    Envía un SMS usando Twilio.
    `to_number` debe venir en formato internacional, ej: +54911XXXXXXX.
    """
    client = _get_twilio_client()
    from_number = getattr(settings, "TWILIO_SMS_FROM", None)
    if not client or not from_number or not to_number:
        return False
    client.messages.create(body=body, from_=from_number, to=to_number)
    return True


def send_whatsapp(to_number: str, body: str) -> bool:
    """
    Envía un WhatsApp usando Twilio.
    Twilio requiere el prefijo 'whatsapp:'.
    """
    client = _get_twilio_client()
    from_number = getattr(settings, "TWILIO_WHATSAPP_FROM", None)
    if not client or not from_number or not to_number:
        return False
    client.messages.create(
        body=body,
        from_=f"whatsapp:{from_number}",
        to=f"whatsapp:{to_number}",
    )
    return True


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Envía un email usando la configuración de correo de Django.
    Podés conectar esto a Twilio SendGrid configurando EMAIL_BACKEND y credenciales.
    """
    if not to_email:
        return False
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not from_email:
        return False
    sent = send_mail(subject, body, from_email, [to_email], fail_silently=True)
    return bool(sent)

