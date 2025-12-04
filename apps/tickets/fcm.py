import logging
import os

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

from apps.usuarios.models import DispositivoNotificacion

logger = logging.getLogger(__name__)


def _init_firebase_app():
    """
    Inicializa Firebase Admin una sola vez por proceso.
    """
    if firebase_admin._apps:
        # Ya hay una app inicializada
        return firebase_admin.get_app()

    # Primero probamos con settings.FIREBASE_CREDENTIALS_PATH
    cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or ""

    # Si no hay nada, intentamos con la variable de entorno estándar
    if not cred_path:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

    if not cred_path:
        logger.warning(
            "Firebase no inicializado: no hay FIREBASE_CREDENTIALS_PATH "
            "ni GOOGLE_APPLICATION_CREDENTIALS configurado."
        )
        return None

    if not os.path.exists(cred_path):
        logger.error("Firebase: el archivo de credenciales no existe: %s", cred_path)
        return None

    try:
        cred = credentials.Certificate(cred_path)
        app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin inicializado correctamente.")
        return app
    except Exception as e:
        logger.exception("Error inicializando Firebase Admin: %s", e)
        return None


def enviar_notificacion_nuevo_ticket(ticket):
    """
    Envía una notificación push al técnico asignado cuando se crea un ticket.
    Usa los tokens guardados en DispositivoNotificacion.
    """
    app = _init_firebase_app()
    if app is None:
        return 0

    if not ticket.asignado_a_id:
        logger.info(
            "Ticket %s no tiene técnico asignado, no se envía notificación.",
            ticket.numero_ticket,
        )
        return 0

    dispositivos = DispositivoNotificacion.objects.filter(
        usuario=ticket.asignado_a, activo=True
    )

    tokens = [d.fcm_token for d in dispositivos if d.fcm_token]
    if not tokens:
        logger.info(
            "Usuario %s no tiene dispositivos activos con token FCM.",
            ticket.asignado_a,
        )
        return 0

    titulo = f"Nuevo ticket {ticket.numero_ticket}"
    cuerpo = ticket.titulo or f"{ticket.local} - {ticket.categoria}"

    # Puedes añadir más datos para que la app los reciba en onMessage/openedApp
    data = {
        "ticket_id": str(ticket.id),
        "numero_ticket": ticket.numero_ticket,
        "estado": ticket.estado,
        "local": str(ticket.local),
    }

    try:
        # Mandamos a todos los tokens de ese técnico
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=titulo,
                body=cuerpo,
            ),
            data=data,
            tokens=tokens,
        )
        response = messaging.send_multicast(message, app=app)

        logger.info(
            "Notificación FCM enviada. Éxitos: %s / Errores: %s",
            response.success_count,
            response.failure_count,
        )

        # Por si quieres ver detalles en los logs:
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                logger.warning(
                    "Error enviando a token %s: %s",
                    tokens[idx],
                    resp.exception,
                )

        return response.success_count
    except Exception as e:
        logger.exception("Error enviando notificación FCM para ticket %s: %s", ticket.id, e)
        return 0


def enviar_notificacion_prueba(usuario):
    """
    Para probar rápido desde la shell de Django.
    """
    app = _init_firebase_app()
    if app is None:
        return 0

    dispositivos = DispositivoNotificacion.objects.filter(
        usuario=usuario, activo=True
    )
    tokens = [d.fcm_token for d in dispositivos if d.fcm_token]
    if not tokens:
        logger.info("Usuario %s no tiene tokens FCM activos.", usuario)
        return 0

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="Prueba de MJK Tickets",
            body="Si lees esto, las notificaciones funcionan 😎",
        ),
        tokens=tokens,
        data={"tipo": "prueba"},
    )

    try:
        response = messaging.send_multicast(message, app=app)
        logger.info(
            "Notificación de prueba enviada. Éxitos: %s / Errores: %s",
            response.success_count,
            response.failure_count,
        )
        return response.success_count
    except Exception as e:
        logger.exception("Error enviando notificación de prueba: %s", e)
        return 0
