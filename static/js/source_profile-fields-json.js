/**
 * SourceProfile — Paso 4 campos JSON
 */
(function () {
    "use strict";

    const root = document.getElementById("source-fields-json-root");
    if (!root || !window.dmsSourceProfile) {
        return;
    }

    const canEdit = root.dataset.canEdit === "1";
    const statusEl = document.getElementById("json-save-status");
    const configNode = document.getElementById("json-config-default");
    const tbody = document.getElementById("source-fields-tbody");
    const form = document.getElementById("field-editor-form");
    const formTitle = document.getElementById("field-editor-title");
    const formErrors = document.getElementById("field-editor-errors");
    const btnAdd = document.getElementById("btn-add-field");
    const btnSave = document.getElementById("btn-save-field");
    const btnCancel = document.getElementById("btn-cancel-field");
    const btnDelete = document.getElementById("btn-delete-field");
    const btnSaveConfig = document.getElementById("btn-save-json-config");

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
            json_path: item.json_path || "",
            content_type: item.content_type || "free_text",
            required: Boolean(item.required),
        };
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
            record_path: (document.getElementById("record_path").value || "").trim(),
        };
    }

    function writeConfigForm() {
        document.getElementById("record_path").value = config.record_path || "";
    }

    function readForm() {
        return {
            name: (document.getElementById("field-name").value || "").trim().toLowerCase(),
            json_path: (document.getElementById("field-json-path").value || "").trim(),
            content_type: document.getElementById("field-content-type").value,
            required: document.getElementById("field-required").checked,
        };
    }

    function writeForm(item) {
        document.getElementById("field-name").value = item.name;
        document.getElementById("field-json-path").value = item.json_path;
        document.getElementById("field-content-type").value = item.content_type;
        document.getElementById("field-required").checked = item.required;
    }

    function blankForm() {
        writeForm({
            name: "",
            json_path: "",
            content_type: "numeric",
            required: true,
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
        if (!data.json_path) {
            errors.push("Indique el json_path del campo.");
        } else if (fields.some(function (f, i) {
            return i !== index && f.json_path === data.json_path;
        })) {
            errors.push("Ya existe un campo con el json_path «" + data.json_path + "».");
        }
        return errors;
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
                + "<td class=\"mono\">" + escapeHtml(item.name) + "</td>"
                + "<td class=\"mono\">" + escapeHtml(item.json_path) + "</td>"
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
        if (!config.record_path) {
            setStatus("Indique la ruta de registros (record_path).", true);
            return Promise.reject(new Error("Indique la ruta de registros (record_path)."));
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

    writeConfigForm();
    renderTable();
    if (canEdit && form) {
        openCreate();
    }
})();
