(function () {
  var form = document.getElementById("fire-form");
  if (!form) return;
  var defer = form.getAttribute("data-route-defer") === "1";

  function mode() {
    var el = form.querySelector('input[name="fire_mode"]:checked');
    return el ? el.value : "pending_only";
  }

  function sync() {
    var bad = mode() === "on_arrival" && defer;
    var conflict = document.getElementById("fire-conflict");
    var btn = document.getElementById("btn-save-fire");
    if (conflict) {
      conflict.hidden = !bad;
      conflict.classList.toggle("is-hidden", !bad);
    }
    if (btn) btn.disabled = bad;
  }

  document.addEventListener("DOMContentLoaded", function () {
    form.querySelectorAll('input[name="fire_mode"]').forEach(function (r) {
      r.addEventListener("change", sync);
    });
    sync();
  });
})();
