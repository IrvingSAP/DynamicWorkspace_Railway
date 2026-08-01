/**
 * STRUCTURE SCOUT — abrir/cerrar diálogo de ayuda «revisión pendiente».
 */
(function () {
  function closeDialog(dialog) {
    if (!dialog) return;
    if (typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
  }

  function openDialog(dialog) {
    if (!dialog) return;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  document.addEventListener("click", function (event) {
    var openBtn = event.target.closest("[data-ss-review-help-open]");
    if (openBtn) {
      event.preventDefault();
      var id = openBtn.getAttribute("data-ss-review-help-open");
      openDialog(document.getElementById(id));
      return;
    }
    var closeBtn = event.target.closest("[data-ss-review-help-close]");
    if (closeBtn) {
      event.preventDefault();
      closeDialog(closeBtn.closest("dialog"));
    }
  });

  document.addEventListener("click", function (event) {
    var dialog = event.target;
    if (dialog && dialog.tagName === "DIALOG" && dialog.classList.contains("ss-needs-review-dialog")) {
      // Clic en backdrop (el propio dialog, no el panel)
      var rect = dialog.getBoundingClientRect();
      var inDialog =
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;
      // Con showModal, el backdrop es el dialog; si el click es en el panel interno, no cerrar
      if (event.target === dialog) {
        closeDialog(dialog);
      }
    }
  });
})();
