from django.contrib import admin

from .models import *
# Register your models here.

class CampoDefinidoInline(admin.TabularInline):
    model = CampoDefinido
    extra = 1
    fields = ('etiqueta', 'tipo', 'tipo_original', 'default_value', 'values', 'validate', 'conditional', 'validate_when_hidden', 'visible_para', 'activo')
    readonly_fields = ('clave', 'etiqueta', 'tipo', 'tipo_original')
    autocomplete_fields = ['visible_para']
    show_change_link = True
    can_delete = True
    max_num = 10
    min_num = 1

@admin.register(Formulario)
class FormularioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha')
    search_fields = ('nombre',)
    inlines = [CampoDefinidoInline]
    ordering = ('-fecha',)
    list_filter = ('fecha',)
    date_hierarchy = 'fecha'
    list_per_page = 20
    list_select_related = True
    actions = ['exportar_csv']


class RespuestaEncuestaInline(admin.TabularInline):
    model = RespuestaEncuesta
    extra = 1
    fields = ('usuario', 'enviado')
    readonly_fields = ('usuario', 'enviado')
    show_change_link = True
    can_delete = True

@admin.register(Encuesta)
class EncuestaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'formulario', 'activa', 'fecha_inicio', 'fecha_fin')
    search_fields = ('nombre', 'descripcion')
    inlines = [RespuestaEncuestaInline]
    list_filter = ('activa', 'formulario')
    ordering = ('-fecha_inicio',)
    date_hierarchy = 'fecha_inicio'
    list_per_page = 20
    list_select_related = True


@admin.register(CampoRespuesta)
class CampoRespuestaAdmin(admin.ModelAdmin):
    list_display = ('respuesta', 'etiqueta', 'clave', 'valor', 'valor_numerico', 'valor_fecha', 'valor_time', 'valor_datetime', 'valor_booleano', 'valor_lista')
    search_fields = ('respuesta__encuesta__nombre', 'clave', 'valor')
    list_filter = ('respuesta__encuesta__formulario',)
    ordering = ('-respuesta__enviado',)
    date_hierarchy = 'respuesta__enviado'
    list_per_page = 20
    list_select_related = True
    