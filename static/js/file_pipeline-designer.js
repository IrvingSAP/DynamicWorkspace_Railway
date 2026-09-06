(function () {
  var cfg = window.FP_DESIGNER || {};
  var kindEl = document.getElementById("fp-kind");
  var projEl = document.getElementById("fp-proj");
  var railEl = document.getElementById("fp-rail");
  var emptyEl = document.getElementById("fp-rail-empty");
  var jsonEl = document.getElementById("fp-steps-json");
  var formEl = document.getElementById("fp-designer-form");
  var addBtn = document.getElementById("fp-add-step");
  var kindsNode = document.getElementById("fp-kinds");
  var draftNode = document.getElementById("fp-draft-steps");
  var kinds = kindsNode ? JSON.parse(kindsNode.textContent) : [];
  var steps = draftNode ? JSON.parse(draftNode.textContent) : [];
  if (!Array.isArray(steps)) steps = [];

  function kindMeta(kind) {
    for (var i = 0; i < kinds.length; i++) {
      if (kinds[i].kind === kind) return kinds[i];
    }
    return { kind: kind, label: kind, short: kind };
  }

  function fillProjects(list) {
    projEl.innerHTML = "";
    if (!list || !list.length) {
      var empty = document.createElement("option");
      empty.value = "";
      empty.disabled = true;
      empty.selected = true;
      empty.textContent = "Sin proyectos activos autorizados";
      projEl.appendChild(empty);
      return;
    }
    list.forEach(function (p, i) {
      var opt = document.createElement("option");
      opt.value = p.slug;
      opt.textContent = p.label;
      if (i === 0) opt.selected = true;
      projEl.appendChild(opt);
    });
  }

  function loadProjects() {
    if (!kindEl || !cfg.projectsUrl) return;
    var url = cfg.projectsUrl + "?kind=" + encodeURIComponent(kindEl.value);
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) { fillProjects(data.results || []); })
      .catch(function () { fillProjects([]); });
  }

  function syncHidden() {
    if (jsonEl) jsonEl.value = JSON.stringify(steps);
  }

  function render() {
    railEl.innerHTML = "";
    if (emptyEl) emptyEl.hidden = steps.length > 0;
    steps.forEach(function (step, index) {
      var meta = kindMeta(step.kind);
      var inputFrom = index === 0 ? "pipeline_input" : "previous";
      var li = document.createElement("li");
      li.className = "fp-step-rail-item";
      var nodeClass = "fp-step-node is-ok";
      li.innerHTML =
        '<span class="' + nodeClass + '">' + (index + 1) + "</span>" +
        '<div class="fp-step-card">' +
        "<h4>" + meta.label + " · <code>" + step.project_slug + "</code></h4>" +
        '<p class="fp-step-meta">kind <code>' + step.kind + "</code> · input: " + inputFrom +
        " · on_error: stop</p>" +
        (cfg.canEdit
          ? '<p class="fp-step-meta fp-step-actions">' +
            '<button type="button" data-act="up" data-i="' + index + '">Subir</button> · ' +
            '<button type="button" data-act="down" data-i="' + index + '">Bajar</button> · ' +
            '<button type="button" data-act="rm" data-i="' + index + '">Quitar</button></p>'
          : "") +
        "</div>";
      railEl.appendChild(li);
    });
    syncHidden();
  }

  if (kindEl) kindEl.addEventListener("change", loadProjects);
  if (addBtn) {
    addBtn.addEventListener("click", function () {
      var slug = projEl.value;
      if (!slug) return;
      steps.push({ kind: kindEl.value, project_slug: slug });
      render();
    });
  }
  if (railEl) {
    railEl.addEventListener("click", function (ev) {
      var btn = ev.target.closest("button[data-act]");
      if (!btn) return;
      var i = parseInt(btn.getAttribute("data-i"), 10);
      var act = btn.getAttribute("data-act");
      if (act === "rm") steps.splice(i, 1);
      if (act === "up" && i > 0) {
        var t = steps[i - 1];
        steps[i - 1] = steps[i];
        steps[i] = t;
      }
      if (act === "down" && i < steps.length - 1) {
        var u = steps[i + 1];
        steps[i + 1] = steps[i];
        steps[i] = u;
      }
      render();
    });
  }
  if (formEl) {
    formEl.addEventListener("submit", function () { syncHidden(); });
  }
  render();
})();
