/**
 * File Watch M9 — avisos: muestra campos si enabled.
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var en = document.getElementById("notify_enabled");
    var box = document.getElementById("notify-fields");
    if (!en || !box) return;
    function sync() {
      var on = en.checked;
      box.hidden = !on;
      box.classList.toggle("is-hidden", !on);
    }
    en.addEventListener("change", sync);
    sync();
  });
})();
