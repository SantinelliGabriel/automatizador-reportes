"""Formularios de clientes e importaciones."""

from django import forms

from automatizador.clientes import clave_cliente
from web.comprobantes.cargas import validar_archivo
from web.comprobantes.models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "cuit"]

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        clave = clave_cliente(nombre)
        if Cliente.objects.filter(nombre_clave=clave).exists():
            raise forms.ValidationError("Ya existe un cliente con ese nombre.")
        return nombre


class CargaForm(forms.Form):
    cliente = forms.ModelChoiceField(queryset=Cliente.objects.order_by("nombre"))
    periodo = forms.RegexField(regex=r"^\d{4}-(0[1-9]|1[0-2])$", max_length=7,
                               help_text="Formato AAAA-MM")
    origen = forms.ChoiceField(choices=[("estandar", "Estándar"), ("arca", "ARCA"),
                                         ("holistor", "Holistor")])
    operacion = forms.ChoiceField(choices=[("ventas", "Ventas"), ("compras", "Compras")])
    archivo = forms.FileField()

    def clean(self):
        datos = super().clean()
        if datos.get("archivo") and datos.get("origen"):
            nombre, sufijo = validar_archivo(datos["archivo"], datos["origen"])
            datos["nombre_archivo"] = nombre
            datos["sufijo"] = sufijo
        return datos
