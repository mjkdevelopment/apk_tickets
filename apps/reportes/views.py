# apps/reportes/views.py
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.db.models import (
    Avg, Count, Sum, Q, F,
    DurationField, IntegerField, ExpressionWrapper, Case, When,
)
from django.db.models.functions import Coalesce

from apps.tickets.models import Ticket


def _human_timedelta(td):
    """Convierte timedelta a texto corto: 2d 3h 15m"""
    if td is None:
        return "-"
    try:
        total = int(td.total_seconds())
    except Exception:
        return "-"
    if total < 0:
        total = 0
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


@login_required
def reportes_dashboard(request):
    """
    Reportes (solo ADMIN):
    - SLA por banca (promedios, % cumplimiento)
    - Reincidencias por banca/categoría (últimos 3 meses)
    """
    if getattr(request.user, "rol", None) != "ADMIN":
        return HttpResponseForbidden("No tienes permiso para ver reportes.")

    ahora = timezone.now()
    # “Últimos 3 meses” -> usamos 90 días (simple y estable)
    desde = ahora - timedelta(days=90)

    estados_abiertos = ["PENDIENTE", "EN_PROCESO", "RESUELTO"]
    estados_cerrados = ["RESUELTO", "CERRADO"]

    # =========================
    # 1) Tickets abiertos (hoy)
    # =========================
    abiertos_qs = (
        Ticket.objects
        .filter(estado__in=estados_abiertos)
        .select_related("local", "categoria", "asignado_a", "creado_por")
    )

    abiertos_total = abiertos_qs.count()
    abiertos_vencidos = abiertos_qs.filter(fecha_limite_sla__lt=ahora).count()

    # =========================
    # 2) SLA por banca (3 meses)
    # =========================
    cerrados_qs = (
        Ticket.objects
        .filter(fecha_creacion__gte=desde, estado__in=estados_cerrados)
        .exclude(fecha_resolucion__isnull=True, fecha_cierre__isnull=True)
        .select_related("local", "categoria")
    )

    duracion_solucion = ExpressionWrapper(
        (Coalesce("fecha_resolucion", "fecha_cierre") - F("fecha_creacion")),
        output_field=DurationField(),
    )
    duracion_respuesta = ExpressionWrapper(
        (F("fecha_asignacion") - F("fecha_creacion")),
        output_field=DurationField(),
    )

    cumple_sla = Case(
        When(fecha_resolucion__isnull=False, fecha_resolucion__lte=F("fecha_limite_sla"), then=1),
        When(fecha_resolucion__isnull=True, fecha_cierre__isnull=False, fecha_cierre__lte=F("fecha_limite_sla"), then=1),
        default=0,
        output_field=IntegerField(),
    )

    sla_por_local_raw = (
        cerrados_qs
        .values("local_id", "local__codigo", "local__nombre")
        .annotate(
            total=Count("id"),
            on_time=Sum(cumple_sla),
            avg_solucion=Avg(duracion_solucion),
            avg_respuesta=Avg(duracion_respuesta),
        )
        .order_by("-total", "local__codigo")
    )

    # Abiertos agrupados por local para “estado actual”
    abiertos_por_local = {
        row["local_id"]: row
        for row in (
            abiertos_qs
            .values("local_id")
            .annotate(
                abiertos=Count("id"),
                vencidos=Count("id", filter=Q(fecha_limite_sla__lt=ahora)),
            )
        )
    }

    sla_por_local = []
    for row in sla_por_local_raw:
        total = row["total"] or 0
        on_time = row["on_time"] or 0
        pct = round((on_time / total) * 100, 1) if total else 0.0

        ab = abiertos_por_local.get(row["local_id"], {})
        sla_por_local.append({
            "codigo": row["local__codigo"],
            "nombre": row["local__nombre"],
            "total": total,
            "on_time": on_time,
            "pct_on_time": pct,
            "avg_solucion": _human_timedelta(row["avg_solucion"]),
            "avg_respuesta": _human_timedelta(row["avg_respuesta"]),
            "abiertos": ab.get("abiertos", 0),
            "abiertos_vencidos": ab.get("vencidos", 0),
        })

    # Totales generales del período
    total_cerrados = cerrados_qs.count()
    total_on_time = cerrados_qs.aggregate(s=Sum(cumple_sla)).get("s") or 0
    pct_on_time = round((total_on_time / total_cerrados) * 100, 1) if total_cerrados else 0.0
    avg_solucion_global = cerrados_qs.aggregate(a=Avg(duracion_solucion)).get("a")
    avg_respuesta_global = cerrados_qs.aggregate(a=Avg(duracion_respuesta)).get("a")

    # =========================
    # 3) Reincidencias (3 meses)
    # =========================
    reincidencias = (
        Ticket.objects
        .filter(fecha_creacion__gte=desde)
        .values("local__codigo", "local__nombre", "categoria__nombre")
        .annotate(total=Count("id"))
        .filter(total__gte=2)
        .order_by("-total", "local__codigo", "categoria__nombre")[:50]
    )

    # =========================
    # 4) Top técnicos cerrando
    # =========================
    tecnicos_top = (
        Ticket.objects
        .filter(estado__in=["CERRADO"], asignado_a__rol="TECNICO")
        .values("asignado_a__id", "asignado_a__first_name", "asignado_a__last_name", "asignado_a__username")
        .annotate(total_cerrados=Count("id"))
        .order_by("-total_cerrados")[:10]
    )

    contexto = {
        "desde": desde,
        "hoy": ahora,

        "abiertos_total": abiertos_total,
        "abiertos_vencidos": abiertos_vencidos,

        "total_cerrados": total_cerrados,
        "pct_on_time": pct_on_time,
        "avg_solucion_global": _human_timedelta(avg_solucion_global),
        "avg_respuesta_global": _human_timedelta(avg_respuesta_global),

        "sla_por_local": sla_por_local,
        "reincidencias": reincidencias,
        "tecnicos_top": tecnicos_top,
    }
    return render(request, "reportes/dashboard.html", contexto)
