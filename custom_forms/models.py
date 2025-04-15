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

        # Última versión
        ultima = FormularioVersion.objects.filter(formulario=self).order_by('-numero').first()
        schema_ultimo = normalizar_json(ultima.json) if ultima else None

        if schema_actual == schema_ultimo:
            return False  # No se ha modificado el schema

        # Verificar si existen respuestas con la versión actual
        tiene_respuestas = RespuestaEncuesta.objects.filter(
            encuesta__formulario=self,
            version=self.version
        ).exists()

        if not tiene_respuestas:
            if ultima:
                ultima.json = self.json
                ultima.save()
            return False  # no se creó nueva versión, solo se actualizó la última

        # Si sí hay respuestas, entonces crear una nueva versión
        nueva_version = self.version + 1
        FormularioVersion.objects.create(
            formulario=self,
            numero=nueva_version,
            json=self.json
        )
        self.version = nueva_version
        self.save(update_fields=['version'])
        return True

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
    visible_para = models.ManyToManyField(Group, blank=True)  # aquí el cambio
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
    valor = models.TextField() # Valor original como texto/JSON
    
    valor_numerico = models.FloatField(null=True, blank=True)
    valor_fecha = models.DateField(null=True, blank=True)
    valor_booleano = models.BooleanField(null=True, blank=True)
    valor_lista = models.JSONField(null=True, blank=True)  # Para select múltiple