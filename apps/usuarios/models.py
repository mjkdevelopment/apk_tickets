"""
Modelos para el sistema de usuarios
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado con roles
    """
    ROLES = [
        ('ADMIN', 'Administrador'),
        ('DIGITADOR', 'Digitador'),
        ('TECNICO', 'Técnico'),
    ]

    rol = models.CharField(
        max_length=20,
        choices=ROLES,
        default='DIGITADOR',
        verbose_name='Rol'
    )

    especialidades = models.ManyToManyField(
        'tickets.CategoriaAveria',
        blank=True,
        related_name='tecnicos_especialistas',
        verbose_name='Especialidades (tipos de avería)',
        help_text='Tipos de avería que este técnico puede atender (PC, Internet, Electricidad, etc.).',
    )

    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Teléfono'
    )

    whatsapp = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='WhatsApp',
        help_text='Formato: +1809XXXXXXX'
    )

    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de actualización'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['username']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"

    def es_admin(self):
        """Verifica si el usuario es administrador"""
        return self.rol == 'ADMIN'

    def es_digitador(self):
        """Verifica si el usuario es digitador"""
        return self.rol == 'DIGITADOR'

    def es_tecnico(self):
        """Verifica si el usuario es técnico"""
        return self.rol == 'TECNICO'

    def puede_crear_tickets(self):
        """Verifica si el usuario puede crear tickets"""
        return self.rol in ['ADMIN', 'DIGITADOR']

    def puede_trabajar_tickets(self):
        """Verifica si el usuario puede trabajar en tickets"""
        return self.rol in ['ADMIN', 'TECNICO']


class DispositivoNotificacion(models.Model):
    """
    Dispositivo (móvil / tablet) que recibe notificaciones push vía FCM
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dispositivos_notificacion',
        verbose_name='Usuario',
    )
    fcm_token = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Token FCM',
        help_text='Token de Firebase Cloud Messaging para este dispositivo.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de registro',
    )
    fecha_ultimo_uso = models.DateTimeField(
        auto_now=True,
        verbose_name='Último uso',
    )

    class Meta:
        verbose_name = 'Dispositivo de notificación'
        verbose_name_plural = 'Dispositivos de notificación'
        ordering = ['-fecha_ultimo_uso']

    def __str__(self):
        return f"{self.usuario} - {self.fcm_token[:12]}..."
