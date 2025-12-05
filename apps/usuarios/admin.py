from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms

from .models import Usuario, DispositivoNotificacion


class UsuarioAdminForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        rol = cleaned_data.get("rol")
        especialidades = cleaned_data.get("especialidades")

        # Intentamos usar la constante, si existe
        rol_tecnico = getattr(Usuario, "ROL_TECNICO", "TECNICO")

        # Si es técnico y no tiene ninguna categoría asignada -> error
        if rol == rol_tecnico:
            if not especialidades or especialidades.count() == 0:
                raise forms.ValidationError(
                    "Cuando el usuario es TÉCNICO debes seleccionar al menos "
                    "una categoría de avería en el campo 'especialidades'."
                )

        return cleaned_data


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioAdminForm

    list_display = ("username", "first_name", "last_name", "rol", "is_active")
    list_filter = ("rol", "is_active", "is_staff", "is_superuser")

    fieldsets = UserAdmin.fieldsets + (
        ("Rol y categorías", {"fields": ("rol", "especialidades")}),
    )

    filter_horizontal = ("groups", "user_permissions", "especialidades")


@admin.register(DispositivoNotificacion)
class DispositivoNotificacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "activo")
    list_filter = ("activo",)
    search_fields = ("usuario__username", "fcm_token")
