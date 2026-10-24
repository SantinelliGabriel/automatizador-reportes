"""Rutas de la interfaz local."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from web.comprobantes import views


urlpatterns = [
    path("", views.clientes, name="clientes"),
    path("login/", auth_views.LoginView.as_view(template_name="comprobantes/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("clientes/nuevo/", views.cliente_nuevo, name="cliente_nuevo"),
    path("cargar/", views.cargar, name="cargar"),
    path("vista-previa/", views.vista_previa, name="vista_previa"),
    path("confirmar/", views.confirmar, name="confirmar"),
    path("admin/", admin.site.urls),
]
