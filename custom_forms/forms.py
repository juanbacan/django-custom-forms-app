
from django import forms
from core.forms import ModelBaseForm, BaseInline, BaseForm
from dal import autocomplete, forward

from .models import Formulario, Encuesta

class FormularioForm(ModelBaseForm):
    class Meta:
        model = Formulario
        fields = ['nombre']
        labels = {
            'nombre': 'Nombre del Formulario',
        }



class EncuestaForm(ModelBaseForm):
    class Meta:
        model = Encuesta
        fields = '__all__'
        labels = {
            'nombre': 'Nombre de la Encuesta',
            'descripcion': 'Descripción',
            'activa': 'Encuesta Activa',
            'fecha_inicio': 'Fecha de Inicio',
            'fecha_fin': 'Fecha de Fin',
        }
        exclude = ['creada_por', 'creada_en']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
        }