import json, re

from django.contrib.auth.models import Group
from django.db import models
from django.core.exceptions import ValidationError

from datetime import datetime

from .models import CampoDefinido, CampoRespuesta, RespuestaEncuesta, FormularioVersion

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

    "datagrid": "datagrid",
    "editgrid": "datagrid", 
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

            if tipo in ['datagrid', 'editgrid']:
                subfields = []
                for subcomp in comp.get('components', []):
                    subfields.append({
                        'key': subcomp.get('key'),
                        'label': subcomp.get('label', subcomp.get('key')),
                        'type': subcomp.get('type'),
                        'validate': subcomp.get('validate', {}),
                        'defaultValue': subcomp.get('defaultValue'),
                    })

                campos.append({
                    'key': comp.get('key'),
                    'label': comp.get('label', comp.get('key')),
                    'type': tipo,
                    'values': subfields,  # Aquí se guarda la estructura interna
                    'validate': comp.get('validate', {}),
                    'validateWhenHidden': comp.get('validateWhenHidden', False),
                    'conditional': comp.get('conditional', {}),
                    'defaultValue': comp.get('defaultValue', None),
                })
                continue

            # # Rejillas de datos
            # if tipo in ['datagrid', 'editgrid']:
            #     values = comp.get('values') or comp.get('data', {}).get('values', [])
            #     validate  = comp.get('validate', {})
            #     validate_when_hidden = comp.get('validateWhenHidden', False)
            #     conditional = comp.get('conditional', {})
            #     default_value = comp.get('defaultValue', None)
            #     campos.append({
            #         'key': comp.get('key'),
            #         'label': comp.get('label', comp.get('key')),
            #         'type': tipo,
            #         'values': values,
            #         'validate': validate,
            #         'validate_when_hidden': validate_when_hidden,
            #         'conditional': conditional,
            #         'defaultValue': default_value,
            #     })
            #     procesar_componentes(comp.get('components', []))
            #     continue

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

    campos_existentes = {c.clave: c for c in respuesta.campos.all()}
    errores = {}

    for clave, valor in respuestas.items():
        # Ignorar campos no definidos y botones/form.io internos
        if clave not in claves_definidas:
            continue

        campo_definido = campos_dict[clave]

        # Procesamiento seguro de valor_str
        if isinstance(valor, (dict, list)):
            valor_str = json.dumps(valor)
        elif isinstance(valor, str):
            valor_str = valor.strip()
        else:
            valor_str = str(valor)

        campo = campos_existentes.get(clave, CampoRespuesta(respuesta=respuesta, clave=clave))
        campo.valor = valor_str
        campo.etiqueta = campo_definido.etiqueta

        # Reset de valores tipados
        campo.valor_numerico = None
        campo.valor_fecha = None
        campo.valor_time = None
        campo.valor_datetime = None
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
                elif isinstance(valor, str) and ',' in valor:
                    campo.valor_lista = [v.strip() for v in valor.split(',')]
                else:
                    campo.valor_lista = [valor]

            campo.save()

        except Exception as e:
            errores[clave] = f"Error en tipo {tipo} con valor '{valor}': {str(e)}"

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
    Recorre todas las respuestas del formulario y actualiza las etiquetas y claves
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



def condicion_cumplida(campo_definido, campos_respuesta):
    cond = campo_definido.conditional
    if not cond or not isinstance(cond, dict):
        return True  # Si no hay condición, el campo es visible

    when = cond.get("when")
    eq = cond.get("eq")
    neq = cond.get("neq")
    show = cond.get("show", True)

    campo_referencia = campos_respuesta.get(when)
    if not campo_referencia:
        return not show  # Si no se respondió el campo base, asumimos lo contrario a show

    # Normalizamos el valor del campo de referencia
    valor = (
        campo_referencia.valor_booleano if campo_referencia.valor_booleano is not None
        else campo_referencia.valor
    )
    valor_str = str(valor).strip().lower()

    # Evaluación de igualdad
    cumple_eq = True
    if eq is not None:
        if isinstance(eq, list):
            comparadores = [str(e).strip().lower() for e in eq]
            cumple_eq = valor_str in comparadores
        else:
            cumple_eq = valor_str == str(eq).strip().lower()

    # Evaluación de desigualdad
    cumple_neq = True
    if neq is not None:
        if isinstance(neq, list):
            comparadores = [str(e).strip().lower() for e in neq]
            cumple_neq = valor_str not in comparadores
        else:
            cumple_neq = valor_str != str(neq).strip().lower()

    cumple = cumple_eq and cumple_neq

    return cumple if show else not cumple


def es_valor_vacio(valor):
    if isinstance(valor, str):
        valor = valor.strip().lower()
    return valor in [None, '', 'null']


def validar_campos_requeridos(campos_definidos, campos_respuesta):
    """
    Retorna una lista de etiquetas de campos requeridos que están vacíos
    y cuya condición (conditional) se cumple.
    """
    faltantes = []

    for campo_def in campos_definidos:
        if not campo_def.validate.get("required", False):
            continue  # No es requerido

        if not condicion_cumplida(campo_def, campos_respuesta):
            continue  # No se muestra, no se valida

        campo_resp = campos_respuesta.get(campo_def.clave)
        if not campo_resp or es_valor_vacio(campo_resp.valor):
            faltantes.append(campo_def.etiqueta)

    return faltantes


def validar_datagrid(campo_definido, campo_respuesta):
    """
    Valida cada fila del datagrid según los subcampos definidos en `values`.
    Devuelve una lista de mensajes de error si faltan campos requeridos.
    """
    errores = []
    columnas = campo_definido.values or []
    filas = campo_respuesta.valor_lista or []

    for i, fila in enumerate(filas):
        for col in columnas:
            if col.get('validate', {}).get('required'):
                key = col['key']
                label = col.get('label', key)
                valor = fila.get(key)

                if es_valor_vacio(valor):
                    errores.append(
                        f"Fila {i + 1} de '{campo_definido.etiqueta}': falta el campo obligatorio '{label}'"
                    )
    return errores


def validar_campos_requeridos(campos_definidos, campos_respuesta):
    """
    Retorna una lista de mensajes de error por campos requeridos no respondidos,
    incluyendo datagrids.
    """
    faltantes = []

    for campo_def in campos_definidos:
        if not campo_def.validate.get("required", False):
            continue  # No es requerido

        if not condicion_cumplida(campo_def, campos_respuesta):
            continue  # No se muestra, no se valida

        campo_resp = campos_respuesta.get(campo_def.clave)

        if campo_def.tipo == 'datagrid':
            if not campo_resp:
                faltantes.append(f"'{campo_def.etiqueta}' no fue respondido")
                continue
            faltantes.extend(validar_datagrid(campo_def, campo_resp))
            continue

        if not campo_resp or es_valor_vacio(campo_resp.valor):
            faltantes.append(f"Campo obligatorio no respondido: '{campo_def.etiqueta}'")

    return faltantes


def guardar_respuesta_en_modelo_desde_respuesta(
    respuesta_obj,
    modelo_class,
    instancia=None,
    extras=None,
    validar=False
):
    campos_respuesta = {c.clave: c for c in respuesta_obj.campos.all()}
    campos_definidos = CampoDefinido.objects.filter(formulario=respuesta_obj.encuesta.formulario, activo=True)

    campos_condicionales_visibles_no_respondidos = []

    crear_modelo = False
    for campo_def in campos_definidos:
        if condicion_cumplida(campo_def, campos_respuesta):
            campo_resp = campos_respuesta.get(campo_def.clave)
            if campo_resp and not es_valor_vacio(campo_resp.valor):
                crear_modelo = True
                break
            else:
                campos_condicionales_visibles_no_respondidos.append(campo_def.etiqueta)

    if not crear_modelo:
        mensaje = (
            "No se puede guardar el modelo porque ningún campo relevante fue respondido. "
            "Se esperaban respuestas en: " +
            ", ".join(campos_condicionales_visibles_no_respondidos)
        )
        raise ValueError(mensaje)

    # Validación de campos requeridos condicionales
    campos_faltantes = validar_campos_requeridos(campos_definidos, campos_respuesta)
    if campos_faltantes:
        raise ValueError("No se puede guardar el modelo porque faltan campos obligatorios: " + ", ".join(campos_faltantes))

    # Crear o usar instancia del modelo
    obj = instancia or modelo_class()

    if extras:
        for k, v in extras.items():
            setattr(obj, k, v)

    fields = {
        f.name: f
        for f in modelo_class._meta.get_fields()
        if isinstance(f, models.Field) and not f.auto_created
    }

    for campo_resp in respuesta_obj.campos.all():
        raw_key = campo_resp.clave
        attr = camel_to_snake(raw_key)

        if attr not in fields:
            continue

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

        try:
            setattr(obj, attr, valor)
        except (ValueError, TypeError):
            continue

    if validar:
        try:
            obj.full_clean()
        except ValidationError as e:
            raise ValueError(f"Error al validar el modelo: {e.message_dict}")

    obj.save()
    return obj



def actualizar_formulario_y_guardar_version(formulario, nuevo_json: dict) -> bool:
    """
    Actualiza el JSON de un formulario y guarda una nueva versión
    solo si ya existen respuestas y el esquema cambió.
    Retorna True si se creó una nueva versión, False si no fue necesario.
    """
    from .utils import normalizar_json

    schema_nuevo = normalizar_json(nuevo_json)
    schema_actual = normalizar_json(formulario.json)

    # Si no hay cambios en el JSON, no hacemos nada
    if schema_nuevo == schema_actual:
        return False

    # Guardamos el nuevo JSON
    formulario.json = nuevo_json
    formulario.save()

    ultima = FormularioVersion.objects.filter(formulario=formulario).order_by('-numero').first()
    schema_ultimo = normalizar_json(ultima.json) if ultima else None

    # Si es igual al último esquema guardado, no hace falta crear una nueva versión
    if schema_nuevo == schema_ultimo:
        return False

    # Verifica si existen respuestas que ya usan la versión actual
    tiene_respuestas = RespuestaEncuesta.objects.filter(
        encuesta__formulario=formulario,
        version=formulario.version
    ).exists()

    if not tiene_respuestas:
        # Solo actualiza la última versión
        if ultima:
            ultima.json = nuevo_json
            ultima.save()
        return False

    # Si hay respuestas, crea una nueva versión
    nueva_version = formulario.version + 1
    FormularioVersion.objects.create(
        formulario=formulario,
        numero=nueva_version,
        json=nuevo_json
    )
    formulario.version = nueva_version
    formulario.save(update_fields=['version'])
    return True

