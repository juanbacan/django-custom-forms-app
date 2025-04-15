
from .views_admin import FormularioAdminView, EncuestaAdminView

custom_forms_urls = (
    {
        "nombre": "Formularios",
        "url": 'formularios/',
        "vista": FormularioAdminView.as_view(),
        "namespace": 'admin_formularios',
    },
    {
        "nombre": "Encuestas",
        "url": 'encuestas/',
        "vista": EncuestaAdminView.as_view(),
        "namespace": 'admin_encuestas',
    },
)