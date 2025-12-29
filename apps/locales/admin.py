from django.contrib import admin
from .models import Local   # 👈 el modelo de tus locales

@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    # Lo dejo simple para no depender de nombres de campos.
    # Si luego quieres, se puede mejorar con list_display, search_fields, etc.
    pass
