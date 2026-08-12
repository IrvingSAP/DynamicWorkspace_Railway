(function () {
  function syncParams() {
    var select = document.querySelector("[data-sm-code]");
    if (!select) return;
    var code = select.value;
    var option = select.options[select.selectedIndex];
    var scope = option ? option.getAttribute("data-scope") : "field";
    var fieldWrap = document.querySelector("[data-sm-field-wrap]");
    if (fieldWrap) {
      fieldWrap.hidden = scope !== "field";
    }
    var shown = false;
    document.querySelectorAll("[data-sm-params]").forEach(function (el) {
      var match = el.getAttribute("data-sm-params") === code;
      el.hidden = !match;
      if (match) shown = true;
    });
    var empty = document.querySelector("[data-sm-params-empty]");
    if (empty) empty.hidden = shown;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var select = document.querySelector("[data-sm-code]");
    if (!select) return;
    select.addEventListener("change", syncParams);
    syncParams();
  });
})();
