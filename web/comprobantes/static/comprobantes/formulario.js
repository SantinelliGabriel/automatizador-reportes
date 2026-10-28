"use strict";

const origen = document.getElementById("id_origen");
const operacion = document.getElementById("id_operacion");
if (origen && operacion) {
  const mixto = operacion.querySelector('option[value="mixto"]');
  if (mixto) {
    function actualizarOperacion() {
      mixto.disabled = origen.value !== "estandar";
      mixto.hidden = mixto.disabled;
      if (mixto.disabled && operacion.value === "mixto") operacion.value = "ventas";
    }
    origen.addEventListener("change", actualizarOperacion);
    actualizarOperacion();
  }
}
