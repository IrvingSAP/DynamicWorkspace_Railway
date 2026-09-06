(function () {
  var form = document.getElementById("cron-form");
  if (!form) return;
  var previewUrl = form.getAttribute("data-preview-url");
  var fieldTime = document.getElementById("field-time");
  var fieldMonthly = document.getElementById("field-monthly");
  var fieldDom = document.getElementById("field-dom");
  var fieldCron = document.getElementById("field-cron");
  var fieldDow = document.getElementById("field-dow");
  var tape = document.getElementById("slot-tape");
  var cronInput = document.getElementById("cron_expr");
  var cronError = document.getElementById("cron-error");

  function kind() {
    var el = form.querySelector('input[name="schedule_kind"]:checked');
    return el ? el.value : "daily";
  }
  function monthlyMode() {
    var el = form.querySelector('input[name="monthly_mode"]:checked');
    return el ? el.value : "last_day";
  }
  function syncFields() {
    var k = kind();
    fieldTime.classList.toggle("is-hidden", k === "cron");
    fieldDow.classList.toggle("is-hidden", k !== "weekly");
    fieldMonthly.classList.toggle("is-hidden", k !== "monthly");
    fieldDom.classList.toggle("is-hidden", k !== "monthly" || monthlyMode() !== "specific");
    fieldCron.classList.toggle("is-hidden", k !== "cron");
  }
  function paintSlots(slots) {
    if (!tape) return;
    if (!slots || !slots.length) {
      tape.innerHTML = "<li>Sin preview</li>";
      return;
    }
    tape.innerHTML = slots
      .map(function (s, i) {
        return "<li><strong>" + (i + 1) + "</strong> " + s + "</li>";
      })
      .join("");
  }
  function refreshPreview() {
    if (!previewUrl) return;
    var params = new URLSearchParams(new FormData(form));
    fetch(previewUrl + "?" + params.toString(), {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.ok) {
          paintSlots(data.slots);
          if (cronError && kind() === "cron") {
            cronError.textContent = "";
            cronError.classList.add("is-hidden");
            fieldCron.classList.remove("has-error");
          }
        } else {
          paintSlots([]);
          if (kind() === "cron" && cronError && data.error) {
            cronError.textContent = data.error;
            cronError.classList.remove("is-hidden");
            fieldCron.classList.add("has-error");
          }
        }
      })
      .catch(function () {});
  }
  form.querySelectorAll('input[name="schedule_kind"]').forEach(function (el) {
    el.addEventListener("change", function () {
      syncFields();
      refreshPreview();
    });
  });
  form.querySelectorAll('input[name="monthly_mode"]').forEach(function (el) {
    el.addEventListener("change", function () {
      syncFields();
      refreshPreview();
    });
  });
  ["time_local", "timezone", "day_of_week", "day_of_month", "cron_expr"].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("change", refreshPreview);
    el.addEventListener("input", refreshPreview);
  });
  syncFields();
})();
