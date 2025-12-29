from django.contrib import admin
from .models import Ticket, CategoriaAveria, ComentarioTicket


@admin.register(CategoriaAveria)
class CategoriaAveriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'numero_ticket',
        'titulo',
        'local',
        'categoria',
        'estado',
        'prioridad',
        'creado_por',
        'asignado_a',
        'fecha_creacion',
    )
    list_filter = ('estado', 'prioridad', 'categoria', 'local')
    search_fields = ('numero_ticket', 'titulo', 'descripcion', 'local__codigo')


@admin.register(ComentarioTicket)
class ComentarioTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'autor', 'es_interno', 'fecha_creacion')
    list_filter = ('es_interno',)
    search_fields = ('ticket__numero_ticket', 'comentario', 'autor__username')
