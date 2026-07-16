/**
 * Editor UI — Transform Rules (transform_rules.md)
 */
(function () {
    "use strict";

    const api = window.dmsTransformRules;
    if (!api) {
        return;
    }

    function readJson(id, fallback) {
        const node = document.getElementById(id);
        if (!node) {
            return fallback;
        }
        try {
            return JSON.parse(node.textContent || "null") || fallback;
        } catch (_err) {
            return fallback;
        }
    }

    const opsCatalog = readJson("dms-transform-ops-catalog", []);
    const pipelineTemplates = readJson("dms-transform-pipeline-templates", []);

    let activeTarget = null;

    const targetsEl = document.getElementById("tr-targets");
    const stepsEl = document.getElementById("tr-steps");
    const emptySteps = document.getElementById("tr-empty-steps");
    const titleEl = document.getElementById("tr-active-title");
    const metaEl = document.getElementById("tr-active-meta");
    const addBtn = document.getElementById("tr-add-step");
    const applyTplBtn = document.getElementById("tr-apply-template");
    const templateSelect = document.getElementById("tr-template-select");
    const saveBtn = document.getElementById("tr-save-btn");
    const previewBtn = document.getElementById("tr-preview-btn");
    const previewSampleBtn = document.getElementById("tr-preview-sample-btn");
    const previewSample = document.getElementById("tr-preview-sample");
    const previewResult = document.getElementById("tr-preview-result");
    const formErrors = document.getElementById("tr-form-errors");

    function findRow(target) {
        return api.getRows().find(function (row) {
            return row.target_field === target;
        });
    }

    function updateStats() {
        const rows = api.getRows();
        let withSteps = 0;
        let total = 0;
        rows.forEach(function (row) {
            const n = (row.transform_pipeline || []).length;
            total += n;
            if (n) {
                withSteps += 1;
            }
        });
        const set = function (id, value) {
            const node = document.getElementById(id);
            if (node) {
                node.textContent = String(value);
            }
        };
        set("tr-stat-fields", rows.length);
        set("tr-stat-with", withSteps);
        set("tr-stat-steps", total);
    }

    function renderTargets() {
        if (!targetsEl) {
            return;
        }
        targetsEl.innerHTML = "";
        api.getRows().forEach(function (row) {
            const li = document.createElement("li");
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className =
                "tr-target-item" + (row.target_field === activeTarget ? " is-active" : "");
            btn.innerHTML =
                '<span class="tr-target-name"></span><span class="tr-target-meta"></span>';
            btn.querySelector(".tr-target-name").textContent = row.target_field;
            const pipe = row.transform_pipeline || [];
            btn.querySelector(".tr-target-meta").textContent = pipe.length
                ? pipe
                      .map(function (step) {
                          return step.op;
                      })
                      .join(" → ")
                : "sin reglas";
            btn.addEventListener("click", function () {
                activeTarget = row.target_field;
                renderTargets();
                renderSteps();
            });
            li.appendChild(btn);
            targetsEl.appendChild(li);
        });
        updateStats();
    }

    function syncRowPipeline(pipeline) {
        const rows = api.getRows().map(function (row) {
            if (row.target_field !== activeTarget) {
                return row;
            }
            const next = Object.assign({}, row);
            next.transform_pipeline = pipeline;
            next.ops_label = pipeline.length
                ? pipeline
                      .map(function (step) {
                          return step.op;
                      })
                      .join(" → ")
                : "(sin reglas)";
            return next;
        });
        api.setRows(rows);
        renderTargets();
    }

    function readPipelineFromDom() {
        const pipeline = [];
        if (!stepsEl) {
            return pipeline;
        }
        stepsEl.querySelectorAll(".tr-step").forEach(function (node) {
            const op = node.querySelector(".tr-step-op").value;
            const step = { op: op };
            if (op === "date_format") {
                const format = (node.querySelector('[data-param="format"]') || {}).value || "";
                const inputs = (node.querySelector('[data-param="input_formats"]') || {}).value || "";
                if (format) {
                    step.format = format;
                }
                if (inputs.trim()) {
                    step.input_formats = inputs
                        .split(",")
                        .map(function (part) {
                            return part.trim();
                        })
                        .filter(Boolean);
                }
            } else if (op === "pad_left" || op === "pad_right") {
                step.char = (node.querySelector('[data-param="char"]') || {}).value || " ";
                step.length = Number((node.querySelector('[data-param="length"]') || {}).value || 0);
            } else if (op === "default_if_empty") {
                step.value = (node.querySelector('[data-param="value"]') || {}).value || "";
            }
            pipeline.push(step);
        });
        return pipeline;
    }

    function commitDomPipeline() {
        if (!activeTarget) {
            return;
        }
        syncRowPipeline(readPipelineFromDom());
    }

    function paramsHtml(op, step) {
        if (op === "date_format") {
            return (
                '<div class="field"><label>format</label>' +
                '<input type="text" data-param="format" value="' +
                escapeAttr(step.format || "%Y-%m-%d") +
                '" placeholder="%Y-%m-%d"></div>' +
                '<div class="field"><label>input_formats</label>' +
                '<input type="text" data-param="input_formats" value="' +
                escapeAttr((step.input_formats || []).join(", ")) +
                '" placeholder="%d/%m/%Y, %Y-%m-%d"></div>'
            );
        }
        if (op === "pad_left" || op === "pad_right") {
            return (
                '<div class="field"><label>char</label>' +
                '<input type="text" data-param="char" maxlength="1" value="' +
                escapeAttr(step.char || "0") +
                '"></div>' +
                '<div class="field"><label>length</label>' +
                '<input type="number" data-param="length" min="1" value="' +
                escapeAttr(step.length != null ? step.length : 5) +
                '"></div>'
            );
        }
        if (op === "default_if_empty") {
            return (
                '<div class="field"><label>value</label>' +
                '<input type="text" data-param="value" value="' +
                escapeAttr(step.value || "") +
                '"></div>'
            );
        }
        return '<span class="hint">Sin parámetros</span>';
    }

    function escapeAttr(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;");
    }

    function bindStepNode(node) {
        const opSelect = node.querySelector(".tr-step-op");
        const params = node.querySelector(".tr-step-params");
        opSelect.addEventListener("change", function () {
            params.innerHTML = paramsHtml(opSelect.value, {});
            commitDomPipeline();
            bindParamInputs(node);
        });
        bindParamInputs(node);
        node.querySelectorAll("[data-action]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const action = btn.getAttribute("data-action");
                const pipeline = readPipelineFromDom();
                const index = Number(node.getAttribute("data-index"));
                if (action === "remove") {
                    pipeline.splice(index, 1);
                } else if (action === "up" && index > 0) {
                    const tmp = pipeline[index - 1];
                    pipeline[index - 1] = pipeline[index];
                    pipeline[index] = tmp;
                } else if (action === "down" && index < pipeline.length - 1) {
                    const tmp = pipeline[index + 1];
                    pipeline[index + 1] = pipeline[index];
                    pipeline[index] = tmp;
                }
                syncRowPipeline(pipeline);
                renderSteps();
            });
        });
    }

    function bindParamInputs(node) {
        node.querySelectorAll("input").forEach(function (input) {
            input.addEventListener("change", commitDomPipeline);
            input.addEventListener("blur", commitDomPipeline);
        });
    }

    function renderSteps() {
        const row = findRow(activeTarget);
        if (addBtn) {
            addBtn.disabled = !row || !api.canEdit;
        }
        if (applyTplBtn) {
            applyTplBtn.disabled = !row || !api.canEdit;
        }
        if (templateSelect) {
            templateSelect.disabled = !row || !api.canEdit;
        }
        if (!row) {
            if (titleEl) {
                titleEl.textContent = "Seleccione un campo";
            }
            if (metaEl) {
                metaEl.textContent = "";
            }
            if (stepsEl) {
                stepsEl.innerHTML = "";
            }
            if (emptySteps) {
                emptySteps.hidden = true;
            }
            return;
        }
        if (titleEl) {
            titleEl.textContent = row.target_field;
        }
        if (metaEl) {
            metaEl.textContent = row.mapping_kind + " · " + (row.source_summary || "");
        }
        const pipeline = row.transform_pipeline || [];
        if (emptySteps) {
            emptySteps.hidden = pipeline.length > 0;
        }
        if (!stepsEl) {
            return;
        }
        stepsEl.innerHTML = "";
        pipeline.forEach(function (step, index) {
            const li = document.createElement("li");
            li.className = "tr-step";
            li.setAttribute("data-index", String(index));
            let options = "";
            opsCatalog.forEach(function (op) {
                options +=
                    '<option value="' +
                    op.code +
                    '"' +
                    (op.code === step.op ? " selected" : "") +
                    ">" +
                    op.name +
                    "</option>";
            });
            li.innerHTML =
                '<span class="tr-step-num">' +
                (index + 1) +
                "</span>" +
                '<select class="tr-step-op"' +
                (api.canEdit ? "" : " disabled") +
                ">" +
                options +
                "</select>" +
                '<div class="tr-step-params">' +
                paramsHtml(step.op, step) +
                "</div>" +
                (api.canEdit
                    ? '<div class="tr-step-actions">' +
                      '<button type="button" class="btn btn-secondary btn-sm" data-action="up">↑</button>' +
                      '<button type="button" class="btn btn-secondary btn-sm" data-action="down">↓</button>' +
                      '<button type="button" class="btn btn-secondary btn-sm" data-action="remove">×</button>' +
                      "</div>"
                    : "");
            stepsEl.appendChild(li);
            if (api.canEdit) {
                bindStepNode(li);
            }
        });
        updateStats();
    }

    function addStep() {
        if (!activeTarget || !api.canEdit) {
            return;
        }
        commitDomPipeline();
        const row = findRow(activeTarget);
        const pipeline = (row.transform_pipeline || []).slice();
        pipeline.push({ op: "trim" });
        syncRowPipeline(pipeline);
        renderSteps();
    }

    async function saveRules() {
        if (formErrors) {
            formErrors.hidden = true;
            formErrors.textContent = "";
        }
        commitDomPipeline();
        try {
            const data = await api.save({ strict: false });
            api.showUserMessage(
                "success",
                data.message || "Reglas de transformación guardadas correctamente."
            );
            renderTargets();
            renderSteps();
        } catch (err) {
            const message =
                (err && err.message) || "Revise los datos de las reglas de transformación.";
            if (formErrors) {
                formErrors.hidden = false;
                const details =
                    err && err.errors && (err.errors.transform_pipeline || err.errors.mappings);
                formErrors.textContent =
                    details && details.length ? details.join(" ") : message;
            }
            api.showUserMessage("error", message);
        }
    }

    function applyTemplate() {
        const row = findRow(activeTarget);
        if (!row || !api.canEdit || !templateSelect || !templateSelect.value) {
            return;
        }
        const tpl = pipelineTemplates.find(function (item) {
            return item.code === templateSelect.value;
        });
        if (!tpl) {
            api.showUserMessage("error", "Plantilla no encontrada.");
            return;
        }
        row.transform_pipeline = JSON.parse(JSON.stringify(tpl.pipeline || []));
        row.ops_label = (row.transform_pipeline || [])
            .map(function (step) {
                return step.op;
            })
            .join(" → ");
        if (!row.ops_label) {
            row.ops_label = "(sin reglas)";
        }
        api.setRows(api.getRows());
        renderTargets();
        renderSteps();
        api.showUserMessage("success", "Plantilla «" + (tpl.name || tpl.code) + "» aplicada.");
    }

    async function runPreview(fromSample) {
        commitDomPipeline();
        const row = findRow(activeTarget);
        if (!row) {
            previewResult.textContent = "Seleccione un campo.";
            return;
        }
        try {
            const data = await api.preview(
                previewSample.value || "",
                row.transform_pipeline || [],
                fromSample
                    ? { fromSample: true, targetField: row.target_field }
                    : {}
            );
            if (fromSample && previewSample && data.input != null) {
                previewSample.value = String(data.input);
            }
            previewResult.textContent =
                JSON.stringify(data.input) + " → " + JSON.stringify(data.output);
        } catch (err) {
            previewResult.textContent = (err && err.message) || "Error en preview.";
            api.showUserMessage("error", (err && err.message) || "Error en preview.");
        }
    }

    if (addBtn) {
        addBtn.addEventListener("click", addStep);
    }
    if (applyTplBtn) {
        applyTplBtn.addEventListener("click", applyTemplate);
    }
    if (saveBtn) {
        saveBtn.addEventListener("click", saveRules);
    }
    if (previewBtn) {
        previewBtn.addEventListener("click", function () {
            runPreview(false);
        });
    }
    if (previewSampleBtn) {
        previewSampleBtn.addEventListener("click", function () {
            runPreview(true);
        });
    }

    const rows = api.getRows();
    if (rows.length) {
        activeTarget = rows[0].target_field;
    }
    renderTargets();
    renderSteps();
})();
