/**
 * SourceProfile — Paso 4 campos Excel (xlsx)
 */
(function () {
    "use strict";

    const root = document.getElementById("source-fields-xlsx-root");
    if (!root || !window.dmsSourceProfile) {
        return;
    }

    const canEdit = root.dataset.canEdit === "1";
    const statusEl = document.getElementById("xlsx-save-status");
    const configNode = document.getElementById("xlsx-config-default");
    const tbody = document.getElementById("source-fields-tbody");
    const form = document.getElementById("field-editor-form");
    const formTitle = document.getElementById("field-editor-title");
    const formErrors = document.getElementById("field-editor-errors");
    const btnAdd = document.getElementById("btn-add-field");
    const btnSave = document.getElementById("btn-save-field");
    const btnCancel = document.getElementById("btn-cancel-field");
    const btnDelete = document.getElementById("btn-delete-field");
    const btnSaveConfig = document.getElementById("btn-save-xlsx-config");
    const dateFormatWrap = document.getElementById("field-date-format-wrap");

    let config = loadConfig();
    let fields = loadFields();
    let editingIndex = null;

    function loadConfig() {
        const source = window.dmsSourceProfile.getSource() || {};
        const fromServer = source.config || {};
        let defaults = {};
        if (configNode) {
            try {
                defaults = JSON.parse(configNode.textContent || "{}");
            } catch (_err) {
                defaults = {};
            }
        }
        return Object.assign({}, defaults, fromServer);
    }

    function loadFields() {
        const source = window.dmsSourceProfile.getSource() || {};
        const serverFields = source.fields;
        if (Array.isArray(serverFields) && serverFields.length) {
            return serverFields.map(cloneField);
        }
        return [];
    }

    function cloneField(item) {
        return {
            name: item.name || "",
            column: (item.column || "").toString().toUpperCase(),
            content_type: item.content_type || "free_text",
            required: Boolean(item.required),
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

    function readConfigForm() {
        return {
            sheet_name: (document.getElementById("sheet_name").value || "").trim(),
            header_row: parseInt(document.getElementById("header_row").value, 10) || 1,
        };
    }

    function writeConfigForm() {
        document.getElementById("sheet_name").value = config.sheet_name || "Hoja1";
        document.getElementById("header_row").value = config.header_row || 1;
    }

    function readForm() {
        return {
            name: (document.getElementById("field-name").value || "").trim().toLowerCase(),
            column: (document.getElementById("field-column").value || "").trim().toUpperCase(),
            content_type: document.getElementById("field-content-type").value,
            required: document.getElementById("field-required").checked,
            date_format: (document.getElementById("field-date-format").value || "").trim(),
        };
    }

    function writeForm(item) {
        document.getElementById("field-name").value = item.name;
        document.getElementById("field-column").value = item.column;
        document.getElementById("field-content-type").value = item.content_type;
        document.getElementById("field-required").checked = item.required;
        document.getElementById("field-date-format").value = item.date_format || "";
        syncDateFormatField();
    }

    function blankForm() {
        writeForm({
            name: "",
            column: "",
            content_type: "numeric",
            required: true,
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
        if (!data.name) {
            errors.push("Ingrese el nombre interno del campo.");
        } else if (!slugRe().test(data.name)) {
            errors.push("El nombre debe empezar con letra minúscula y usar solo letras, números o guión bajo.");
        } else if (fields.some(function (f, i) { return i !== index && f.name === data.name; })) {
            errors.push("Ya existe un campo con el nombre «" + data.name + "».");
        }
        if (!data.column) {
            errors.push("Indique la columna de Excel.");
        } else if (fields.some(function (f, i) {
            return i !== index && f.column === data.column;
        })) {
            errors.push("Ya existe un campo con la columna «" + data.column + "».");
        }
        if (isDateType(data.content_type) && !data.date_format) {
            errors.push("Indique date_format para campos de fecha u hora.");
        }
        return errors;
    }

    function syncDateFormatField() {
        if (!dateFormatWrap) {
            return;
        }
        const type = document.getElementById("field-content-type").value;
        dateFormatWrap.hidden = !isDateType(type);
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
                '<tr class="fields-empty-row"><td colspan="5">'
                + "No hay campos definidos. Use «+ Agregar campo» para comenzar."
                + "</td></tr>"
            );
            return;
        }

        tbody.innerHTML = fields.map(function (item, index) {
            return (
                "<tr data-field-index=\"" + index + "\">"
                + "<td class=\"mono\">" + escapeHtml(item.column) + "</td>"
                + "<td class=\"mono\">" + escapeHtml(item.name) + "</td>"
                + "<td><span class=\"cell-badge\">" + escapeHtml(item.content_type) + "</span></td>"
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
        return window.dmsSourceProfile.save(payload).then(function () {
            setStatus("Guardado correctamente.", false);
        }).catch(function (err) {
            const message = err.message || "No se pudo guardar.";
            setStatus(message, true);
            if (window.dmsSourceProfile && typeof window.dmsSourceProfile.showUserMessage === "function") {
                window.dmsSourceProfile.showUserMessage("error", message);
            } else if (typeof window.dwShowMessage === "function") {
                window.dwShowMessage("error", message);
            }
            throw err;
        });
    }

    function saveConfig() {
        if (!canEdit) {
            return Promise.resolve();
        }
        config = readConfigForm();
        if (!config.sheet_name) {
            setStatus("Indique el nombre de la hoja.", true);
            return Promise.reject(new Error("Indique el nombre de la hoja."));
        }
        return persist({ config: config });
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

    function saveField() {
        clearErrors();
        const data = readForm();
        const errors = validateField(data, editingIndex);
        if (errors.length) {
            showErrors(errors);
            return;
        }
        if (editingIndex === null) {
            fields.push(data);
        } else {
            fields[editingIndex] = data;
        }
        renderTable();
        saveFields().then(function () {
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

    if (btnSaveConfig) {
        btnSaveConfig.addEventListener("click", function () {
            saveConfig();
        });
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
    const contentTypeSelect = document.getElementById("field-content-type");
    if (contentTypeSelect) {
        contentTypeSelect.addEventListener("change", syncDateFormatField);
    }

    writeConfigForm();
    renderTable();
    if (canEdit && form) {
        syncDateFormatField();
        openCreate();
    }
})();
