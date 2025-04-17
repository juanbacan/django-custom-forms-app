import json

from django.contrib.auth.models import Group
from datetime import datetime

from .models import CampoDefinido, CampoRespuesta


# Mapeo de tipo Formio a tipo lógico
formio_type_to_logical_type = {
    "textfield": "text",
    "textarea": "text",
    "email": "text",
    "phoneNumber": "text",
    "url": "text",
    "tags": "text",
    "password": "text",
    "number": "number",
    "currency": "number",
    "checkbox": "boolean",
    "selectboxes": "multi_select",
    "select": "select",
    "radio": "radio",
    "datetime": "datetime",
    "day": "date",
    "time": "time",
    "file": "file",
    "signature": "signature",
    "survey": "survey",
    "custom": "custom",
    "button": None,
    "content": None,
    "htmlelement": None,
}

def extraer_componentes(schema):
    campos = []

    def procesar_componentes(componentes):
        for comp in componentes:
            tipo = comp.get('type')
            if tipo in ['panel', 'well', 'columns', 'fieldset', 'tabs', 'container']:
                if tipo == 'tabs':
                    for tab in comp.get('components', []):
                        procesar_componentes(tab.get('components', []))
                elif tipo == 'columns':
                    for col in comp.get('columns', []):
                        procesar_componentes(col.get('components', []))
                else:
                    procesar_componentes(comp.get('components', []))
            elif tipo == 'table':
                for row in comp.get('rows', []):
                    for cell in row:
                        procesar_componentes(cell.get('components', []))
            elif tipo in ['datagrid', 'editgrid']:
                campos.append({
                    'key': comp.get('key'),
                    'label': comp.get('label', comp.get('key')),
                    'type': tipo
                })
                procesar_componentes(comp.get('components', []))
            elif tipo in ['content', 'htmlelement', 'button']:
                continue
            else:
                if comp.get('input'):
                    campos.append({
                        'key': comp.get('key'),
                        'label': comp.get('label', comp.get('key')),
                        'type': tipo
                    })

    procesar_componentes(schema.get('components', []))
    return campos


def crear_campos_definidos_desde_schema(formulario, schema):
    admin_group = Group.objects.filter(name='Desarrollador').first()
    campos_extraidos = extraer_componentes(schema)

    for campo in campos_extraidos:
        clave = campo['key']
        etiqueta = campo['label']
        tipo_original = campo['type']
        tipo_logico = formio_type_to_logical_type.get(tipo_original, 'text')

        if tipo_logico is None:
            continue  # omitir campos decorativos o irrelevantes

        campo_def, creado = CampoDefinido.objects.get_or_create(
            formulario=formulario,
            clave=clave,
            defaults={
                'etiqueta': etiqueta,
                'tipo': tipo_logico,
                'tipo_original': tipo_original
            }
        )

        if creado and admin_group:
            campo_def.visible_para.add(admin_group)

    """
    Crea los campos definidos en el formulario a partir de un schema Formio.
    Los campos se crean con el grupo 'Desarrollador' como visible por defecto.
    Si el campo ya existe, no se crea nuevamente.
    """

    admin_group = Group.objects.filter(name='Desarrollador').first()
    campos_extraidos = extraer_componentes(schema)

    for campo in campos_extraidos:
        clave = campo['key']
        etiqueta = campo['label']
        tipo = campo['type']

        campo_def, creado = CampoDefinido.objects.get_or_create(
            formulario=formulario,
            clave=clave,
            defaults={
                'etiqueta': etiqueta,
                'tipo': tipo
            }
        )

        if creado and admin_group:
            campo_def.visible_para.add(admin_group)


def sincronizar_campos_definidos(formulario, schema):
    campos_schema = extraer_componentes(schema)
    claves_nuevas = [c['key'] for c in campos_schema]

    # Campos actuales
    campos_actuales = CampoDefinido.objects.filter(formulario=formulario)
    campos_dict = {c.clave: c for c in campos_actuales}

    admin_group = Group.objects.filter(name='Desarrollador').first()

    for campo_nuevo in campos_schema:
        clave = campo_nuevo['key']
        etiqueta = campo_nuevo['label']
        tipo_original = campo_nuevo['type']
        tipo_logico = formio_type_to_logical_type.get(tipo_original, 'text')

        if tipo_logico is None:
            continue

        if clave in campos_dict:
            campo = campos_dict[clave]
            campo.etiqueta = etiqueta
            campo.tipo = tipo_logico
            campo.tipo_original = tipo_original
            campo.activo = True
            campo.save()
        else:
            nuevo = CampoDefinido.objects.create(
                formulario=formulario,
                clave=clave,
                etiqueta=etiqueta,
                tipo=tipo_logico,
                tipo_original=tipo_original,
                activo=True
            )
            if admin_group:
                nuevo.visible_para.add(admin_group)

    # Marcar campos eliminados como inactivos
    for clave, campo in campos_dict.items():
        if clave not in claves_nuevas and campo.activo:
            campo.activo = False
            campo.save()


def guardar_o_actualizar_campos_respuesta(respuesta, respuestas):
    campos_definidos = CampoDefinido.objects.filter(formulario=respuesta.encuesta.formulario)
    campos_dict = {c.clave: c for c in campos_definidos}
    claves_definidas = set(campos_dict.keys())

    campos_existentes = {
        c.clave: c for c in respuesta.campos.all()
    }

    errores = {}

    for clave, valor in respuestas.items():
        # Omitir campos no definidos y botones
        if clave not in claves_definidas:
            continue

        valor_str = json.dumps(valor) if isinstance(valor, (dict, list)) else str(valor).strip()
        campo_definido = campos_dict[clave]

        # Si el campo ya existe, lo usamos; si no, lo creamos
        campo = campos_existentes.get(clave, CampoRespuesta(respuesta=respuesta, clave=clave))
        campo.valor = valor_str

        # Limpiar campos tipo
        campo.valor_numerico = None
        campo.valor_fecha = None
        campo.valor_booleano = None
        campo.valor_lista = None

        tipo = campo_definido.tipo

        try:
            if tipo == 'number':
                campo.valor_numerico = float(valor_str.replace(",", "."))

            elif tipo == 'date':
                campo.valor_fecha = datetime.strptime(valor_str, "%Y-%m-%d").date()

            elif tipo == 'time':
                t = datetime.strptime(valor_str, "%H:%M:%S").time()
                campo.valor_numerico = t.hour * 3600 + t.minute * 60 + t.second

            elif tipo == 'boolean':
                if valor_str.lower() in ['true', '1', 'sí', 'si']:
                    campo.valor_booleano = True
                elif valor_str.lower() in ['false', '0', 'no']:
                    campo.valor_booleano = False
                else:
                    raise ValueError("Valor booleano inválido")

            elif tipo in ['multi_select', 'selectboxes', 'checkboxes']:
                if isinstance(valor, list):
                    campo.valor_lista = valor
                else:
                    campo.valor_lista = [valor]

            # Guardar finalmente
            campo.save()

        except Exception as e:
            errores[clave] = f"Error en tipo {tipo}: {str(e)}"

    return errores


def normalizar_json(schema):
    """
    Normaliza el JSON para comparar su contenido sin importar el orden.
    """
    return json.dumps(schema, sort_keys=True, separators=(',', ':'))