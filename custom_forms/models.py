import json

from django.db import models
from django.contrib.auth.models import Group

from core.models import CustomUser
from django.db import models


class Formulario(models.Model):
    nombre = models.CharField(max_length=255)
    json = models.JSONField()
    fecha = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.nombre


    def guardar_nueva_version(self):
        from .utils import normalizar_json

        schema_actual = normalizar_json(self.json)

        ultima = FormularioVersion.objects.filter(formulario=self).order_by('-numero').first()
        schema_ultimo = normalizar_json(ultima.json) if ultima else None

        if schema_actual == schema_ultimo:
            return False

        tiene_respuestas = RespuestaEncuesta.objects.filter(
            encuesta__formulario=self,
            version=self.version
        ).exists()

        if not tiene_respuestas:
            if ultima:
                ultima.json = self.json
                ultima.save()
            return False

        nueva_version = self.version + 1
        FormularioVersion.objects.create(
            formulario=self,
            numero=nueva_version,
            json=self.json
        )
        self.version = nueva_version
        # ⛔ aquí evitas volver a llamar save con sincronización
        self.save(update_fields=['version'], sync_labels=False)
        return True

    def generar_modelo_django(self):
        from .utils import camel_to_snake

        campos = CampoDefinido.objects.filter(formulario=self, activo=True)
        model_name = f"Formulario{self.pk:04}"

        tipo_map = {
            "text":         "models.CharField(max_length=255)",
            "number":       "models.FloatField()",
            "date":         "models.DateField()",
            "time":         "models.TimeField()",
            "datetime":     "models.DateTimeField()",
            "boolean":      "models.BooleanField()",
            "multi_select": "models.JSONField()",
        }

        lines = [
            "from django.db import models",
            "",
            f"class {model_name}(models.Model):"
        ]

        for campo in campos:
            name     = camel_to_snake(campo.clave)
            label    = campo.etiqueta.replace("'", "\\'")
            required = bool(campo.validate.get("required", False))

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
                    f"models.CharField(max_length=255, "
                    f"choices={const}, "
                    f"verbose_name='{label}'{null_blank})"
                )
            else:
                td = tipo_map.get(campo.tipo, "models.TextField()")
                if td.endswith("()"):
                    # ej: FloatField()
                    base = td[:-2]
                    field = f"{base}(verbose_name='{label}'{null_blank})"
                else:
                    # ej: CharField(max_length=255)
                    base = td[:-1]
                    field = f"{base}, verbose_name='{label}'{null_blank})"

            lines.append(f"    {name} = {field}")

        return "\n".join(lines)



    def save(self, *args, **kwargs):
        from .utils import normalizar_json, sincronizar_campos_definidos, actualizar_etiquetas_respuestas
        is_new = self.pk is None

        json_original = None
        if not is_new:
            json_original = normalizar_json(Formulario.objects.get(pk=self.pk).json)

        super().save(*args, **kwargs)

        # Evitar sincronización si no hay cambios
        json_nuevo = normalizar_json(self.json)
        if json_nuevo == json_original:
            return

        # El schema cambió, sincronizamos campos y respuestas:
        sincronizar_campos_definidos(self, self.json)
        actualizar_etiquetas_respuestas(self)


class FormularioVersion(models.Model):
    formulario = models.ForeignKey('Formulario', on_delete=models.CASCADE, related_name='versiones')
    numero = models.PositiveIntegerField()
    json = models.JSONField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('formulario', 'numero')
        ordering = ['-numero']

    def __str__(self):
        return f"{self.formulario.nombre} - v{self.numero}"
    
class CampoDefinido(models.Model):
    formulario = models.ForeignKey(Formulario, on_delete=models.CASCADE)
    clave = models.CharField(max_length=100)
    etiqueta = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20)  # text, number, date, time, etc.
    tipo_original = models.CharField(max_length=50)
    values = models.JSONField(null=True, blank=True)
    validate = models.JSONField(null=True, blank=True)
    conditional = models.JSONField(null=True, blank=True)
    validate_when_hidden = models.BooleanField(default=False)
    default_value = models.CharField(null=True, blank=True, max_length=255)
    visible_para = models.ManyToManyField(Group, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.etiqueta} ({self.clave})"


class Encuesta(models.Model):
    formulario = models.ForeignKey(Formulario, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    creada_por = models.ForeignKey(CustomUser, null=True, on_delete=models.SET_NULL)
    creada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class RespuestaEncuesta(models.Model):
    encuesta = models.ForeignKey(Encuesta, on_delete=models.CASCADE)
    usuario = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    version = models.PositiveIntegerField()
    enviado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Respuesta de {self.usuario}"


class CampoRespuesta(models.Model):
    respuesta = models.ForeignKey(RespuestaEncuesta, on_delete=models.CASCADE, related_name='campos')
    clave = models.CharField(max_length=100)
    etiqueta = models.CharField(max_length=255, blank=True)
    valor = models.TextField() # Valor original como texto/JSON
    
    valor_numerico = models.FloatField(null=True, blank=True)
    valor_fecha = models.DateField(null=True, blank=True)
    valor_time = models.TimeField(null=True, blank=True)
    valor_datetime = models.DateTimeField(null=True, blank=True)
    valor_booleano = models.BooleanField(null=True, blank=True)
    valor_lista = models.JSONField(null=True, blank=True)  # Para select múltiple



