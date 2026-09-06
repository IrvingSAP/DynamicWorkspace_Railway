(function () {
  var form = document.getElementById("route-form");
  if (!form) return;
  var projectsUrl = form.getAttribute("data-projects-url") || "";
  var kindSelect = document.getElementById("kind");
  var projectSelect = document.getElementById("project_id");
  var selectedProject = projectSelect ? projectSelect.value : "";

  function mode() {
    var el = form.querySelector('input[name="route_mode"]:checked');
    return el ? el.value : "defer";
  }

  function sync() {
    var m = mode();
    document.querySelectorAll(".route-panel").forEach(function (panel) {
      var match = panel.getAttribute("data-mode") === m;
      panel.hidden = !match;
      panel.classList.toggle("is-hidden", !match);
    });
  }

  function loadProjects() {
    if (!kindSelect || !projectSelect || !projectsUrl) return;
    var kind = kindSelect.value;
    var url = projectsUrl + (projectsUrl.indexOf("?") >= 0 ? "&" : "?") + "kind=" + encodeURIComponent(kind);
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var rows = (data && data.projects) || [];
        var keep = selectedProject;
        projectSelect.innerHTML = '<option value="">— Elija —</option>';
        rows.forEach(function (row) {
          var opt = document.createElement("option");
          opt.value = row.id;
          opt.textContent = row.label;
          if (!row.published) opt.disabled = true;
          if (row.id === keep && row.published) opt.selected = true;
          projectSelect.appendChild(opt);
        });
      })
      .catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", function () {
    form.querySelectorAll('input[name="route_mode"]').forEach(function (r) {
      r.addEventListener("change", sync);
    });
    if (kindSelect) kindSelect.addEventListener("change", loadProjects);
    sync();
  });
})();
