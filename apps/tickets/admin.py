# apps/tickets/admin.py
from django.contrib import admin
from . import models

"""
Registro sencillo de los modelos del app `tickets` en el admin.

IMPORTANTE:
- No usamos list_display ni nada raro a propósito,
  para evitar errores como el de 'autor' que te salió antes.
- Solo registramos si el modelo existe en models.py,
  así no se rompe si algún nombre cambia en el futuro.
"""

if hasattr(models, "Ticket"):
    admin.site.register(models.Ticket)

if hasattr(models, "ComentarioTicket"):
    admin.site.register(models.ComentarioTicket)

if hasattr(models, "CategoriaAveria"):
    admin.site.register(models.CategoriaAveria)
