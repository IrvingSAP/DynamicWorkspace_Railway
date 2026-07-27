(function () {
  "use strict";

  function maskValue(raw) {
    var text = raw == null ? "" : String(raw);
    if (!text) return "—";
    if (text.length <= 2) return "**";
    return text.slice(0, 2) + "***";
  }

  function applyMask(masked) {
    document.querySelectorAll("[data-raw-value]").forEach(function (el) {
      var raw = el.getAttribute("data-raw-value") || "";
      el.textContent = masked ? maskValue(raw) : raw || "—";
      el.classList.toggle("value-masked", masked);
    });
  }

  function bindMaskToggle() {
    var toggle = document.getElementById("toggle-reveal-values");
    if (!toggle) return;
    applyMask(!toggle.checked);
    toggle.addEventListener("change", function () {
      applyMask(!toggle.checked);
    });
  }

  function bindSeverityFilters() {
    var chips = document.querySelectorAll("[data-sev-filter]");
    var rows = document.querySelectorAll("[data-sev]");
    if (!chips.length || !rows.length) return;

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        var sev = chip.getAttribute("data-sev-filter");
        chips.forEach(function (c) {
          c.classList.toggle("is-active", c === chip);
        });
        rows.forEach(function (row) {
          var match = sev === "all" || row.getAttribute("data-sev") === sev;
          row.hidden = !match;
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindMaskToggle();
    bindSeverityFilters();
  });
})();
