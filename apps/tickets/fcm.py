import json
import requests
from django.conf import settings
from apps.usuarios.models import DispositivoNotificacion

from google.oauth2 import service_account
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


def _get_access_token():
    """
    Obtiene un token de acceso OAuth2 usando el JSON de servicio de Firebase.
    """
    print("[FCM] Obteniendo access token...")

    credentials = service_account.Credentials.from_service_account_file(
        str(settings.FIREBASE_CREDENTIALS_FILE),
        scopes=SCOPES,
    )
    credentials.refresh(Request())
    print("[FCM] Access token obtenido OK.")
    return credentials.token


def enviar_notificacion_nuevo_ticket(ticket):
    """
    Envía una notificación push FCM al técnico asignado al ticket.
    Usa HTTP v1: https://fcm.googleapis.com/v1/projects/PROJECT_ID/messages:send
    """
    try:
        if not ticket.asignado_a:
            print(f"[FCM] Ticket {ticket.id}: sin técnico asignado. No se envía push.")
            return

        # 1) Buscar dispositivos activos del técnico
        dispositivos = DispositivoNotificacion.objects.filter(
            usuario=ticket.asignado_a,
            activo=True,
        ).exclude(fcm_token__isnull=True).exclude(fcm_token__exact="")

        if not dispositivos.exists():
            print(f"[FCM] Ticket {ticket.id}: el técnico {ticket.asignado_a} no tiene dispositivos activos.")
            return

        print(f"[FCM] Ticket {ticket.id}: encontré {dispositivos.count()} dispositivo(s) para {ticket.asignado_a}.")

        # 2) Access token
        access_token = _get_access_token()

        url = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        # URL del ticket (asegúrate de que BASE_URL sea https://majestiksolutions.pythonanywhere.com)
        ticket_url = f"{settings.BASE_URL}/tickets/{ticket.id}/detalle/"

        # 3) Enviar a cada dispositivo
        for disp in dispositivos:
            cuerpo = {
                "message": {
                    "token": disp.fcm_token,
                    "notification": {
                        "title": f"Nuevo ticket {ticket.numero_ticket}",
                        "body": f"{ticket.local} - {ticket.categoria.nombre if ticket.categoria else ''}",
                    },
                    "data": {
                        "ticket_id": str(ticket.id),
                        "estado": ticket.estado,
                        "ticket_url": ticket_url,
                        # 👇 esto es clave para que Flutter reciba el tap
                        "click_action": "FLUTTER_NOTIFICATION_CLICK",
                    },
                    "android": {
                        "notification": {
                            # 👇 también aquí por compatibilidad
                            "click_action": "FLUTTER_NOTIFICATION_CLICK",
                        }
                    },
                }
            }

            print(f"[FCM] Enviando a token {disp.fcm_token[:20]}...")

            resp = requests.post(url, headers=headers, json=cuerpo, timeout=10)

            print(f"[FCM] Respuesta FCM: {resp.status_code} - {resp.text}")

    except Exception as e:
        # Cualquier error lo imprimimos para verlo en los logs de PythonAnywhere
        print(f"[FCM] ERROR enviando notificación: {e}")
