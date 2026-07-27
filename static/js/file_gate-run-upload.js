(function () {
  "use strict";

  function bindDropzone() {
    var zone = document.getElementById("run-dropzone");
    var input = document.getElementById("run-file-input");
    var chip = document.getElementById("run-file-chip");
    var nameEl = document.getElementById("run-file-name");
    var btn = document.getElementById("btn-run-validate");
    if (!zone || !input) return;

    function enableBtn() {
      if (!btn) return;
      btn.disabled = false;
    }

    function setFile(file) {
      if (!file) return;
      zone.classList.add("has-file");
      if (chip && nameEl) {
        chip.hidden = false;
        nameEl.textContent =
          file.name + " · " + Math.max(1, Math.round(file.size / 1024)) + " KB";
      }
      enableBtn();
    }

    zone.addEventListener("click", function () {
      input.click();
    });

    zone.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        input.click();
      }
    });

    zone.addEventListener("dragover", function (event) {
      event.preventDefault();
      zone.classList.add("is-dragover");
    });

    zone.addEventListener("dragleave", function () {
      zone.classList.remove("is-dragover");
    });

    zone.addEventListener("drop", function (event) {
      event.preventDefault();
      zone.classList.remove("is-dragover");
      var file =
        event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) {
        input.files = event.dataTransfer.files;
        setFile(file);
      }
    });

    input.addEventListener("change", function () {
      setFile(input.files && input.files[0]);
    });
  }

  document.addEventListener("DOMContentLoaded", bindDropzone);
})();
