/**
 * TargetProfile — Paso 4 campos posicionales (txt_fixed)
 */
(function () {
    "use strict";

    const root = document.getElementById("target-fields-root");
    if (!root || root.dataset.variant !== "fixed" || !window.dmsTargetProfile) {
        return;
    }

    const canEdit = root.dataset.canEdit === "1";
    const statusEl = document.getElementById("fields-save-status");
    const tbody = document.getElementById("target-fields-tbody");
    const form = document.getElementById("field-editor-form");
    const formTitle = document.getElementById("field-editor-title");
    const formErrors = document.getElementById("field-editor-errors");
    const btnAdd = document.getElementById("btn-add-field");
    const btnSave = document.getElementById("btn-save-field");
    const btnCancel = document.getElementById("btn-cancel-field");
    const btnDelete = document.getElementById("btn-delete-field");
    const dateFormatWrap = document.getElementById("field-date-format-wrap");

    let fields = loadFields();
    let editingIndex = null;

    function loadFields() {
        const target = window.dmsTargetProfile.getTarget() || {};
        const serverFields = target.fields;
        if (Array.isArray(serverFields) && serverFields.length) {
            return serverFields.map(cloneField);
        }
        return [];
    }

    function cloneField(item) {
        return {
            name: item.name || "",
            label: item.label || "",
            order: Number(item.order) || 1,
            data_type: item.data_type || "string",
            required: Boolean(item.required),
            start: item.start != null ? Number(item.start) : null,
            end: item.end != null ? Number(item.end) : null,
            align: item.align || "left",
            pad_char: item.pad_char != null && item.pad_char !== "" ? String(item.pad_char).slice(0, 1) : " ",
            max_length: item.max_length != null && item.max_length !== "" ? Number(item.max_length) : null,
            date_format: item.date_format || "",
        };
    }

    function isDateType(type) {
        return type === "date" || type === "datetime";
    }

    function setStatus(message, isError) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message || "";
        statusEl.classList.toggle("step-save-status--error", Boolean(isError));
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function slugRe() {
        return /^[a-z][a-z0-9_]*$/;
    }

    function syncDateFormatField() {
        if (!dateFormatWrap) {
            return;
        }
        const type = document.getElementById("field-data-type").value;
        dateFormatWrap.hidden = !isDateType(type);
    }

    function readForm() {
        const maxLengthRaw = (document.getElementById("field-max-length").value || "").trim();
        const maxLength = maxLengthRaw === "" ? null : parseInt(maxLengthRaw, 10);
        const pad = document.getElementById("field-pad-char").value;
        return {
            name: (document.getElementById("field-name").value || "").trim().toLowerCase(),
            label: (document.getElementById("field-label").value || "").trim(),
            order: parseInt(document.getElementById("field-order").value, 10),
            data_type: document.getElementById("field-data-type").value,
            required: document.getElementById("field-required").checked,
            start: parseInt(document.getElementById("field-start").value, 10),
            end: parseInt(document.getElementById("field-end").value, 10),
            align: document.getElementById("field-align").value || "left",
            pad_char: pad === "" ? " " : String(pad).slice(0, 1),
            max_length: Number.isFinite(maxLength) ? maxLength : null,
            date_format: (document.getElementById("field-date-format").value || "").trim(),
        };
    }

    function writeForm(item) {
        document.getElementById("field-name").value = item.name;
        document.getElementById("field-label").value = item.label || "";
        document.getElementById("field-order").value = item.order;
        document.getElementById("field-data-type").value = item.data_type;
        document.getElementById("field-required").checked = item.required;
        document.getElementById("field-start").value = item.start != null ? item.start : "";
        document.getElementById("field-end").value = item.end != null ? item.end : "";
        document.getElementById("field-align").value = item.align || "left";
        document.getElementById("field-pad-char").value = item.pad_char != null ? item.pad_char : " ";
        document.getElementById("field-max-length").value = item.max_length != null ? item.max_length : "";
        document.getElementById("field-date-format").value = item.date_format || "";
        syncDateFormatField();
    }

    function blankForm() {
        const nextOrder = fields.length
            ? Math.max.apply(null, fields.map(function (f) { return f.order; })) + 1
            : 1;
        const nextStart = fields.length
            ? Math.max.apply(null, fields.map(function (f) {
                return f.end != null ? f.end : (f.start || 0);
            })) + 1
            : 1;
        writeForm({
            name: "",
            label: "",
            order: nextOrder,
            data_type: "string",
            required: true,
            start: nextStart,
            end: nextStart,
            align: "left",
            pad_char: " ",
            max_length: null,
            date_format: "",
        });
    }

    function clearErrors() {
        if (!formErrors) {
            return;
        }
        formErrors.hidden = true;
        formErrors.innerHTML = "";
    }

    function showErrors(messages) {
        if (!formErrors || !messages.length) {
            return;
        }
        formErrors.hidden = false;
        formErrors.innerHTML = messages.map(function (msg) {
            return "<p>" + escapeHtml(msg) + "</p>";
        }).join("");
    }

    function validateField(data, index) {
        const errors = [];
        const warnings = [];
        if (!data.name) {
            errors.push("Ingrese el nombre del campo.");
        } else if (!slugRe().test(data.name)) {
            errors.push("El nombre debe empezar con letra minúscula y usar solo letras, números o guión bajo.");
        } else if (fields.some(function (f, i) { return i !== index && f.name === data.name; })) {
            errors.push("Ya existe un campo con el nombre «" + data.name + "».");
        }
        if (!Number.isFinite(data.order) || data.order < 1) {
            errors.push("El order debe ser un número mayor o igual a 1.");
        } else if (fields.some(function (f, i) {
            return i !== index && f.order === data.order;
        })) {
            errors.push("Ya existe un campo con el order " + data.order + ".");
        }
        if (!Number.isFinite(data.start) || data.start < 1) {
            errors.push("El inicio debe ser un número mayor o igual a 1.");
        }
        if (!Number.isFinite(data.end) || data.end < 1) {
            errors.push("El fin debe ser un número mayor o igual a 1.");
        }
        if (Number.isFinite(data.start) && Number.isFinite(data.end) && data.end < data.start) {
            errors.push("El fin debe ser mayor o igual al inicio.");
        }
        if (data.max_length != null && (!Number.isFinite(data.max_length) || data.max_length < 1)) {
            errors.push("La longitud máxima debe ser un número mayor o igual a 1.");
        }
        if (isDateType(data.data_type) && !data.date_format) {
            warnings.push("Se recomienda indicar date_format para campos de fecha u hora.");
        }
        return { errors: errors, warnings: warnings };
    }

    function setEditorMode(mode, index) {
        editingIndex = mode === "edit" ? index : null;
        const nameInput = document.getElementById("field-name");
        if (formTitle) {
            formTitle.textContent = mode === "edit" ? "Editar campo" : "Agregar campo";
        }
        if (nameInput) {
            nameInput.readOnly = mode === "edit";
        }
        if (btnDelete) {
            btnDelete.hidden = mode !== "edit";
        }
        if (btnSave) {
            btnSave.textContent = mode === "edit" ? "Guardar cambios" : "Agregar campo";
        }
    }

    function renderTable() {
        if (!tbody) {
            return;
        }
        if (!fields.length) {
            tbody.innerHTML = (
                '<tr class="fields-empty-row"><td colspan="10">'
                + "No hay campos definidos. Use «Cargar desde origen» o «+ Agregar campo»."
                + "</td></tr>"
            );
            return;
        }

        tbody.innerHTML = fields.map(function (item, index) {
            return (
                "<tr data-field-index=\"" + index + "\">"
                + "<td class=\"mono\">" + item.order + "</td>"
                + "<td class=\"mono\">" + escapeHtml(item.name) + "</td>"
                + "<td>" + escapeHtml(item.label || "—") + "</td>"
                + "<td class=\"mono\">" + (item.start != null ? item.start : "—") + "</td>"
                + "<td class=\"mono\">" + (item.end != null ? item.end : "—") + "</td>"
                + "<td><span class=\"cell-badge\">" + escapeHtml(item.align || "left") + "</span></td>"
                + "<td class=\"mono\">" + escapeHtml(item.pad_char === " " ? "␣" : (item.pad_char || "—")) + "</td>"
                + "<td><span class=\"cell-badge\">" + escapeHtml(item.data_type) + "</span></td>"
                + "<td>" + (item.required ? "Sí" : "No") + "</td>"
                + "<td class=\"col-actions\">"
                + (canEdit
                    ? "<button type=\"button\" class=\"btn btn-ghost btn-sm\" data-action=\"edit\" data-index=\"" + index + "\">Editar</button> "
                    + "<button type=\"button\" class=\"btn btn-ghost btn-sm btn-ghost--danger\" data-action=\"delete\" data-index=\"" + index + "\">Eliminar</button>"
                    : "—")
                + "</td>"
                + "</tr>"
            );
        }).join("");
    }

    function persist(payload) {
        return window.dmsTargetProfile.save(payload).then(function () {
            setStatus("Guardado correctamente.", false);
        }).catch(function (err) {
            const message = err.message || "No se pudo guardar.";
            setStatus(message, true);
            if (window.dmsTargetProfile && typeof window.dmsTargetProfile.showUserMessage === "function") {
                window.dmsTargetProfile.showUserMessage("error", message);
            } else if (typeof window.dwShowMessage === "function") {
                window.dwShowMessage("error", message);
            }
            throw err;
        });
    }

    function saveFields() {
        return persist({ fields: fields });
    }

    function openCreate() {
        clearErrors();
        blankForm();
        setEditorMode("create", null);
    }

    function openEdit(index) {
        clearErrors();
        writeForm(fields[index]);
        setEditorMode("edit", index);
    }

    function toPayload(data) {
        const payload = {
            name: data.name,
            label: data.label || data.name,
            order: data.order,
            data_type: data.data_type,
            required: data.required,
            start: data.start,
            end: data.end,
            align: data.align,
            pad_char: data.pad_char,
            date_format: data.date_format,
        };
        if (data.max_length != null) {
            payload.max_length = data.max_length;
        }
        return payload;
    }

    function saveField() {
        clearErrors();
        const data = readForm();
        const result = validateField(data, editingIndex);
        if (result.errors.length) {
            showErrors(result.errors);
            return;
        }
        const payload = toPayload(data);
        if (editingIndex === null) {
            fields.push(payload);
        } else {
            fields[editingIndex] = payload;
        }
        fields.sort(function (a, b) { return a.order - b.order; });
        renderTable();
        saveFields().then(function () {
            if (result.warnings.length && window.dmsTargetProfile) {
                window.dmsTargetProfile.showUserMessage("warning", result.warnings.join(" "));
            }
            openCreate();
        });
    }

    function deleteField(index) {
        const name = fields[index].name;
        const doDelete = function () {
            fields.splice(index, 1);
            renderTable();
            saveFields().then(function () {
                openCreate();
            });
        };
        if (typeof window.dwConfirmWarning === "function") {
            window.dwConfirmWarning(
                "¿Eliminar el campo «" + name + "»?",
                doDelete,
                { title: "Eliminar campo", okLabel: "Eliminar" }
            );
        } else if (window.confirm("¿Eliminar el campo «" + name + "»?")) {
            doDelete();
        }
    }

    const dataTypeSelect = document.getElementById("field-data-type");
    if (dataTypeSelect) {
        dataTypeSelect.addEventListener("change", syncDateFormatField);
    }
    if (btnAdd) {
        btnAdd.addEventListener("click", openCreate);
    }
    if (btnSave) {
        btnSave.addEventListener("click", function (e) {
            e.preventDefault();
            saveField();
        });
    }
    if (btnCancel) {
        btnCancel.addEventListener("click", function (e) {
            e.preventDefault();
            clearErrors();
            openCreate();
        });
    }
    if (btnDelete) {
        btnDelete.addEventListener("click", function (e) {
            e.preventDefault();
            if (editingIndex !== null) {
                deleteField(editingIndex);
            }
        });
    }
    if (tbody) {
        tbody.addEventListener("click", function (e) {
            const btn = e.target.closest("[data-action]");
            if (!btn) {
                return;
            }
            const index = parseInt(btn.dataset.index, 10);
            if (!Number.isFinite(index)) {
                return;
            }
            if (btn.dataset.action === "edit") {
                openEdit(index);
            } else if (btn.dataset.action === "delete") {
                deleteField(index);
            }
        });
    }
    if (form) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            saveField();
        });
    }

    document.addEventListener("dms:target-fields-imported", function (event) {
        const imported = (event.detail && event.detail.fields) || [];
        fields = imported.map(cloneField);
        renderTable();
        setStatus(event.detail && event.detail.message ? event.detail.message : "Campos importados.", false);
        if (canEdit && form) {
            openCreate();
        }
    });

    renderTable();
    if (canEdit && form) {
        syncDateFormatField();
        openCreate();
    }
})();
