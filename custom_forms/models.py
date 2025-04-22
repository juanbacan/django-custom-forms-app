import json

from django.db import models
from django.contrib.auth.models import Group

from core.models import CustomUser, ModeloBase
from django.db import models


class Formulario(ModeloBase):
    nombre = models.CharField(max_length=1024)
    json = models.JSONField()
    fecha = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.nombre

    def generar_modelo_django(self):
        from .utils import camel_to_snake

        campos = CampoDefinido.objects.filter(formulario=self, activo=True)
        model_name = f"Formulario{self.pk:04}"

        tipo_map = {
            "text":         "models.CharField(max_length=1024)",
            "number":       "models.FloatField()",
            "date":         "models.DateField()",
            "time":         "models.TimeField()",
            "datetime":     "models.DateTimeField()",
            "boolean":      "models.BooleanField()",
            "multi_select": "models.JSONField()",
            "datagrid":     "models.JSONField()",
        }

        lines = [
            "from django.db import models",
            "",
            f"class {model_name}(models.Model):"
        ]

        for campo in campos:
            name     = camel_to_snake(campo.clave)
            label    = campo.etiqueta.replace("'", "\\'")
            required = campo.validate.get("required", False) and not campo.conditional

            # blank/null si NO es requerido
            null_blank = ""
            if not required:
                if campo.tipo in ("number", "date", "time", "datetime"):
                    null_blank = ", null=True, blank=True"
                else:
                    null_blank = ", blank=True"

            if campo.values:
                # genera choice
                const = f"{name.upper()}_CHOICES"
                # asumimos que la constante ya existe en el mismo archivo
                field = (
                    f"models.CharField(max_length=1024, "
                    f"choices={const}, "
                    f"verbose_name='{label}'{null_blank})"
                )
            else:
                # Usa TextField si el tipo original indica área de texto
                if campo.tipo_original == "textfield":
                    td = tipo_map.get(campo.tipo, "models.TextField()")
                else:
                    td = "models.TextField()"
                if td.endswith("()"):
                    # ej: FloatField()
                    base = td[:-2]
                    field = f"{base}(verbose_name='{label}'{null_blank})"
                else:
                    # ej: CharField(max_length=1024)
                    base = td[:-1]
                    field = f"{base}, verbose_name='{label}'{null_blank})"

            lines.append(f"    {name} = {field}")

        return "\n".join(lines)

    def campos_tabla(self):
        """
        Devuelve una lista de los campos que deben mostrarse en la tabla de respuestas.
        """
        return CampoDefinido.objects.filter(formulario=self, table_view=True, activo=True)

    def save(self, *args, **kwargs):
        from .utils import sincronizar_campos_definidos
        super().save(*args, **kwargs)
        sincronizar_campos_definidos(self, self.json)

class FormularioVersion(ModeloBase):
    formulario = models.ForeignKey('Formulario', on_delete=models.CASCADE, related_name='versiones')
    numero = models.PositiveIntegerField()
    json = models.JSONField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('formulario', 'numero')
        ordering = ['-numero']

    def __str__(self):
        return f"{self.formulario.nombre} - v{self.numero}"
    
class CampoDefinido(ModeloBase):
    formulario = models.ForeignKey(Formulario, on_delete=models.CASCADE)
    clave = models.CharField(max_length=100)
    etiqueta = models.CharField(max_length=1024)
    tipo = models.CharField(max_length=20)  # text, number, date, time, etc.
    tipo_original = models.CharField(max_length=50)
    values = models.JSONField(null=True, blank=True)
    validate = models.JSONField(null=True, blank=True)
    conditional = models.JSONField(null=True, blank=True)
    validate_when_hidden = models.BooleanField(default=False)
    default_value = models.CharField(null=True, blank=True, max_length=1024)
    table_view = models.BooleanField(default=False)
    visible_para = models.ManyToManyField(Group, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.etiqueta} ({self.clave})"


class Encuesta(ModeloBase):
    formulario = models.ForeignKey(Formulario, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=1024)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    creada_por = models.ForeignKey(CustomUser, null=True, on_delete=models.SET_NULL)
    creada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class RespuestaEncuesta(ModeloBase):
    encuesta = models.ForeignKey(Encuesta, on_delete=models.CASCADE)
    usuario = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    version = models.PositiveIntegerField()
    enviado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Respuesta de {self.usuario}"


class CampoRespuesta(ModeloBase):
    respuesta = models.ForeignKey(RespuestaEncuesta, on_delete=models.CASCADE, related_name='campos')
    campo_definido = models.ForeignKey(CampoDefinido, on_delete=models.CASCADE)

    clave = models.CharField(max_length=100)
    etiqueta = models.CharField(max_length=1024, blank=True)
    valor = models.TextField() # Valor original como texto/JSON
    
    valor_numerico = models.FloatField(null=True, blank=True)
    valor_fecha = models.DateField(null=True, blank=True)
    valor_time = models.TimeField(null=True, blank=True)
    valor_datetime = models.DateTimeField(null=True, blank=True)
    valor_booleano = models.BooleanField(null=True, blank=True)
    valor_lista = models.JSONField(null=True, blank=True)  # Para select múltiple



