"""
Configuración del admin de Django para usuarios
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, DispositivoNotificacion


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = [
        'username', 'email', 'first_name', 'last_name', 
        'rol', 'activo', 'is_active'
    ]
    list_filter = ['rol', 'activo', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información Adicional', {
            'fields': ('rol', 'telefono', 'whatsapp', 'activo')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Adicional', {
            'fields': ('rol', 'telefono', 'whatsapp', 'activo')
        }),
    )


@admin.register(DispositivoNotificacion)
class DispositivoNotificacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "plataforma", "token", "fecha_registro", "activo")
    list_filter = ("plataforma", "activo")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "token")

