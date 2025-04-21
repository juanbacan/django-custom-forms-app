import json
from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q

from core.views import ViewAdministracionBase
from core.utils import error_json, success_json, get_redirect_url

from .utils import guardar_o_actualizar_campos_respuesta, actualizar_formulario_y_guardar_version

from .models import Formulario, Encuesta, RespuestaEncuesta, FormularioVersion
from .forms import FormularioForm, EncuestaForm

class FormularioAdminView(ViewAdministracionBase):
    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if self.action and hasattr(self, f'post_{self.action}'):
            return getattr(self, f'post_{self.action}')(request, context, *args, **kwargs)
        return error_json(mensaje="Acción no permitida")
    
    def post_add(self, request, context, *args, **kwargs):
        form = FormularioForm(request.POST)
        if form.is_valid():
            object = form.save(commit=False)

            schema = request.POST.get('schema', None)
            if not   schema:
                return error_json(mensaje="No ha agregado campos al formulario")
            try:
                schema = json.loads(schema)
            except json.JSONDecodeError:
                return error_json(mensaje="El esquema no es un JSON válido")

            object.json = schema
            object.save()

            messages.success(request, "Formulario creado exitosamente")
            return success_json(mensaje="Formulario creado exitosamente", url=get_redirect_url(request, object))
        else:
            return error_json(mensaje="Error al crear el formulario", forms=[form])
        
    def post_edit(self, request, context, *args, **kwargs):
        object = Formulario.objects.get(pk=self.data.get('id', None))
        form = FormularioForm(request.POST, instance=object)
        if form.is_valid():
            object = form.save(commit=False)
            schema = request.POST.get('schema', None)
            
            if not   schema:
                return error_json(mensaje="No ha agregado campos al formulario")
            try:
                schema = json.loads(schema)
            except json.JSONDecodeError:
                return error_json(mensaje="El esquema no es un JSON válido")
            
            actualizar_formulario_y_guardar_version(object, schema)

            mensaje = "Formulario editado exitosamente"
            messages.success(request, mensaje)
            return success_json(mensaje=mensaje, url=get_redirect_url(request, object))
        else:
            return error_json(mensaje="Error al editar el formulario", forms=[form])

    def post_delete(self, request, context, *args, **kwargs):
        id = self.data.get('id', None)
        object = Formulario.objects.get(id=id)
        object.delete()
        messages.success(request, "Formulario eliminado exitosamente")
        return success_json(mensaje="Formulario eliminado exitosamente", url=get_redirect_url(request, object))
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if self.action and hasattr(self, f'get_{self.action}'):
            return getattr(self, f'get_{self.action}')(request, context, *args, **kwargs)

        context['objects'] = Formulario.objects.all()
        return render(request, 'custom_forms/admin/lista.html', context)
    
    def get_add(self, request, context, *args, **kwargs):
        context['form'] = FormularioForm()
        return render(request, 'custom_forms/admin/form_formulario.html', context)
    
    def get_edit(self, request, context, *args, **kwargs):
        object = Formulario.objects.get(pk=self.data.get('id', None))
        context['form'] = FormularioForm(instance=object)
        context['object'] = object
        return render(request, 'custom_forms/admin/form_formulario.html', context)
    
    def get_versiones(self, request, context, *args, **kwargs):
        object = Formulario.objects.get(pk=self.data.get('id', None))
        context['object'] = object
        context['versiones'] = object.versiones.all()
        return render(request, 'custom_forms/admin/versiones.html', context)
    
    def get_ver_version(self, request, context, *args, **kwargs):
        object = FormularioVersion.objects.get(pk=self.data.get('id', None))
        context['object'] = object
        return render(request, 'custom_forms/admin/ver_version.html', context)
    
    def get_generar_modelo_django(self, request, context, *args, **kwargs):
        object = Formulario.objects.get(pk=self.data.get('id', None))
        context['object'] = object
        context['modelo_code'] = object.generar_modelo_django()
        return render(request, 'custom_forms/admin/generar_modelo.html', context)

    def get_delete(self, request, context, *args, **kwargs):
        id = self.data.get('id', None)
        object = Formulario.objects.get(id=id)
        context['title'] = "Eliminar registro"
        context['message'] = f'¿Está seguro de que desea eliminar el registro: {object}?"'
        context['formid'] = object.id 
        context['delete_obj'] = True
        return render(request, 'core/modals/formModal.html', context)
    

class EncuestaAdminView(ViewAdministracionBase):
    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if self.action and hasattr(self, f'post_{self.action}'):
            return getattr(self, f'post_{self.action}')(request, context, *args, **kwargs)
        return error_json(mensaje="Acción no permitida")
    
    def post_add(self, request, context, *args, **kwargs):
        form = EncuestaForm(request.POST)
        if form.is_valid():
            object = form.save(commit=False)
            object.creada_por = request.user if request.user.is_authenticated else None
            object.creada_en = datetime.now()
            object.save()
            messages.success(request, "Encuesta creada exitosamente")
            return success_json(mensaje="Encuesta creada exitosamente", url=get_redirect_url(request, object))
        else:
            return error_json(mensaje="Error al crear la encuesta", forms=[form])
        
    def post_edit(self, request, context, *args, **kwargs):
        object = Encuesta.objects.get(pk=self.data.get('id', None))
        form = EncuestaForm(request.POST, instance=object)
        if form.is_valid():
            object = form.save()
            messages.success(request, "Encuesta editada exitosamente")
            return success_json(mensaje="Encuesta editada exitosamente", url=get_redirect_url(request, object))
        else:
            return error_json(mensaje="Error al editar la encuesta", forms=[form])

    def post_delete(self, request, context, *args, **kwargs):
        id = self.data.get('id', None)
        object = Encuesta.objects.get(id=id)
        object.delete()
        messages.success(request, "Formulario eliminado exitosamente")
        return success_json(mensaje="Formulario eliminado exitosamente", url=get_redirect_url(request, object))
    
    def post_responder_encuesta(self, request, context, *args, **kwargs):
        encuesta = Encuesta.objects.get(pk=self.data.get('id', None))
        respuestas = json.loads(request.POST.get('respuestas', None))

        respuesta = RespuestaEncuesta.objects.create(
            encuesta=encuesta,
            usuario=request.user if request.user.is_authenticated else None,
            version=encuesta.formulario.version
        )

        errores = guardar_o_actualizar_campos_respuesta(respuesta, respuestas)
        if errores:
            raise ValueError("Error al guardar las respuestas: " + str(errores))
        
        messages.success(request, "Encuesta respondida exitosamente")
        return success_json(mensaje="Encuesta respondida exitosamente", url=get_redirect_url(request, encuesta))
    
    def post_edit_resultado(self, request, context, *args, **kwargs):
        respuesta = RespuestaEncuesta.objects.get(pk=self.data.get('id_respuesta', None))
        respuestas = json.loads(request.POST.get('respuestas', None))

        errores = guardar_o_actualizar_campos_respuesta(respuesta, respuestas)
        if errores:
            raise ValueError("Error al guardar las respuestas: " + str(errores))
        
        messages.success(request, "Encuesta editada exitosamente")
        return success_json(mensaje="Encuesta editada exitosamente", url=get_redirect_url(request, respuesta, self.action))
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if self.action and hasattr(self, f'get_{self.action}'):
            return getattr(self, f'get_{self.action}')(request, context, *args, **kwargs)

        context['objects'] = Encuesta.objects.all()
        return render(request, 'custom_forms/admin/lista_encuestas.html', context)
    
    def get_add(self, request, context, *args, **kwargs):
        context['form'] = EncuestaForm()
        return render(request, 'core/forms/formAdmin.html', context)
    
    def get_edit(self, request, context, *args, **kwargs):
        object = Encuesta.objects.get(pk=self.data.get('id', None))
        context['form'] = EncuestaForm(instance=object)
        context['object'] = object
        return render(request, 'core/forms/formAdmin.html', context)
    
    def get_responder_encuesta(self, request, context, *args, **kwargs):
        context['encuesta'] = encuesta = Encuesta.objects.get(pk=self.data.get('id', None))
        context['formulario'] = encuesta.formulario
        return render(request, 'custom_forms/admin/responder_encuesta.html', context)
    
    def get_resultados(self, request, context, *args, **kwargs):
        context['object'] = encuesta = Encuesta.objects.get(pk=self.data.get('id', None))
        respuestas = RespuestaEncuesta.objects.filter(encuesta=encuesta).prefetch_related('campos')

        resultados = []
        for respuesta in respuestas:
            fila = {
                'id': respuesta.id,
                'usuario': respuesta.usuario,
                'fecha': respuesta.enviado,
                'campos': {campo.clave: campo.valor for campo in respuesta.campos.all()}
            }
            resultados.append(fila)
        context['resultados'] = resultados
        return render(request, 'custom_forms/admin/resultados.html', context)
    
    def get_ver_resultado(self, request, context, *args, **kwargs):
        context['object'] = respuesta = RespuestaEncuesta.objects.get(pk=self.data.get('id', None))
        version_obj = FormularioVersion.objects.filter(
            formulario=respuesta.encuesta.formulario,
            numero=respuesta.version
        ).first()

        schema = version_obj.json if version_obj else respuesta.encuesta.formulario.json
        # Convertir los campos a un dict {clave: valor} para pasar a Formio
        submission_data = {campo.clave: json.loads(campo.valor) if campo.valor.startswith('[') or campo.valor.startswith('{') else campo.valor for campo in respuesta.campos.all()}
        context['schema'] = schema
        context['submission'] = submission_data
        context['formulario'] = respuesta.encuesta.formulario
        context['encuesta'] = respuesta.encuesta
        context['informativo'] = True # Solo visualización del formulario
        return render(request, 'custom_forms/admin/responder_encuesta.html', context)
        # return render(request, 'custom_forms/admin/ver_resultado.html', context)
    

    def get_edit_resultado(self, request, context, *args, **kwargs):
        context['object'] = respuesta = RespuestaEncuesta.objects.get(pk=self.data.get('id', None))
        version_obj = FormularioVersion.objects.filter(formulario=respuesta.encuesta.formulario, numero=respuesta.version).first()

        schema = version_obj.json if version_obj else respuesta.encuesta.formulario.json
        # Convertir los campos a un dict {clave: valor} para pasar a Formio
        submission_data = {campo.clave: json.loads(campo.valor) if campo.valor.startswith('[') or campo.valor.startswith('{') else campo.valor for campo in respuesta.campos.all()}
        context['schema'] = schema
        context['submission'] = submission_data
        context['formulario'] = respuesta.encuesta.formulario
        context['encuesta'] = respuesta.encuesta
        return render(request, 'custom_forms/admin/responder_encuesta.html', context)

    def get_delete(self, request, context, *args, **kwargs):
        id = self.data.get('id', None)
        object = Encuesta.objects.get(id=id)
        context['title'] = "Eliminar registro"
        context['message'] = f'¿Está seguro de que desea eliminar el registro: {object}?"'
        context['formid'] = object.id 
        context['delete_obj'] = True
        return render(request, 'core/modals/formModal.html', context)
        
    
