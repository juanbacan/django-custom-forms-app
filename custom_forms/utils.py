import json, re

from django.contrib.auth.models import Group
from datetime import datetime

from .models import CampoDefinido, CampoRespuesta, RespuestaEncuesta

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
    # Layouts y decorativos se omiten en el procesamiento
    "button": None,
    "content": None,
    "htmlelement": None,
    "panel": None,
    "well": None,
    "columns": None,
    "fieldset": None,
    "tabs": None,
    "container": None,
}

def extraer_componentes(schema):
    """
    Recorre recursivamente el schema Formio y extrae todos los componentes 'input' útiles,
    devolviendo lista de diccionarios con key, label, type, opciones (si aplica) y required.
    """
    campos = []

    def procesar_componentes(componentes):
        for comp in componentes:
            tipo = comp.get('type')

            # Layouts y contenedores
            if tipo in ['panel', 'well', 'columns', 'fieldset', 'tabs', 'container']:
                if tipo == 'tabs':
                    for tab in comp.get('components', []):
                        procesar_componentes(tab.get('components', []))
                elif tipo == 'columns':
                    for col in comp.get('columns', []):
                        procesar_componentes(col.get('components', []))
                else:
                    procesar_componentes(comp.get('components', []))
                continue

            # Tabla
            if tipo == 'table':
                for row in comp.get('rows', []):
                    for cell in row:
                        procesar_componentes(cell.get('components', []))
                continue

            # Rejillas de datos
            if tipo in ['datagrid', 'editgrid']:
                values = comp.get('values') or comp.get('data', {}).get('values', [])
                validate  = comp.get('validate', {})
                validate_when_hidden = comp.get('validateWhenHidden', False)
                conditional = comp.get('conditional', {})
                default_value = comp.get('defaultValue', None)
                campos.append({
                    'key': comp.get('key'),
                    'label': comp.get('label', comp.get('key')),
                    'type': tipo,
                    'values': values,
                    'validate': validate,
                    'validate_when_hidden': validate_when_hidden,
                    'conditional': conditional,
                    'defaultValue': default_value,
                })
                procesar_componentes(comp.get('components', []))
                continue

            # Elementos no input (decorativos, botones)
            if tipo in ['content', 'htmlelement', 'button']:
                continue

            # Componentes con input
            if comp.get('input'):
                values = comp.get('values') or comp.get('data', {}).get('values', [])
                validate  = comp.get('validate', {})
                validate_when_hidden = comp.get('validateWhenHidden', False)
                conditional = comp.get('conditional', {})
                default_value = comp.get('defaultValue', None)

                campos.append({
                    'key': comp.get('key'),
                    'label': comp.get('label', comp.get('key')),
                    'type': tipo,
                    'values': values,
                    'validate': validate,
                    'validateWhenHidden': validate_when_hidden,
                    'conditional': conditional,
                    'defaultValue': default_value,
                })

    procesar_componentes(schema.get('components', []))
    return campos


def sincronizar_campos_definidos(formulario, schema):
    """
    Sincroniza los CampoDefinido de un formulario a partir del schema Formio:
    - Crea nuevos campos si no existen.
    - Actualiza campos existentes (etiqueta, tipo, values, validate y activo).
    - Marca como inactivos los campos eliminados del schema.
    """
    admin_group = Group.objects.filter(name='Desarrollador').first()
    componentes = extraer_componentes(schema)
    claves_nuevas = {comp['key'] for comp in componentes}

    # Cargar campos actuales
    actuales = {c.clave: c for c in CampoDefinido.objects.filter(formulario=formulario)}

    for comp in componentes:
        clave = comp['key']
        etiqueta = comp['label']
        tipo_orig = comp['type']
        tipo_log = formio_type_to_logical_type.get(tipo_orig)
        # Omitir layouts/elementos no mapeables
        if not tipo_log:
            continue

        # Extraer valores y validación
        values = comp.get('values') or comp.get('data', {}).get('values', [])
        validate = comp.get('validate', {})
        validate_when_hidden = comp.get('validateWhenHidden', False)
        conditional = comp.get('conditional', {})
        default_value = comp.get('defaultValue', None)

        if clave in actuales:
            campo = actuales[clave]
            campo.etiqueta              = etiqueta
            campo.tipo                  = tipo_log
            campo.tipo_original         = tipo_orig
            campo.values                = values
            campo.validate              = validate
            campo.validate_when_hidden  = validate_when_hidden
            campo.conditional           = conditional
            campo.default_value         = default_value
            campo.activo                = True
            campo.save()
        else:
            nuevo = CampoDefinido.objects.create(
                formulario=formulario,
                clave=clave,
                etiqueta=etiqueta,
                tipo=tipo_log,
                tipo_original=tipo_orig,
                values=values,
                validate=validate,
                validate_when_hidden=validate_when_hidden,
                conditional=conditional,
                default_value=default_value,
                activo=True
            )
            if admin_group:
                nuevo.visible_para.add(admin_group)

    # Marcar campos eliminados como inactivos
    for clave, campo in actuales.items():
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
        campo.etiqueta = campo_definido.etiqueta

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
                try:
                    campo.valor_fecha = datetime.strptime(valor_str[:10], "%Y-%m-%d").date()
                except ValueError:
                    campo.valor_fecha = datetime.strptime(valor_str[:10], "%m/%d/%Y").date()

            elif tipo == 'time':
                t = datetime.strptime(valor_str[:8], "%H:%M:%S").time()
                campo.valor_time = t
                campo.valor_numerico = t.hour * 3600 + t.minute * 60 + t.second

            elif tipo == 'datetime':
                campo.valor_datetime = datetime.fromisoformat(valor_str)

            elif tipo == 'boolean':
                if isinstance(valor, bool):
                    campo.valor_booleano = valor
                elif isinstance(valor_str, str):
                    if valor_str.lower() in ['true', '1', 'sí', 'si']:
                        campo.valor_booleano = True
                    elif valor_str.lower() in ['false', '0', 'no']:
                        campo.valor_booleano = False
                    else:
                        raise ValueError(f"Valor booleano inválido: {valor_str}")

            elif tipo in ['multi_select', 'selectboxes', 'checkboxes']:
                if isinstance(valor, list):
                    campo.valor_lista = valor
                else:
                    campo.valor_lista = [valor]

            campo.save()

        except Exception as e:
            errores[clave] = f"Error en tipo {tipo}: {str(e)}"

    return errores


def normalizar_json(schema):
    """
    Normaliza el JSON para comparar su contenido sin importar el orden.
    """
    return json.dumps(schema, sort_keys=True, separators=(',', ':'))


def camel_to_snake(name: str) -> str:
    """
    Convierte CamelCase o PascalCase a snake_case.
    """

    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()


def actualizar_etiquetas_respuestas(formulario):
    """
    Recorre todas las respuestas del formulario y actualiza las etiquetas (y claves si deseas)
    en los campos de respuesta según la definición actual de CampoDefinido.
    """
    campos_definidos = CampoDefinido.objects.filter(formulario=formulario)
    campos_dict = {c.clave: c.etiqueta for c in campos_definidos}

    respuestas = RespuestaEncuesta.objects.filter(encuesta__formulario=formulario).prefetch_related('campos')

    for respuesta in respuestas:
        for campo in respuesta.campos.all():
            nueva_etiqueta = campos_dict.get(campo.clave)
            if nueva_etiqueta and campo.etiqueta != nueva_etiqueta:
                campo.etiqueta = nueva_etiqueta
                campo.save()



def guardar_respuesta_en_modelo_desde_respuesta(
    respuesta_obj,
    modelo_class,
    instancia=None,
    extras=None
):
    """
    Toma una RespuestaEncuesta y vuelca sus CampoRespuesta en una instancia
    de modelo_class, mapeando CamelCase->snake_case automáticamente.
    """
    obj = instancia or modelo_class()
    if extras:
        for k, v in extras.items():
            setattr(obj, k, v)

    # Prepara mapa de fields del modelo destino
    fields = {
        f.name: f
        for f in modelo_class._meta.get_fields()
        if isinstance(f, models.Field)
    }

    for campo_resp in respuesta_obj.campos.all():
        raw_key = campo_resp.clave  # ej. "TipoDeDispositivoMedicoDeUsoHumano"
        attr = camel_to_snake(raw_key)  # => "tipo_de_dispositivo_medico_de_uso_humano"
        if attr not in fields:
            continue

        field = fields[attr]
        # Escoge el valor tipado
        if campo_resp.valor_datetime is not None:
            valor = campo_resp.valor_datetime
        elif campo_resp.valor_fecha is not None:
            valor = campo_resp.valor_fecha
        elif campo_resp.valor_time is not None:
            valor = campo_resp.valor_time
        elif campo_resp.valor_numerico is not None:
            valor = campo_resp.valor_numerico
        elif campo_resp.valor_booleano is not None:
            valor = campo_resp.valor_booleano
        elif campo_resp.valor_lista not in (None, []):
            valor = campo_resp.valor_lista
        else:
            try:
                valor = json.loads(campo_resp.valor)
            except Exception:
                valor = campo_resp.valor

        # Asigna directamente (tipos ya correctos)
        setattr(obj, attr, valor)

    obj.save()
    return obj