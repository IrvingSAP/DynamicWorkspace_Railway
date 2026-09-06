(function () {
  var form = document.getElementById("source-form");
  if (!form) return;

  function selectedKind() {
    var el = form.querySelector('input[name="source_kind"]:checked');
    return el ? el.value : "sftp";
  }

  function syncPanels() {
    var kind = selectedKind();
    document.querySelectorAll(".source-panel").forEach(function (panel) {
      var match = panel.getAttribute("data-kind") === kind;
      panel.hidden = !match;
      panel.classList.toggle("is-hidden", !match);
      panel.querySelectorAll("input, select, textarea").forEach(function (el) {
        el.disabled = !match;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    form.querySelectorAll('input[name="source_kind"]').forEach(function (radio) {
      radio.addEventListener("change", syncPanels);
    });
    syncPanels();
  });
})();
