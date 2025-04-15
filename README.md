# django-formbuilder

**Sistema completo para la construcción, edición, versionado y gestión de formularios dinámicos en Django, con soporte visual basado en Formio.js.**

---

## 🚀 Características

- Constructor visual drag-and-drop usando [Formio.js](https://formio.github.io/formio.js/)
- Soporte para múltiples tipos de campos, incluyendo fechas, archivos, firmas y select múltiples
- Guarda las respuestas como clave-valor con tipado automático (`fecha`, `booleano`, `numérico`, etc.)
- Control de visibilidad de campos por grupos (`ManyToManyField` a `auth.Group`)
- Soporte para versionado automático de formularios
- Comparación inteligente del schema con `normalizar_json`
- Visualización editable o solo lectura de formularios renderizados con Formio

---

## 🛠️ Requisitos

- Python 3.8+
- Django 3.2+
- Formio.js (se incluye desde CDN en los templates)
- Bootstrap (opcional para estilos)

---

## 📦 Instalación

```bash
pip install django-formbuilder
```

Agrega a `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'formbuilder',
]
```

Aplica las migraciones:

```bash
python manage.py migrate
```

---

## 📋 Modelos principales

### `Formulario`
Modelo base que almacena el JSON del formulario (estructura generada con Formio).

### `CampoDefinido`
Campos definidos a partir del esquema de Formio, normalizados a un tipo lógico (`number`, `boolean`, etc.). Controla visibilidad por grupo (`visible_para`).

### `Encuesta`
Relación de un formulario con una instancia de aplicación (puede usarse varias veces).

### `RespuestaEncuesta`
Almacena una respuesta a una encuesta con versión, usuario y fecha.

### `CampoRespuesta`
Cada entrada (clave/valor) respondida, con campos automáticos para:
- `valor_numerico`
- `valor_fecha`
- `valor_booleano`
- `valor_lista`

---

## 🧠 Utilidades

### `extraer_componentes(schema)`
Extrae los campos input válidos desde el JSON Formio, incluyendo soporte para `tabs`, `panels`, `tables`, `columns`, etc.

### `crear_campos_definidos_desde_schema(formulario, schema)`
Extrae los campos del schema y los guarda como `CampoDefinido`, visibles para el grupo "Desarrollador".

### `sincronizar_campos_definidos(formulario, schema)`
Actualiza etiquetas, tipos, y marca como inactivos los campos eliminados del esquema.

### `guardar_o_actualizar_campos_respuesta(respuesta, respuestas)`
Guarda o actualiza los valores respondidos por un usuario, con interpretación automática de tipos.

### `normalizar_json(schema)`
Convierte un schema a string ordenado (útil para comparación y detección de cambios).

---

## 🖼️ Renderización del formulario

```javascript
Formio.createForm(document.getElementById('form-render'), schema).then(form => {
    form.setSubmission({ data: respuestas });

    form.on('submit', function(submission) {
        // Puedes enviarlo por POST tradicional o AJAX
        const data = submission.data;
        ...
    });
});
```

---

## 🧪 Ejemplo de test

```python
from formbuilder.utils import guardar_o_actualizar_campos_respuesta

def test_guardado_numerico():
    errores = guardar_o_actualizar_campos_respuesta(respuesta, {"edad": 25})
    assert errores == {}
    assert respuesta.campos.get(clave="edad").valor_numerico == 25.0
```

---

## 📄 Licencia

MIT

---

## ✨ Autor

Desarrollado por [juanbacan]

---