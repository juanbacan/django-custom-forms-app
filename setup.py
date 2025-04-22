from setuptools import setup, find_packages

setup(
    name="django-custom-forms-app",  # Nombre que tendrá en PyPI
    version="0.0.12",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Django>=3.1",  
    ],
    author="juanbacan",
    author_email="juan.ingaor@gmail.com",
    description="Sistema de formularios dinámicos para Django con constructor visual basado en Formio.js, control de roles, versionado automático y tipado de respuestas.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/juanbacan/django-custom-forms-app",  # URL del repositorio (cuando esté en GitHub)
    classifiers=[
        "Framework :: Django",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
