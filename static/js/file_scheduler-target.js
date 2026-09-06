(function () {
  var form = document.getElementById("target-form");
  if (!form) return;

  var projectsUrl = form.getAttribute("data-projects-url") || "";
  var panelJob = document.getElementById("panel-job");
  var panelPipeline = document.getElementById("panel-pipeline");
  var fieldWatch = document.getElementById("field-watch");
  var fieldArtifact = document.getElementById("field-artifact");
  var fieldNone = document.getElementById("field-none-confirm");
  var kindSelect = document.getElementById("kind");
  var projectSelect = document.getElementById("project_id");
  var selectedProject = projectSelect ? projectSelect.value : "";

  function mode() {
    var el = form.querySelector('input[name="target_mode"]:checked');
    return el ? el.value : "job";
  }

  function origin() {
    var el = form.querySelector('input[name="input_origin"]:checked');
    return el ? el.value : "watch";
  }

  function syncPanels() {
    var isJob = mode() === "job";
    if (panelJob) panelJob.classList.toggle("is-hidden", !isJob);
    if (panelPipeline) panelPipeline.classList.toggle("is-hidden", isJob);
    var o = origin();
    if (isJob && o === "none") {
      var watchRadio = form.querySelector('input[name="input_origin"][value="watch"]');
      if (watchRadio) watchRadio.checked = true;
      o = "watch";
    }
    if (fieldWatch) fieldWatch.classList.toggle("is-hidden", o !== "watch");
    if (fieldArtifact) fieldArtifact.classList.toggle("is-hidden", o !== "artifact");
    if (fieldNone) fieldNone.classList.toggle("is-hidden", !(o === "none" && !isJob));
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
        projectSelect.innerHTML = '<option value="">— Elija un proyecto —</option>';
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

  form.addEventListener("change", function (ev) {
    var name = ev.target && ev.target.name;
    if (name === "target_mode" || name === "input_origin") syncPanels();
    if (name === "kind") {
      selectedProject = "";
      loadProjects();
    }
    if (name === "project_id") selectedProject = projectSelect.value;
  });

  syncPanels();
})();
