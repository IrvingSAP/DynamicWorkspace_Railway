(function () {
  "use strict";

  function numberValue(id, fallback) {
    var node = document.getElementById(id);
    var value = node ? Number(node.value) : fallback;
    return Number.isFinite(value) ? value : fallback;
  }

  function selectedMode() {
    var checked = document.querySelector('input[name="threshold_mode"]:checked');
    return checked ? checked.value : "percent";
  }

  function syncMaxErrors() {
    var input = document.getElementById("max_errors");
    var range = document.getElementById("max_errors_range");
    var output = document.getElementById("max_errors_output");
    if (!input || !range || !output) return;

    function setValue(value) {
      var safe = Math.max(1, Math.min(10000, Number(value) || 1));
      input.value = safe;
      range.value = safe;
      output.textContent = safe.toLocaleString("es-ES") + " errores";
    }

    range.addEventListener("input", function () {
      setValue(range.value);
    });
    input.addEventListener("input", function () {
      setValue(input.value);
    });
    setValue(input.value);
  }

  function syncThreshold() {
    var unit = document.getElementById("threshold_unit");
    var hint = document.getElementById("threshold_hint");
    var input = document.getElementById("threshold_value");
    if (!input) return;

    var mode = selectedMode();
    if (unit) unit.textContent = mode === "percent" ? "%" : "filas";
    if (hint) {
      hint.textContent = mode === "percent"
        ? "Falla cuando el porcentaje de filas rechazadas supera este valor."
        : "Falla cuando la cantidad de filas rechazadas supera este valor.";
    }
    input.max = mode === "percent" ? "100" : "10000000";
    input.step = mode === "percent" ? "0.1" : "1";
    syncDecisionLab();
  }

  function syncDecisionLab() {
    var outcome = document.getElementById("decision_outcome");
    var status = document.getElementById("decision_status");
    var detail = document.getElementById("decision_detail");
    if (!outcome || !status || !detail) return;

    var rows = Math.max(0, numberValue("lab_rows", 1000));
    var rejected = Math.max(0, numberValue("lab_rejected", 0));
    var threshold = Math.max(0, numberValue("threshold_value", 1));
    var mode = selectedMode();
    var measured = mode === "percent"
      ? (rows > 0 ? (rejected / rows) * 100 : 0)
      : rejected;
    var failed = measured > threshold;

    outcome.classList.toggle("is-failed", failed);
    status.textContent = failed ? "FAILED" : "PASSED";
    detail.textContent = mode === "percent"
      ? measured.toLocaleString("es-ES", { maximumFractionDigits: 4 }) + "% frente a " + threshold + "%"
      : rejected.toLocaleString("es-ES") + " frente a " + threshold + " permitidas";
  }

  document.addEventListener("DOMContentLoaded", function () {
    syncMaxErrors();

    document.querySelectorAll('input[name="threshold_mode"]').forEach(function (input) {
      input.addEventListener("change", syncThreshold);
    });

    ["threshold_value", "lab_rows", "lab_rejected"].forEach(function (id) {
      var input = document.getElementById(id);
      if (input) input.addEventListener("input", syncDecisionLab);
    });

    syncThreshold();
  });
})();

