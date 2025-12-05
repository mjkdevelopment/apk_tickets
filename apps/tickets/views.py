from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden

from .utils import enviar_whatsapp_ticket_asignado
from apps.tickets.models import Ticket, ComentarioTicket
from apps.tickets.forms import TicketForm, ComentarioTicketForm, TicketEstadoForm
from .fcm import enviar_notificacion_nuevo_ticket


@login_required
def tickets_lista(request):
    """
    Lista de tickets filtrada por rol y por estado.

    - ADMIN:
        puede ver abiertos / cerrados / todos (filtro ?ver=...)
    - DIGITADOR:
        igual que admin pero solo de los que él creó
    - TÉCNICO:
        SOLO ve tickets ABIERTOS:
          * los que tiene asignados
          * + los sin asignar de sus categorías de especialidad
    """
    usuario = request.user
    ver = request.GET.get('ver', 'abiertos')

    tickets = Ticket.objects.select_related(
        'local', 'categoria', 'creado_por', 'asignado_a'
    )

    # --- Filtro por rol ---
    if usuario.es_digitador():
        tickets = tickets.filter(creado_por=usuario)

    elif usuario.es_tecnico():
        cats = usuario.especialidades.all()

        if cats.exists():
            tickets = tickets.filter(
                Q(asignado_a=usuario) |
                Q(asignado_a__isnull=True, categoria__in=cats)
            )
        else:
            # Técnico sin especialidades configuradas => ve solo
            # tickets abiertos asignados a él o sin asignar
            tickets = tickets.filter(
                Q(asignado_a=usuario) |
                Q(asignado_a__isnull=True)
            )

        # Para técnicos SIEMPRE solo abiertos, ignoramos ?ver
        tickets = tickets.exclude(
            estado__in=['RESUELTO', 'CERRADO', 'CANCELADO']
        )
        ver = 'abiertos'  # para marcar pestaña en plantilla si usas tabs

    else:
        # ADMIN normal
        if ver == 'abiertos':
            tickets = tickets.exclude(
                estado__in=['RESUELTO', 'CERRADO', 'CANCELADO']
            )
        elif ver == 'cerrados':
            tickets = tickets.filter(
                estado__in=['RESUELTO', 'CERRADO', 'CANCELADO']
            )
        # ver == 'todos' => sin filtro extra

    tickets = tickets.order_by('-fecha_creacion')

    contexto = {
        'tickets': tickets,
        'ver': ver,
    }
    return render(request, 'tickets/tickets_lista.html', contexto)


@login_required
def ticket_crear(request):
    """
    Crear un nuevo ticket.
    Solo ADMIN y DIGITADOR pueden crear.
    """
    usuario = request.user

    if not usuario.puede_crear_tickets():
        messages.error(request, 'No tienes permiso para crear tickets.')
        return redirect('tickets_lista')

    if request.method == 'POST':
        form = TicketForm(request.POST, usuario=usuario)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.creado_por = usuario

            # ==========================
            # Generar título automático
            # ==========================
            desc = (ticket.descripcion or '').strip().replace('\n', ' ')
            resumen = desc[:60]
            if len(desc) > 60:
                resumen += '...'

            if ticket.categoria_id:
                base = ticket.categoria.nombre
            else:
                base = 'Ticket'

            ticket.titulo = f'{base} - {resumen}' if resumen else base
            # ==========================

            ticket.save()
            form.save_m2m()  # por si el form tiene ManyToMany

            # 👉 WhatsApp al técnico asignado (como ya tenías)
            enviar_whatsapp_ticket_asignado(ticket)

            # 👉 NUEVO: notificación push al técnico asignado (FCM)
            try:
                enviar_notificacion_nuevo_ticket(ticket)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Error enviando notificación FCM para el ticket %s",
                    ticket.id,
                )

            messages.success(request, f'Ticket {ticket.numero_ticket} creado correctamente.')
            return redirect('ticket_detalle', pk=ticket.pk)
    else:
        form = TicketForm(usuario=usuario)

    return render(request, 'tickets/ticket_form.html', {'form': form})


@login_required
def ticket_detalle(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    usuario = request.user

    # ---------- PERMISOS DE VISUALIZACIÓN ----------
    if usuario.es_admin():
        # Admin ve todo
        pass

    elif usuario.es_digitador():
        # Digitador solo ve tickets que él creó
        if ticket.creado_por != usuario:
            return HttpResponseForbidden("No tienes permiso para ver este ticket.")

    elif usuario.es_tecnico():
        # Técnico: siempre puede ver los que están asignados a él
        if ticket.asignado_a == usuario:
            pass
        else:
            # Si está asignado a otro → no
            if ticket.asignado_a is not None:
                return HttpResponseForbidden("No tienes permiso para ver este ticket.")

            # Si está sin asignar: solo si la categoría está en sus especialidades
            cats = usuario.especialidades.all()
            if cats.exists() and ticket.categoria not in cats:
                return HttpResponseForbidden("No tienes permiso para ver este ticket.")
    else:
        return HttpResponseForbidden("No tienes permiso para ver este ticket.")
    # ---------- FIN PERMISOS DE VISTA ----------

    # ¿Quién puede CAMBIAR el ESTADO?
    #   ✅ Admin
    #   ✅ Técnico asignado
    if usuario.es_admin():
        puede_actualizar_estado = True
    elif usuario.es_tecnico() and ticket.asignado_a == usuario:
        puede_actualizar_estado = True
    else:
        puede_actualizar_estado = False

    comentarios = ComentarioTicket.objects.filter(
        ticket=ticket
    ).select_related('usuario').order_by('fecha_creacion')

    # ---------- POST / GET ----------
    if request.method == "POST":

        # 1) Actualizar estado
        if "actualizar_estado" in request.POST:
            if not puede_actualizar_estado:
                # Digitador o técnico no asignado intentando cambiar estado
                return HttpResponseForbidden("No tienes permiso para cambiar el estado de este ticket.")

            estado_form = TicketEstadoForm(
                request.POST,
                request.FILES,
                instance=ticket,
                usuario=usuario,   # 👈 clave para que el form sepa quién eres
            )
            comentario_form = ComentarioTicketForm()

            if estado_form.is_valid():
                tecnico_original = ticket.asignado_a
                ticket_obj = estado_form.save(commit=False)

                # Solo admin puede cambiar el técnico asignado
                if not usuario.es_admin():
                    ticket_obj.asignado_a = tecnico_original

                ticket_obj.save()
                messages.success(request, "Ticket actualizado correctamente.")
                return redirect("ticket_detalle", pk=ticket_obj.pk)

        # 2) Nuevo comentario
        elif "nuevo_comentario" in request.POST:
            comentario_form = ComentarioTicketForm(request.POST, request.FILES)
            estado_form = TicketEstadoForm(instance=ticket, usuario=usuario)

            if comentario_form.is_valid():
                comentario = comentario_form.save(commit=False)
                comentario.ticket = ticket
                comentario.usuario = usuario
                comentario.save()
                messages.success(request, "Comentario agregado.")
                return redirect("ticket_detalle", pk=ticket.pk)

        else:
            # POST raro: recargamos formularios
            estado_form = TicketEstadoForm(instance=ticket, usuario=usuario)
            comentario_form = ComentarioTicketForm()

    else:
        # GET normal
        estado_form = TicketEstadoForm(instance=ticket, usuario=usuario)
        comentario_form = ComentarioTicketForm()

    # ---------- SIEMPRE llegamos aquí con un HttpResponse ----------
    return render(request, "tickets/ticket_detalle.html", {
        "ticket": ticket,
        "estado_form": estado_form,
        "comentario_form": comentario_form,
        "comentarios": comentarios,
        "puede_actualizar_estado": puede_actualizar_estado,
    })


@login_required
def ticket_tomar(request, pk):
    """
    Permite a un TÉCNICO tomar un ticket que esté sin asignar.
    Solo si la categoría está dentro de sus especialidades.
    """
    usuario = request.user
    ticket = get_object_or_404(Ticket, pk=pk)

    if not usuario.es_tecnico():
        return HttpResponseForbidden("Solo los técnicos pueden tomar tickets.")

    # Ya tiene técnico asignado → no se puede tomar
    if ticket.asignado_a and ticket.asignado_a != usuario:
        messages.error(request, "Este ticket ya tiene un técnico asignado.")
        return redirect('ticket_detalle', pk=ticket.pk)

    # Comprobar especialidades
    cats = usuario.especialidades.all()
    if cats.exists() and ticket.categoria not in cats:
        messages.error(request, "Este ticket no corresponde a tus tipos de avería.")
        return redirect('ticket_detalle', pk=ticket.pk)

    if request.method == 'POST':
        ticket.asignado_a = usuario
        ticket.save()
        messages.success(request, "Has tomado este ticket.")
        return redirect('ticket_detalle', pk=ticket.pk)

    return redirect('ticket_detalle', pk=ticket.pk)


@login_required
def ticket_actualizar_estado(request, pk):
    """
    Cambiar estado, solución, técnico asignado y foto de reparación.
    Solo ADMIN y TECNICO.
    """
    ticket = get_object_or_404(Ticket, pk=pk)
    usuario = request.user

    if not (usuario.es_admin() or usuario.es_tecnico()):
        return HttpResponseForbidden('No tienes permiso para cambiar el estado de este ticket.')

    if request.method == 'POST':
        form = TicketEstadoForm(request.POST, request.FILES, instance=ticket, usuario=usuario)
        if form.is_valid():
            tecnico_original = ticket.asignado_a

            ticket_obj = form.save(commit=False)

            # Si NO es admin, no le dejamos cambiar el técnico
            if not request.user.es_admin():
                ticket_obj.asignado_a = tecnico_original

            ticket_obj.save()
            messages.success(request, "Ticket actualizado correctamente.")
            return redirect('ticket_detalle', pk=ticket_obj.pk)
    else:
        form = TicketEstadoForm(instance=ticket, usuario=usuario)

    return render(request, 'tickets/ticket_estado_form.html', {
        'ticket': ticket,
        'form': form,
    })
