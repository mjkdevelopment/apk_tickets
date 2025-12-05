from django import forms

from apps.tickets.models import Ticket, ComentarioTicket, CategoriaAveria
from apps.locales.models import Local
from apps.usuarios.models import Usuario


class TicketForm(forms.ModelForm):
    """
    Formulario para crear/editar tickets.
    NO pedimos título: se genera automático en la vista.

    El campo `local` se maneja como texto libre:
    - Si el nombre existe en Local, se reutiliza.
    - Si no existe, se crea automáticamente.
    """

    local = forms.CharField(
        label="Local *",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Escribe el nombre del local...",
            }
        ),
    )

    class Meta:
        model = Ticket
        fields = ["local", "categoria", "descripcion", "prioridad", "asignado_a"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        usuario = kwargs.pop("usuario", None)
        super().__init__(*args, **kwargs)

        self.usuario = usuario

        # Labels más claros
        self.fields["descripcion"].label = "Comentario / descripción de la avería"

        # Estilos Bootstrap
        # `local` es un input de texto (ya tiene form-control arriba)
        self.fields["categoria"].widget.attrs.update({"class": "form-select"})
        self.fields["prioridad"].widget.attrs.update({"class": "form-select"})
        self.fields["descripcion"].widget.attrs.update({"class": "form-control"})
        self.fields["asignado_a"].widget.attrs.update({"class": "form-select"})

        # Si estamos editando, prellenar el nombre del local actual
        if self.instance.pk and getattr(self.instance, "local", None):
            self.fields["local"].initial = self.instance.local.nombre

        # Solo técnicos activos en el combo
        self.fields["asignado_a"].queryset = Usuario.objects.filter(
            rol="TECNICO",
            activo=True,
        )

        # Para no admins, que el técnico sea opcional
        if not (usuario and usuario.es_admin()):
            self.fields["asignado_a"].required = False

    def clean_local(self):
        nombre = (self.cleaned_data.get("local") or "").strip()
        if not nombre:
            raise forms.ValidationError("Debes escribir el nombre del local.")
        return nombre

    def clean_asignado_a(self):
        tecnico = self.cleaned_data.get("asignado_a")
        categoria = self.cleaned_data.get("categoria")

        if tecnico and categoria:
            # Si el técnico NO tiene esa categoría como especialidad => error
            if not tecnico.especialidades.filter(pk=categoria.pk).exists():
                nombre = tecnico.get_full_name() or tecnico.username
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    f'El técnico "{nombre}" no tiene la categoría '
                    f'"{categoria}" como especialidad.'
                )

        return tecnico

    def save(self, commit=True):
        """
        Convierte el texto del campo `local` en un objeto Local.
        Si no existe, lo crea.
        """
        ticket = super().save(commit=False)

        nombre_local = self.cleaned_data["local"].strip()

        # Buscar local por nombre, sin importar mayúsculas/minúsculas
        local = Local.objects.filter(nombre__iexact=nombre_local).first()
        if not local:
            local = Local.objects.create(nombre=nombre_local)

        ticket.local = local

        if commit:
            ticket.save()
            self.save_m2m()

        return ticket


class TicketEstadoForm(forms.ModelForm):
    """
    Formulario para cambiar estado / solución / foto de un ticket.
    El admin también puede cambiar el técnico asignado.
    """

    class Meta:
        model = Ticket
        fields = ["estado", "solucion", "foto_reparacion", "asignado_a"]
        widgets = {
            "solucion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        # 👇 aquí viene el usuario logueado, si la vista lo manda
        usuario = kwargs.pop("usuario", None)
        super().__init__(*args, **kwargs)

        self.usuario = usuario

        # Estilos Bootstrap
        self.fields["estado"].widget.attrs.update({"class": "form-select"})
        self.fields["solucion"].widget.attrs.update({"class": "form-control"})
        if "foto_reparacion" in self.fields:
            self.fields["foto_reparacion"].widget.attrs.update(
                {"class": "form-control"}
            )

        # Configurar el combo de técnicos
        self.fields["asignado_a"].widget.attrs.update({"class": "form-select"})
        self.fields["asignado_a"].queryset = Usuario.objects.filter(
            rol="TECNICO",
            activo=True,
        )
        self.fields["asignado_a"].label = "Técnico asignado"

        # 🔒 Solo el admin puede cambiar el técnico asignado
        if not (usuario and usuario.es_admin()):
            self.fields["asignado_a"].disabled = True

    def clean_asignado_a(self):
        tecnico = self.cleaned_data.get("asignado_a")
        categoria = getattr(self.instance, "categoria", None)

        if tecnico and categoria:
            if not tecnico.especialidades.filter(pk=categoria.pk).exists():
                nombre = tecnico.get_full_name() or tecnico.username
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    f'El técnico "{nombre}" no tiene la categoría '
                    f'"{categoria}" como especialidad.'
                )

        return tecnico


class ComentarioTicketForm(forms.ModelForm):
    """
    Formulario para agregar comentarios a un ticket.
    Solo técnicos y admins pueden marcar comentarios como internos.
    """

    class Meta:
        model = ComentarioTicket
        fields = ["comentario", "es_interno"]
        widgets = {
            "comentario": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Escribe tu comentario aquí...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["comentario"].widget.attrs.update({"class": "form-control"})

        # Si no es técnico ni admin, ocultamos el campo "es_interno"
        if user and not (user.es_tecnico() or user.es_admin()):
            self.fields.pop("es_interno", None)


class FiltroTicketsForm(forms.Form):
    """
    (Opcional) Filtro para listar tickets.
    Aunque ahora no lo usemos, lo dejamos por si alguna vista lo importa.
    """

    ESTADO_CHOICES = [("", "Todos los estados")] + list(
        Ticket._meta.get_field("estado").choices
    )
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    categoria = forms.ModelChoiceField(
        queryset=CategoriaAveria.objects.filter(activo=True),
        required=False,
        empty_label="Todas las categorías",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    local = forms.ModelChoiceField(
        queryset=Local.objects.filter(activo=True),
        required=False,
        empty_label="Todos los locales",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Buscar por número, título, local o comentario...",
            }
        ),
    )
