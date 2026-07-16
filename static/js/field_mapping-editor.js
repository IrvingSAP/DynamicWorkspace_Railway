/**
 * Editor UI — Field Mapping (field_mapping.md)
 */
(function () {
    "use strict";

    const api = window.dmsFieldMapping;
    if (!api) {
        return;
    }

    const KIND_LABELS = {
        direct: "Directo",
        constant: "Constante",
        concat: "Concat",
        generated: "Generado",
        split: "Split",
        expression: "Expresión",
    };

    function readJsonScript(id, fallback) {
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

    const sourceFields = readJsonScript("dms-field-mapping-source", []);
    const targetFields = readJsonScript("dms-field-mapping-target", []);
    const suggestions = readJsonScript("dms-field-mapping-suggestions", []);
    const samplePreviewRow = readJsonScript("dms-field-mapping-sample-row", null);

    const sourceList = document.getElementById("fm-source-list");
    const targetList = document.getElementById("fm-target-list");
    const tbody = document.getElementById("fm-mappings-body");
    const emptyState = document.getElementById("fm-empty");
    const formErrors = document.getElementById("fm-form-errors");
    const dialog = document.getElementById("fm-mapping-dialog");
    const dialogErrors = document.getElementById("fm-dialog-errors");
    const previewInputs = document.getElementById("fm-preview-inputs");
    const previewErrors = document.getElementById("fm-preview-errors");
    const previewResults = document.getElementById("fm-preview-results");
    const previewBody = document.getElementById("fm-preview-body");

    const els = {
        editIndex: document.getElementById("fm-edit-index"),
        targetField: document.getElementById("fm-target-field"),
        mappingKind: document.getElementById("fm-mapping-kind"),
        sourceField: document.getElementById("fm-source-field"),
        constantValue: document.getElementById("fm-constant-value"),
        concatParts: document.getElementById("fm-concat-parts"),
        generatorType: document.getElementById("fm-generator-type"),
        genPrefix: document.getElementById("fm-gen-prefix"),
        genSuffix: document.getElementById("fm-gen-suffix"),
        genStart: document.getElementById("fm-gen-start"),
        genStep: document.getElementById("fm-gen-step"),
        genPad: document.getElementById("fm-gen-pad"),
        genPadChar: document.getElementById("fm-gen-pad-char"),
        genTemplate: document.getElementById("fm-gen-template"),
        genScope: document.getElementById("fm-gen-scope"),
        genReset: document.getElementById("fm-gen-reset"),
        dateFormat: document.getElementById("fm-date-format"),
        dateFormatWrap: document.getElementById("fm-date-format-wrap"),
        splitSource: document.getElementById("fm-split-source"),
        splitPart: document.getElementById("fm-split-part"),
        splitDelimiter: document.getElementById("fm-split-delimiter"),
        splitIndex: document.getElementById("fm-split-index"),
        splitStart: document.getElementById("fm-split-start"),
        splitLength: document.getElementById("fm-split-length"),
        splitPattern: document.getElementById("fm-split-pattern"),
        splitGroup: document.getElementById("fm-split-group"),
        exprTree: document.getElementById("fm-expr-tree"),
    };

    const EXPR_MAX_DEPTH = 5;
    const EXPR_OPS = [
        { value: "add", label: "Sumar (+)" },
        { value: "subtract", label: "Restar (−)" },
        { value: "multiply", label: "Multiplicar (×)" },
        { value: "divide", label: "Dividir (÷)" },
        { value: "concat", label: "Concatenar" },
        { value: "coalesce", label: "Coalesce" },
    ];

    function fieldName(item) {
        return String((item && item.name) || "").trim().toLowerCase();
    }

    function activeMappings() {
        return api.getMappings().filter(function (item) {
            return item && item.is_active !== false;
        });
    }

    function mappedTargets() {
        const set = {};
        activeMappings().forEach(function (item) {
            set[String(item.target_field || "").toLowerCase()] = true;
        });
        return set;
    }

    function usedSources() {
        const set = {};
        activeMappings().forEach(function (item) {
            (item.source_fields || []).forEach(function (name) {
                set[String(name).toLowerCase()] = true;
            });
            (item.parts || []).forEach(function (part) {
                if (part && part.type === "field" && part.name) {
                    set[String(part.name).toLowerCase()] = true;
                }
            });
        });
        return set;
    }

    function summarizeExpression(node) {
        if (!node || typeof node !== "object") {
            return "—";
        }
        if (Object.prototype.hasOwnProperty.call(node, "field")) {
            return String(node.field || "");
        }
        if (Object.prototype.hasOwnProperty.call(node, "literal")) {
            return JSON.stringify(node.literal);
        }
        if (node.op) {
            return (
                "(" +
                summarizeExpression(node.left) +
                " " +
                (node.op || "") +
                " " +
                summarizeExpression(node.right) +
                ")"
            );
        }
        return "—";
    }

    function summarizeMapping(item) {
        const kind = item.mapping_kind || "direct";
        if (kind === "constant") {
            return JSON.stringify(item.value || "");
        }
        if (kind === "concat") {
            return (item.parts || [])
                .map(function (part) {
                    return part.type === "literal"
                        ? '"' + (part.value || "") + '"'
                        : part.name || "";
                })
                .join(" + ");
        }
        if (kind === "generated") {
            const gen = item.generator || {};
            return gen.type || "generated";
        }
        if (kind === "split") {
            const split = item.split || {};
            return (
                (item.source_fields || []).join(", ") +
                " → " +
                (split.part || "split")
            );
        }
        if (kind === "expression") {
            return summarizeExpression(item.expression || {});
        }
        return (item.source_fields || []).join(", ") || "—";
    }

    function pipelineLabel(item) {
        const pipe = item.transform_pipeline || [];
        if (!pipe.length) {
            return "—";
        }
        return pipe
            .map(function (step) {
                return step.op || "";
            })
            .filter(Boolean)
            .join(", ");
    }

    function setStat(id, value) {
        const node = document.getElementById(id);
        if (node) {
            node.textContent = String(value);
        }
    }

    function addDirectMapping(sourceName, targetName) {
        const mapped = mappedTargets();
        if (mapped[String(targetName).toLowerCase()]) {
            api.showUserMessage(
                "warning",
                "Ya existe un mapeo activo para «" + targetName + "»."
            );
            return false;
        }
        const mappings = api.getMappings();
        mappings.push({
            target_field: targetName,
            mapping_kind: "direct",
            source_fields: [sourceName],
            transform_pipeline: [{ op: "trim" }],
            sort_order: mappings.length + 1,
            is_active: true,
        });
        mappings.forEach(function (item, idx) {
            item.sort_order = idx + 1;
        });
        api.setMappings(mappings);
        renderTable();
        api.showUserMessage(
            "success",
            "Mapeo directo «" + sourceName + "» → «" + targetName + "»."
        );
        return true;
    }

    function bindTargetDrop(li, targetName) {
        if (!api.canEdit) {
            return;
        }
        li.classList.add("is-drop-target");
        li.setAttribute("data-target-name", targetName);
        li.addEventListener("dragover", function (event) {
            event.preventDefault();
            li.classList.add("is-dragover");
        });
        li.addEventListener("dragleave", function () {
            li.classList.remove("is-dragover");
        });
        li.addEventListener("drop", function (event) {
            event.preventDefault();
            li.classList.remove("is-dragover");
            const sourceName = (
                event.dataTransfer.getData("text/plain") || ""
            ).trim();
            if (!sourceName) {
                return;
            }
            addDirectMapping(sourceName, targetName);
        });
    }

    function renderSideLists() {
        const mapped = mappedTargets();
        const used = usedSources();
        let unmapped = 0;
        let unused = 0;
        let requiredPending = 0;

        if (sourceList) {
            sourceList.innerHTML = "";
            sourceFields.forEach(function (field) {
                const name = fieldName(field);
                const isUsed = !!used[name];
                if (!isUsed) {
                    unused += 1;
                }
                const li = document.createElement("li");
                li.className =
                    "fm-field-item" +
                    (isUsed ? " is-mapped" : " is-unused") +
                    (api.canEdit ? " is-draggable" : "");
                li.setAttribute("data-source-name", name);
                if (api.canEdit) {
                    li.draggable = true;
                    li.addEventListener("dragstart", function (event) {
                        event.dataTransfer.setData("text/plain", name);
                        event.dataTransfer.effectAllowed = "copy";
                    });
                }
                li.innerHTML =
                    '<span class="fm-field-name"></span><span class="fm-field-meta"></span>';
                li.querySelector(".fm-field-name").textContent = field.name || name;
                li.querySelector(".fm-field-meta").textContent =
                    (field.label || field.content_type || "") +
                    (isUsed ? "" : " · sin usar");
                sourceList.appendChild(li);
            });
        }

        if (targetList) {
            targetList.innerHTML = "";
            targetFields.forEach(function (field) {
                const name = fieldName(field);
                const isMapped = !!mapped[name];
                const required = !!field.required;
                if (!isMapped) {
                    unmapped += 1;
                    if (
                        required &&
                        (field.default_value === null ||
                            field.default_value === undefined ||
                            field.default_value === "")
                    ) {
                        requiredPending += 1;
                    }
                }
                const li = document.createElement("li");
                li.className =
                    "fm-field-item" +
                    (isMapped
                        ? " is-mapped"
                        : required
                          ? " is-required-unmapped"
                          : "");
                li.innerHTML =
                    '<span class="fm-field-name"></span><span class="fm-field-meta"></span>';
                li.querySelector(".fm-field-name").textContent = field.name || name;
                li.querySelector(".fm-field-meta").textContent =
                    (field.label || field.data_type || "") +
                    (required ? " · obligatorio" : "") +
                    (isMapped ? "" : " · sin mapeo");
                bindTargetDrop(li, name);
                targetList.appendChild(li);
            });
        }

        setStat("fm-stat-mappings", activeMappings().length);
        setStat("fm-stat-unmapped", unmapped);
        setStat("fm-stat-unused", unused);
        setStat("fm-stat-required", requiredPending);
    }

    function renderTable() {
        const mappings = api.getMappings();
        if (!tbody) {
            return;
        }
        tbody.innerHTML = "";
        if (emptyState) {
            emptyState.hidden = mappings.length > 0;
        }
        mappings.forEach(function (item, index) {
            const tr = document.createElement("tr");
            if (item.is_active === false) {
                tr.style.opacity = "0.55";
            }
            tr.innerHTML =
                '<td><strong class="fm-target"></strong></td>' +
                '<td><span class="fm-kind-badge"></span></td>' +
                '<td><span class="fm-source-summary"></span></td>' +
                '<td><span class="fm-source-summary fm-pipe"></span></td>' +
                '<td class="fm-row-actions"></td>';
            tr.querySelector(".fm-target").textContent = item.target_field || "—";
            tr.querySelector(".fm-kind-badge").textContent =
                KIND_LABELS[item.mapping_kind] || item.mapping_kind || "—";
            tr.querySelector(".fm-source-summary").textContent = summarizeMapping(item);
            tr.querySelector(".fm-pipe").textContent = pipelineLabel(item);

            const actions = tr.querySelector(".fm-row-actions");
            if (api.canEdit) {
                const editBtn = document.createElement("button");
                editBtn.type = "button";
                editBtn.className = "btn btn-secondary btn-sm";
                editBtn.textContent = "Editar";
                editBtn.addEventListener("click", function () {
                    openDialog(index);
                });
                const delBtn = document.createElement("button");
                delBtn.type = "button";
                delBtn.className = "btn btn-secondary btn-sm";
                delBtn.textContent = "Quitar";
                delBtn.addEventListener("click", function () {
                    removeMapping(index);
                });
                actions.appendChild(editBtn);
                actions.appendChild(delBtn);
            }
            tbody.appendChild(tr);
        });
        renderSideLists();
    }

    function fillSelect(select, options, selected) {
        if (!select) {
            return;
        }
        select.innerHTML = "";
        options.forEach(function (opt) {
            const option = document.createElement("option");
            option.value = opt.value;
            option.textContent = opt.label;
            if (opt.value === selected) {
                option.selected = true;
            }
            select.appendChild(option);
        });
    }

    function showKindPanels(kind) {
        document.querySelectorAll(".fm-kind-panel").forEach(function (panel) {
            panel.hidden = panel.getAttribute("data-kind") !== kind;
        });
        updateSplitParamsVisibility();
    }

    function updateSplitParamsVisibility() {
        const part = (els.splitPart && els.splitPart.value) || "first_word";
        const delim = document.getElementById("fm-split-params-delimiter");
        const sub = document.getElementById("fm-split-params-substring");
        const regex = document.getElementById("fm-split-params-regex");
        if (delim) {
            delim.hidden = part !== "delimiter";
        }
        if (sub) {
            sub.hidden = part !== "substring";
        }
        if (regex) {
            regex.hidden = part !== "regex";
        }
    }

    function defaultExprNode() {
        return {
            op: "multiply",
            left: { field: "" },
            right: { literal: 1 },
        };
    }

    function detectOperandKind(node) {
        if (!node || typeof node !== "object") {
            return "literal";
        }
        if (node.op) {
            return "expression";
        }
        if (Object.prototype.hasOwnProperty.call(node, "field")) {
            return "field";
        }
        return "literal";
    }

    function renderExprTree(rootNode) {
        if (!els.exprTree) {
            return;
        }
        els.exprTree.innerHTML = "";
        els.exprTree.appendChild(buildExprEditor(rootNode || defaultExprNode(), 0));
    }

    function buildExprEditor(node, depth) {
        const wrap = document.createElement("div");
        wrap.className = "fm-expr-node";
        wrap.setAttribute("data-depth", String(depth));

        const head = document.createElement("div");
        head.className = "fm-expr-node-head";

        const kindSel = document.createElement("select");
        kindSel.className = "fm-expr-kind";
        [
            { value: "expression", label: "Expresión" },
            { value: "field", label: "Campo" },
            { value: "literal", label: "Literal" },
        ].forEach(function (opt) {
            const option = document.createElement("option");
            option.value = opt.value;
            option.textContent = opt.label;
            kindSel.appendChild(option);
        });
        const initialKind = detectOperandKind(node);
        kindSel.value = depth === 0 ? "expression" : initialKind;
        if (depth === 0) {
            kindSel.disabled = true;
        }
        head.appendChild(kindSel);

        const opSel = document.createElement("select");
        opSel.className = "fm-expr-op";
        EXPR_OPS.forEach(function (opt) {
            const option = document.createElement("option");
            option.value = opt.value;
            option.textContent = opt.label;
            opSel.appendChild(option);
        });
        opSel.value = (node && node.op) || "multiply";
        head.appendChild(opSel);

        const fieldSel = document.createElement("select");
        fieldSel.className = "fm-expr-field";
        fillSelect(fieldSel, sourceSelectOptions(), (node && node.field) || "");
        head.appendChild(fieldSel);

        const litInput = document.createElement("input");
        litInput.type = "text";
        litInput.className = "fm-expr-literal";
        litInput.autocomplete = "off";
        litInput.value =
            node && Object.prototype.hasOwnProperty.call(node, "literal")
                ? String(node.literal)
                : "";
        head.appendChild(litInput);

        wrap.appendChild(head);

        const children = document.createElement("div");
        children.className = "fm-expr-children";
        const leftBox = document.createElement("div");
        const rightBox = document.createElement("div");
        const leftLabel = document.createElement("div");
        leftLabel.className = "fm-expr-child-label";
        leftLabel.textContent = "Izquierda";
        const rightLabel = document.createElement("div");
        rightLabel.className = "fm-expr-child-label";
        rightLabel.textContent = "Derecha";
        leftBox.appendChild(leftLabel);
        rightBox.appendChild(rightLabel);
        children.appendChild(leftBox);
        children.appendChild(rightBox);
        wrap.appendChild(children);

        function syncKindUI() {
            const kind = kindSel.value;
            const isExpr = kind === "expression";
            const isField = kind === "field";
            opSel.hidden = !isExpr;
            fieldSel.hidden = !isField;
            litInput.hidden = isExpr || isField;
            children.hidden = !isExpr;
            if (isExpr && !leftBox.querySelector(".fm-expr-node") && depth + 1 < EXPR_MAX_DEPTH) {
                leftBox.appendChild(
                    buildExprEditor((node && node.left) || { field: "" }, depth + 1)
                );
                rightBox.appendChild(
                    buildExprEditor((node && node.right) || { literal: "" }, depth + 1)
                );
            }
            if (!isExpr) {
                leftBox.querySelectorAll(".fm-expr-node").forEach(function (child) {
                    child.remove();
                });
                rightBox.querySelectorAll(".fm-expr-node").forEach(function (child) {
                    child.remove();
                });
            }
        }

        kindSel.addEventListener("change", function () {
            if (kindSel.value === "expression" && depth + 1 >= EXPR_MAX_DEPTH) {
                kindSel.value = "literal";
                showDialogErrors("Profundidad máxima de expresión: " + EXPR_MAX_DEPTH + ".");
                return;
            }
            if (kindSel.value === "expression") {
                leftBox.querySelectorAll(".fm-expr-node").forEach(function (child) {
                    child.remove();
                });
                rightBox.querySelectorAll(".fm-expr-node").forEach(function (child) {
                    child.remove();
                });
                leftBox.appendChild(buildExprEditor({ field: "" }, depth + 1));
                rightBox.appendChild(buildExprEditor({ literal: "" }, depth + 1));
            }
            syncKindUI();
        });

        if (initialKind === "expression" || depth === 0) {
            leftBox.appendChild(
                buildExprEditor((node && node.left) || { field: "" }, depth + 1)
            );
            rightBox.appendChild(
                buildExprEditor((node && node.right) || { literal: 1 }, depth + 1)
            );
        }
        syncKindUI();
        return wrap;
    }

    function readExprNode(wrap) {
        if (!wrap) {
            return null;
        }
        const kindSel = wrap.querySelector(":scope > .fm-expr-node-head > .fm-expr-kind");
        const opSel = wrap.querySelector(":scope > .fm-expr-node-head > .fm-expr-op");
        const fieldSel = wrap.querySelector(":scope > .fm-expr-node-head > .fm-expr-field");
        const litInput = wrap.querySelector(":scope > .fm-expr-node-head > .fm-expr-literal");
        const kind = kindSel ? kindSel.value : "literal";
        if (kind === "field") {
            if (!fieldSel || !fieldSel.value) {
                return null;
            }
            return { field: fieldSel.value };
        }
        if (kind === "literal") {
            let literal = litInput ? litInput.value : "";
            if (literal !== "" && !Number.isNaN(Number(literal))) {
                literal = Number(literal);
            }
            return { literal: literal };
        }
        const children = wrap.querySelector(":scope > .fm-expr-children");
        const childNodes = children
            ? children.querySelectorAll(":scope > div > .fm-expr-node")
            : [];
        const left = readExprNode(childNodes[0]);
        const right = readExprNode(childNodes[1]);
        if (!left || !right) {
            return null;
        }
        return {
            op: (opSel && opSel.value) || "multiply",
            left: left,
            right: right,
        };
    }

    function clearDialogErrors() {
        if (!dialogErrors) {
            return;
        }
        dialogErrors.hidden = true;
        dialogErrors.textContent = "";
    }

    function showDialogErrors(text) {
        if (!dialogErrors) {
            return;
        }
        dialogErrors.hidden = false;
        dialogErrors.textContent = text;
    }

    function addConcatRow(part) {
        const row = document.createElement("div");
        row.className = "fm-concat-row";
        const type = (part && part.type) || "literal";
        row.innerHTML =
            '<select class="fm-concat-type">' +
            '<option value="literal">Literal</option>' +
            '<option value="field">Campo</option>' +
            "</select>" +
            '<input type="text" class="fm-concat-value" autocomplete="off">' +
            '<button type="button" class="btn btn-secondary btn-sm fm-concat-remove">×</button>';
        const typeSel = row.querySelector(".fm-concat-type");
        const valueInput = row.querySelector(".fm-concat-value");
        typeSel.value = type;
        if (type === "field") {
            const select = document.createElement("select");
            select.className = "fm-concat-value";
            fillSelect(
                select,
                sourceFields.map(function (field) {
                    return { value: fieldName(field), label: field.name || fieldName(field) };
                }),
                (part && part.name) || ""
            );
            valueInput.replaceWith(select);
        } else {
            valueInput.value = (part && part.value) || "";
        }
        typeSel.addEventListener("change", function () {
            const current = row.querySelector(".fm-concat-value");
            if (typeSel.value === "field") {
                const select = document.createElement("select");
                select.className = "fm-concat-value";
                fillSelect(
                    select,
                    sourceFields.map(function (field) {
                        return {
                            value: fieldName(field),
                            label: field.name || fieldName(field),
                        };
                    }),
                    ""
                );
                current.replaceWith(select);
            } else {
                const input = document.createElement("input");
                input.type = "text";
                input.className = "fm-concat-value";
                input.autocomplete = "off";
                current.replaceWith(input);
            }
        });
        row.querySelector(".fm-concat-remove").addEventListener("click", function () {
            row.remove();
        });
        els.concatParts.appendChild(row);
    }

    function readConcatParts() {
        const parts = [];
        els.concatParts.querySelectorAll(".fm-concat-row").forEach(function (row) {
            const type = row.querySelector(".fm-concat-type").value;
            const valueNode = row.querySelector(".fm-concat-value");
            if (type === "literal") {
                parts.push({ type: "literal", value: valueNode.value || "" });
            } else if (valueNode.value) {
                parts.push({ type: "field", name: valueNode.value });
            }
        });
        return parts;
    }

    function readPipeline() {
        const pipe = [];
        document.querySelectorAll("#fm-transforms input[type=checkbox]").forEach(function (box) {
            if (!box.checked) {
                return;
            }
            const step = { op: box.value };
            if (box.value === "date_format") {
                step.format = (els.dateFormat && els.dateFormat.value.trim()) || "%Y-%m-%d";
            } else if (box.value === "pad_left" || box.value === "pad_right") {
                step.char = "0";
                step.length = 5;
            } else if (box.value === "default_if_empty") {
                step.value = "";
            }
            pipe.push(step);
        });
        return pipe;
    }

    function setPipeline(pipeline) {
        const ops = {};
        (pipeline || []).forEach(function (step) {
            ops[step.op] = step;
        });
        document.querySelectorAll("#fm-transforms input[type=checkbox]").forEach(function (box) {
            box.checked = !!ops[box.value];
        });
        const dateStep = ops.date_format;
        els.dateFormat.value = dateStep && dateStep.format ? dateStep.format : "";
        updateDateFormatVisibility();
    }

    function updateDateFormatVisibility() {
        const box = document.querySelector('#fm-transforms input[value="date_format"]');
        els.dateFormatWrap.hidden = !(box && box.checked);
    }

    function sourceSelectOptions() {
        return sourceFields.map(function (field) {
            return { value: fieldName(field), label: field.name || fieldName(field) };
        });
    }

    function collectExpressionFields(node, acc) {
        if (!node || typeof node !== "object") {
            return;
        }
        if (node.field) {
            acc.push(String(node.field).toLowerCase());
            return;
        }
        if (node.op) {
            collectExpressionFields(node.left, acc);
            collectExpressionFields(node.right, acc);
        }
    }

    function openDialog(index) {
        clearDialogErrors();
        const mappings = api.getMappings();
        const isNew = index < 0;
        const item = isNew
            ? {
                  target_field: "",
                  mapping_kind: "direct",
                  source_fields: [],
                  transform_pipeline: [{ op: "trim" }],
                  is_active: true,
              }
            : mappings[index] || {};

        els.editIndex.value = String(index);
        fillSelect(
            els.targetField,
            targetFields.map(function (field) {
                return { value: fieldName(field), label: field.name || fieldName(field) };
            }),
            item.target_field || ""
        );
        els.mappingKind.value = item.mapping_kind || "direct";
        fillSelect(
            els.sourceField,
            sourceSelectOptions(),
            (item.source_fields && item.source_fields[0]) || ""
        );
        fillSelect(
            els.splitSource,
            sourceSelectOptions(),
            (item.source_fields && item.source_fields[0]) || ""
        );
        els.constantValue.value = item.value || "";
        els.concatParts.innerHTML = "";
        (item.parts || []).forEach(addConcatRow);
        if (!(item.parts || []).length && (item.mapping_kind || "") === "concat") {
            addConcatRow({ type: "literal", value: "" });
        }
        const gen = item.generator || {};
        els.generatorType.value = gen.type || "sequence_numeric";
        els.genPrefix.value = gen.prefix || "";
        if (els.genSuffix) {
            els.genSuffix.value = gen.suffix || "";
        }
        els.genStart.value = gen.start != null ? gen.start : 1;
        if (els.genStep) {
            els.genStep.value = gen.step != null ? gen.step : 1;
        }
        els.genPad.value = gen.pad_length != null ? gen.pad_length : 0;
        if (els.genPadChar) {
            els.genPadChar.value = gen.pad_char || "0";
        }
        els.genTemplate.value = gen.template || "";
        if (els.genScope) {
            els.genScope.value = gen.scope || "job";
        }
        if (els.genReset) {
            els.genReset.checked = gen.reset_per_job !== false;
        }

        const split = item.split || {};
        if (els.splitPart) {
            els.splitPart.value = split.part || "first_word";
        }
        if (els.splitDelimiter) {
            els.splitDelimiter.value =
                split.delimiter != null ? String(split.delimiter) : " ";
        }
        if (els.splitIndex) {
            els.splitIndex.value = split.index != null ? split.index : 0;
        }
        if (els.splitStart) {
            els.splitStart.value = split.start != null ? split.start : 0;
        }
        if (els.splitLength) {
            els.splitLength.value = split.length != null ? split.length : 1;
        }
        if (els.splitPattern) {
            els.splitPattern.value = split.pattern || "";
        }
        if (els.splitGroup) {
            els.splitGroup.value = split.group != null ? split.group : 0;
        }

        renderExprTree(item.expression || defaultExprNode());

        setPipeline(item.transform_pipeline || []);
        showKindPanels(els.mappingKind.value);
        if (typeof dialog.showModal === "function") {
            dialog.showModal();
        }
    }

    function buildMappingFromForm() {
        const kind = els.mappingKind.value;
        const target = els.targetField.value;
        if (!target) {
            showDialogErrors("Seleccione un campo destino.");
            return null;
        }
        const mapping = {
            target_field: target,
            mapping_kind: kind,
            source_fields: [],
            transform_pipeline: readPipeline(),
            sort_order: 0,
            is_active: true,
        };
        if (kind === "direct") {
            if (!els.sourceField.value) {
                showDialogErrors("Seleccione un campo origen.");
                return null;
            }
            mapping.source_fields = [els.sourceField.value];
        } else if (kind === "constant") {
            mapping.value = els.constantValue.value;
            if (!mapping.value) {
                showDialogErrors("Indique el valor constante.");
                return null;
            }
        } else if (kind === "concat") {
            mapping.parts = readConcatParts();
            if (!mapping.parts.length) {
                showDialogErrors("Añada al menos una parte en concat.");
                return null;
            }
            mapping.source_fields = mapping.parts
                .filter(function (part) {
                    return part.type === "field";
                })
                .map(function (part) {
                    return part.name;
                });
        } else if (kind === "generated") {
            mapping.generator = {
                type: els.generatorType.value,
                prefix: els.genPrefix.value || undefined,
                suffix: (els.genSuffix && els.genSuffix.value) || undefined,
                start: Number(els.genStart.value || 1),
                step: Number((els.genStep && els.genStep.value) || 1),
                pad_length: Number(els.genPad.value || 0) || undefined,
                pad_char: (els.genPadChar && els.genPadChar.value) || undefined,
                template: els.genTemplate.value || undefined,
                scope: (els.genScope && els.genScope.value) || "job",
                reset_per_job: !els.genReset || els.genReset.checked,
            };
        } else if (kind === "split") {
            if (!els.splitSource || !els.splitSource.value) {
                showDialogErrors("Seleccione un campo origen para split.");
                return null;
            }
            const part = els.splitPart.value || "first_word";
            const split = { part: part };
            if (part === "delimiter") {
                split.delimiter = els.splitDelimiter.value;
                split.index = Number(els.splitIndex.value || 0);
            } else if (part === "substring") {
                split.start = Number(els.splitStart.value || 0);
                split.length = Number(els.splitLength.value || 1);
            } else if (part === "regex") {
                if (!els.splitPattern.value) {
                    showDialogErrors("Indique el patrón regex.");
                    return null;
                }
                split.pattern = els.splitPattern.value;
                split.group = Number(els.splitGroup.value || 0);
            }
            mapping.source_fields = [els.splitSource.value];
            mapping.split = split;
        } else if (kind === "expression") {
            const root = els.exprTree
                ? els.exprTree.querySelector(":scope > .fm-expr-node")
                : null;
            const expression = readExprNode(root);
            if (!expression || !expression.op) {
                showDialogErrors("Complete la expresión (operador y operandos).");
                return null;
            }
            mapping.expression = expression;
            const fields = [];
            collectExpressionFields(mapping.expression, fields);
            mapping.source_fields = fields.filter(function (name, idx, arr) {
                return arr.indexOf(name) === idx;
            });
        } else {
            showDialogErrors("Este tipo de enlace aún no está habilitado.");
            return null;
        }
        return mapping;
    }

    function applyDialog() {
        const mapping = buildMappingFromForm();
        if (!mapping) {
            return;
        }
        const index = Number(els.editIndex.value);
        const mappings = api.getMappings();
        const duplicate = mappings.findIndex(function (item, idx) {
            return (
                idx !== index &&
                item.is_active !== false &&
                String(item.target_field || "").toLowerCase() === mapping.target_field
            );
        });
        if (duplicate >= 0) {
            showDialogErrors("Ya existe un mapeo activo para ese destino.");
            return;
        }
        if (index >= 0 && index < mappings.length) {
            mappings[index] = mapping;
        } else {
            mappings.push(mapping);
        }
        mappings.forEach(function (item, idx) {
            item.sort_order = idx + 1;
        });
        api.setMappings(mappings);
        renderTable();
        dialog.close();
    }

    function removeMapping(index) {
        const mappings = api.getMappings();
        mappings.splice(index, 1);
        mappings.forEach(function (item, idx) {
            item.sort_order = idx + 1;
        });
        api.setMappings(mappings);
        renderTable();
    }

    function applySuggestions() {
        const current = api.getMappings();
        const mapped = mappedTargets();
        const next = current.slice();
        suggestions.forEach(function (item) {
            const target = String(item.target_field || "").toLowerCase();
            if (!target || mapped[target]) {
                return;
            }
            next.push(Object.assign({}, item));
            mapped[target] = true;
        });
        next.forEach(function (item, idx) {
            item.sort_order = idx + 1;
        });
        api.setMappings(next);
        renderTable();
        const added = next.length - current.length;
        api.showUserMessage(
            "success",
            added
                ? "Se añadieron " + added + " sugerencias por nombre igual."
                : "No hay nuevos nombres coincidentes para sugerir."
        );
    }

    async function saveMappings() {
        if (formErrors) {
            formErrors.hidden = true;
            formErrors.textContent = "";
        }
        try {
            const data = await api.save(api.getMappings(), { strict: false });
            api.showUserMessage("success", data.message || "Mapeo de campos guardado correctamente.");
            renderTable();
        } catch (err) {
            const message = (err && err.message) || "Revise los datos del mapeo de campos.";
            if (formErrors) {
                formErrors.hidden = false;
                const details = err && err.errors && err.errors.mappings;
                formErrors.textContent = details && details.length ? details.join(" ") : message;
            }
            api.showUserMessage("error", message);
        }
    }

    function renderPreviewInputs(values) {
        if (!previewInputs) {
            return;
        }
        previewInputs.innerHTML = "";
        const vals = values || {};
        sourceFields.forEach(function (field) {
            const name = fieldName(field);
            const wrap = document.createElement("div");
            wrap.className = "field";
            const label = document.createElement("label");
            label.textContent = field.name || name;
            const input = document.createElement("input");
            input.type = "text";
            input.className = "fm-preview-input";
            input.setAttribute("data-source-name", name);
            input.value =
                vals[name] != null
                    ? String(vals[name])
                    : vals[field.name] != null
                      ? String(vals[field.name])
                      : "";
            wrap.appendChild(label);
            wrap.appendChild(input);
            previewInputs.appendChild(wrap);
        });
    }

    function readPreviewRow() {
        const row = {};
        document.querySelectorAll(".fm-preview-input").forEach(function (input) {
            const name = input.getAttribute("data-source-name");
            if (name) {
                row[name] = input.value;
            }
        });
        return row;
    }

    async function runPreview() {
        if (!api.preview) {
            return;
        }
        if (previewErrors) {
            previewErrors.hidden = true;
            previewErrors.textContent = "";
        }
        try {
            const data = await api.preview(api.getMappings(), readPreviewRow(), 1);
            if (previewBody) {
                previewBody.innerHTML = "";
                const targetRow = data.target_row || {};
                Object.keys(targetRow).forEach(function (key) {
                    const tr = document.createElement("tr");
                    tr.innerHTML = "<td></td><td></td>";
                    tr.children[0].textContent = key;
                    tr.children[1].textContent =
                        targetRow[key] == null ? "" : String(targetRow[key]);
                    previewBody.appendChild(tr);
                });
            }
            if (previewResults) {
                previewResults.hidden = false;
            }
            const errs = data.row_errors || [];
            if (errs.length && previewErrors) {
                previewErrors.hidden = false;
                previewErrors.textContent = errs
                    .map(function (err) {
                        return (err.field || "") + ": " + (err.message || "");
                    })
                    .join(" ");
            }
            api.showUserMessage("success", data.message || "Preview listo.");
        } catch (err) {
            const message = (err && err.message) || "No se pudo generar el preview.";
            if (previewErrors) {
                previewErrors.hidden = false;
                previewErrors.textContent = message;
            }
            api.showUserMessage("error", message);
        }
    }

    function bind() {
        const addBtn = document.getElementById("fm-add-btn");
        const saveBtn = document.getElementById("fm-save-btn");
        const suggestBtn = document.getElementById("fm-suggest-btn");
        const applyBtn = document.getElementById("fm-dialog-apply");
        const previewBtn = document.getElementById("fm-preview-run");
        const sampleBtn = document.getElementById("fm-preview-sample");
        if (addBtn) {
            addBtn.addEventListener("click", function () {
                openDialog(-1);
            });
        }
        if (saveBtn) {
            saveBtn.addEventListener("click", function () {
                saveMappings();
            });
        }
        if (suggestBtn) {
            suggestBtn.addEventListener("click", applySuggestions);
        }
        if (applyBtn) {
            applyBtn.addEventListener("click", applyDialog);
        }
        if (previewBtn) {
            previewBtn.addEventListener("click", runPreview);
        }
        if (sampleBtn && samplePreviewRow) {
            sampleBtn.addEventListener("click", function () {
                renderPreviewInputs(samplePreviewRow);
                api.showUserMessage("success", "Fila muestra cargada en el preview.");
            });
        }
        if (els.mappingKind) {
            els.mappingKind.addEventListener("change", function () {
                showKindPanels(els.mappingKind.value);
            });
        }
        if (els.splitPart) {
            els.splitPart.addEventListener("change", updateSplitParamsVisibility);
        }
        document.querySelectorAll("#fm-transforms input[type=checkbox]").forEach(function (box) {
            box.addEventListener("change", updateDateFormatVisibility);
        });
        const addLiteral = document.getElementById("fm-concat-add-literal");
        const addField = document.getElementById("fm-concat-add-field");
        if (addLiteral) {
            addLiteral.addEventListener("click", function () {
                addConcatRow({ type: "literal", value: "" });
            });
        }
        if (addField) {
            addField.addEventListener("click", function () {
                addConcatRow({ type: "field", name: "" });
            });
        }
    }

    bind();
    renderPreviewInputs({});
    renderTable();
})();
