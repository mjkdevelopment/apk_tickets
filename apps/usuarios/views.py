"""
Vistas para el sistema de usuarios
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.urls import reverse

from .forms import LoginForm, UsuarioCreateForm, UsuarioUpdateForm

Usuario = get_user_model()


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = (request.POST.get("username") or request.POST.get("usuario") or "").strip()
        password = request.POST.get("password") or request.POST.get("contrasena") or ""
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")

        messages.error(request, "Usuario o contraseña incorrectos")

    # mantenemos el form solo para render bonito
    form = LoginForm(request)
    return render(request, "usuarios/login.html", {"form": form})


@login_required
def logout_view(request):
    """
    Cerrar sesión
    """
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    """
    Dashboard principal.

    - ADMIN: ve todos los tickets abiertos.
    - DIGITADOR: ve sus tickets abiertos.
    - TÉCNICO: ve sus tickets asignados abiertos + (si aplica) tickets sin asignar de sus especialidades.
    """
    from apps.tickets.models import Ticket  # import local para evitar ciclos raros
    from django.db.models import Q
    from django.utils import timezone
    from datetime import timedelta

    usuario = request.user
    ahora = timezone.now()

    estados_abiertos = ['PENDIENTE', 'EN_PROCESO', 'RESUELTO']

    qs = (
        Ticket.objects
        .filter(estado__in=estados_abiertos)
        .select_related('local', 'categoria', 'asignado_a', 'creado_por')
    )

    if usuario.rol == 'DIGITADOR':
        qs = qs.filter(creado_por=usuario)

    elif usuario.rol == 'TECNICO':
        cats = usuario.especialidades.all()
        if cats.exists():
            qs = qs.filter(
                Q(asignado_a=usuario) |
                Q(asignado_a__isnull=True, categoria__in=cats)
            )
        else:
            qs = qs.filter(asignado_a=usuario)

    # Resumen
    total_abiertos = qs.count()
    vencidos = qs.filter(fecha_limite_sla__lt=ahora).count()
    por_vencer_2h = qs.filter(
        fecha_limite_sla__gte=ahora,
        fecha_limite_sla__lte=ahora + timedelta(hours=2),
    ).count()

    # Orden: lo más urgente arriba
    tickets_abiertos = qs.order_by('fecha_limite_sla', '-fecha_creacion')[:50]

    contexto = {
        "user": usuario,
        "tickets_abiertos": tickets_abiertos,
        "total_abiertos": total_abiertos,
        "vencidos": vencidos,
        "por_vencer_2h": por_vencer_2h,
        "ahora": ahora,
    }
    return render(request, "dashboard.html", contexto)


@login_required
def usuarios_lista(request):
    """
    Lista de usuarios (solo admin)
    """
    if not request.user.es_admin():
        messages.error(request, "No tienes permisos para ver usuarios")
        return redirect("dashboard")

    usuarios = Usuario.objects.all().order_by("username")
    return render(request, "usuarios/usuarios_lista.html", {"usuarios": usuarios})


@login_required
def usuario_crear(request):
    """
    Crear usuario (solo admin)
    """
    if not request.user.es_admin():
        messages.error(request, "No tienes permisos para crear usuarios")
        return redirect("dashboard")

    if request.method == "POST":
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, "Usuario creado correctamente")
            return redirect("usuario_detalle", pk=usuario.pk)
    else:
        form = UsuarioCreateForm()

    return render(
        request,
        "usuarios/usuario_form.html",
        {"form": form, "titulo": "Crear usuario"},
    )


@login_required
def usuario_detalle(request, pk):
    """
    Detalle de usuario (solo admin)
    """
    if not request.user.es_admin():
        messages.error(request, "No tienes permisos para ver usuarios")
        return redirect("dashboard")

    usuario = get_object_or_404(Usuario, pk=pk)
    return render(request, "usuarios/usuario_detalle.html", {"usuario": usuario})


@login_required
def usuario_editar(request, pk):
    """
    Editar usuario (solo admin)
    """
    if not request.user.es_admin():
        messages.error(request, "No tienes permisos para editar usuarios")
        return redirect("dashboard")

    usuario = get_object_or_404(Usuario, pk=pk)

    if request.method == "POST":
        form = UsuarioUpdateForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado correctamente")
            return redirect("usuario_detalle", pk=usuario.pk)
    else:
        form = UsuarioUpdateForm(instance=usuario)

    return render(
        request,
        "usuarios/usuario_form.html",
        {"form": form, "titulo": "Editar usuario"},
    )
