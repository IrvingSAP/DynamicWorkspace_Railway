/**
 * SourceProfile — Paso 4 campos posicionales (txt_fixed)
 * Modos: start/end | start/length | char (+ opcional start/length)
 */
(function () {
    "use strict";

    const root = document.getElementById("source-fields-root");
    if (!root) {
        return;
    }

    const defaultFields = window.dmsSourceProfile
        ? window.dmsSourceProfile.getSource().fields || []
        : [];

    const tbody = document.getElementById("source-fields-tbody");
    const ruler = document.getElementById("positional-ruler");
    const form = document.getElementById("field-editor-form");
    const formTitle = document.getElementById("field-editor-title");
    const formErrors = document.getElementById("field-editor-errors");
    const patternWrap = document.getElementById("field-pattern-wrap");
    const dateFormatWrap = document.getElementById("field-date-format-wrap");
    const charWrap = document.getElementById("field-char-wrap");
    const startWrap = document.getElementById("field-start-wrap");
    const endWrap = document.getElementById("field-end-wrap");
    const lengthWrap = document.getElementById("field-length-wrap");
    const btnAdd = document.getElementById("btn-add-field");
    const btnSave = document.getElementById("btn-save-field");
    const btnCancel = document.getElementById("btn-cancel-field");
    const btnDelete = document.getElementById("btn-delete-field");

    const SEGMENT_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4", "#ec4899"];

    let fields = loadFields();
    let editingIndex = null;

    function loadFields() {
        if (window.dmsSourceProfile) {
            const serverFields = window.dmsSourceProfile.getSource().fields;
            if (Array.isArray(serverFields) && serverFields.length) {
                return serverFields.map(cloneField);
            }
        }
        return defaultFields.map(cloneField);
    }

    function persistFields() {
        if (!window.dmsSourceProfile) {
            return Promise.resolve();
        }
        return window.dmsSourceProfile.save({ fields: fields });
    }

    function inferPositionMode(item) {
        if ((item.char || "").trim()) {
            return "char";
        }
        if (item.length && (!item.end || item.end === item.start + item.length - 1)) {
            return "length";
        }
        return "end";
    }

    function resolveBounds(item) {
        const mode = item.position_mode || inferPositionMode(item);
        const start = Number(item.start);
        let end = Number(item.end);
        let length = Number(item.length);
        const char = (item.char || "").trim();

        if (mode === "length" && Number.isFinite(start) && Number.isFinite(length) && length >= 1) {
            end = start + length - 1;
        } else if (mode === "end" && Number.isFinite(start) && Number.isFinite(end) && end >= start) {
            length = end - start + 1;
        } else if (mode === "char" && Number.isFinite(start) && !Number.isFinite(end)) {
            length = Number.isFinite(length) && length >= 1 ? length : 1;
            end = start + length - 1;
        }

        return {
            start: Number.isFinite(start) ? start : null,
            end: Number.isFinite(end) ? end : null,
            length: Number.isFinite(length) ? length : null,
            char: char,
            position_mode: mode,
        };
    }

    function cloneField(item) {
        const bounds = resolveBounds({
            start: item.start,
            end: item.end,
            length: item.length,
            char: item.char,
            position_mode: item.position_mode || inferPositionMode(item),
        });
        return {
            name: item.name || "",
            label: item.label || "",
            start: bounds.start,
            end: bounds.end,
            length: bounds.length,
            char: bounds.char,
            position_mode: bounds.position_mode,
            content_type: item.content_type || "free_text",
            required: Boolean(item.required),
            pattern: item.pattern || "",
            date_format: item.date_format || "",
        };
    }

    function isDateType(type) {
        return type === "date" || type === "datetime";
    }

    function fieldLength(item) {
        const bounds = resolveBounds(item);
        if (bounds.length != null) {
            return bounds.length;
        }
        if (bounds.start != null && bounds.end != null) {
            return bounds.end - bounds.start + 1;
        }
        return "—";
    }

    function modeLabel(item) {
        const mode = item.position_mode || inferPositionMode(item);
        if (mode === "length") {
            return "longitud";
        }
        if (mode === "char") {
            return "char";
        }
        return "fin";
    }

    function slugRe() {
        return /^[a-z][a-z0-9_]*$/;
    }

    function rangesOverlap(a, b) {
        if (a.start == null || a.end == null || b.start == null || b.end == null) {
            return false;
        }
        return a.start <= b.end && b.start <= a.end;
    }

    function clearErrors() {
        if (!formErrors) {
            return;
        }
        formErrors.hidden = true;
        formErrors.innerHTML = "";
        form.querySelectorAll(".has-error").forEach(function (el) {
            el.classList.remove("has-error");
        });
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

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function syncPositionModeUi() {
        const mode = document.getElementById("field-position-mode").value;
        if (endWrap) {
            endWrap.hidden = mode !== "end";
        }
        if (lengthWrap) {
            lengthWrap.hidden = mode !== "length" && mode !== "char";
        }
        if (charWrap) {
            charWrap.hidden = mode !== "char";
        }
        if (startWrap) {
            const startLabel = startWrap.querySelector("label");
            if (startLabel) {
                startLabel.innerHTML = mode === "char"
                    ? "Inicio (opcional, 1-based)"
                    : "Inicio (1-based) <span class=\"req\">*</span>";
            }
        }
    }

    function readForm() {
        const mode = document.getElementById("field-position-mode").value;
        const raw = {
            name: (document.getElementById("field-name").value || "").trim().toLowerCase(),
            label: (document.getElementById("field-label").value || "").trim(),
            position_mode: mode,
            start: parseInt(document.getElementById("field-start").value, 10),
            end: parseInt(document.getElementById("field-end").value, 10),
            length: parseInt(document.getElementById("field-length").value, 10),
            char: (document.getElementById("field-char").value || "").trim(),
            content_type: document.getElementById("field-content-type").value,
            required: document.getElementById("field-required").checked,
            pattern: (document.getElementById("field-pattern").value || "").trim(),
            date_format: (document.getElementById("field-date-format").value || "").trim(),
        };
        const bounds = resolveBounds(raw);
        return Object.assign({}, raw, bounds);
    }

    function writeForm(item) {
        const mode = item.position_mode || inferPositionMode(item);
        document.getElementById("field-name").value = item.name;
        document.getElementById("field-label").value = item.label;
        document.getElementById("field-position-mode").value = mode;
        document.getElementById("field-start").value = item.start != null ? item.start : "";
        document.getElementById("field-end").value = item.end != null ? item.end : "";
        document.getElementById("field-length").value = item.length != null ? item.length : "";
        document.getElementById("field-char").value = item.char || "";
        document.getElementById("field-content-type").value = item.content_type;
        document.getElementById("field-required").checked = item.required;
        document.getElementById("field-pattern").value = item.pattern;
        document.getElementById("field-date-format").value = item.date_format || "";
        syncPositionModeUi();
        syncConditionalFields();
    }

    function blankForm() {
        const nextStart = fields.length
            ? Math.max.apply(
                null,
                fields.map(function (f) {
                    return f.end != null ? f.end : (f.start || 0);
                })
            ) + 1
            : 1;
        writeForm({
            name: "",
            label: "",
            position_mode: "end",
            start: nextStart,
            end: nextStart,
            length: 1,
            char: "",
            content_type: "numeric",
            required: true,
            pattern: "",
            date_format: "",
        });
    }

    function validateField(data, index) {
        const errors = [];
        const warnings = [];

        if (!data.name) {
            errors.push("Ingrese el nombre (slug) del campo.");
        } else if (!slugRe().test(data.name)) {
            errors.push("El nombre debe empezar con letra minúscula y usar solo letras, números o guión bajo.");
        } else if (fields.some(function (f, i) { return i !== index && f.name === data.name; })) {
            errors.push("Ya existe un campo con el nombre «" + data.name + "».");
        }

        const mode = data.position_mode || "end";
        if (mode === "char") {
            if (!data.char) {
                errors.push("Indique el marcador char.");
            }
            if (data.length != null && data.length < 1) {
                errors.push("La longitud debe ser ≥ 1.");
            }
        } else if (mode === "length") {
            if (!Number.isFinite(data.start) || data.start < 1) {
                errors.push("El inicio debe ser un número mayor o igual a 1.");
            }
            if (!Number.isFinite(data.length) || data.length < 1) {
                errors.push("La longitud debe ser un número mayor o igual a 1.");
            }
        } else {
            if (!Number.isFinite(data.start) || data.start < 1) {
                errors.push("El inicio debe ser un número mayor o igual a 1.");
            }
            if (!Number.isFinite(data.end) || data.end < 1) {
                errors.push("El fin debe ser un número mayor o igual a 1.");
            }
            if (Number.isFinite(data.start) && Number.isFinite(data.end) && data.end < data.start) {
                errors.push("El fin debe ser mayor o igual al inicio.");
            }
        }

        if (data.start != null && data.end != null) {
            const overlap = fields.find(function (f, i) {
                return i !== index && rangesOverlap(resolveBounds(f), data);
            });
            if (overlap) {
                errors.push(
                    "El rango " + data.start + "–" + data.end
                    + " se solapa con el campo «" + overlap.name + "» ("
                    + overlap.start + "–" + overlap.end + ")."
                );
            }
        }

        if (data.content_type === "custom" && !data.pattern) {
            errors.push("Indique el patrón regex para el tipo custom.");
        }
        if (isDateType(data.content_type) && !data.date_format) {
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
        form.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function renderTable() {
        if (!tbody) {
            return;
        }
        if (!fields.length) {
            tbody.innerHTML = (
                '<tr class="fields-empty-row"><td colspan="9">'
                + "No hay campos definidos. Use «+ Agregar campo» para comenzar."
                + "</td></tr>"
            );
            return;
        }

        tbody.innerHTML = fields.map(function (item, index) {
            const startText = item.start != null ? item.start : "—";
            const endText = item.end != null ? item.end : "—";
            return (
                "<tr data-field-index=\"" + index + "\">"
                + "<td class=\"mono\">" + escapeHtml(item.name) + "</td>"
                + "<td>" + escapeHtml(item.label || "—") + "</td>"
                + "<td class=\"mono\">" + startText + "</td>"
                + "<td class=\"mono\">" + endText + "</td>"
                + "<td class=\"mono\">" + fieldLength(item) + "</td>"
                + "<td><span class=\"cell-badge\">" + escapeHtml(modeLabel(item)) + "</span></td>"
                + "<td><span class=\"cell-badge\">" + escapeHtml(item.content_type) + "</span></td>"
                + "<td>" + (item.required ? "Sí" : "No") + "</td>"
                + "<td class=\"col-actions\">"
                + "<button type=\"button\" class=\"btn btn-ghost btn-sm\" data-action=\"edit\" data-index=\"" + index + "\">Editar</button> "
                + "<button type=\"button\" class=\"btn btn-ghost btn-sm btn-ghost--danger\" data-action=\"delete\" data-index=\"" + index + "\">Eliminar</button>"
                + "</td>"
                + "</tr>"
            );
        }).join("");
    }

    function renderPreview() {
        if (!ruler) {
            return;
        }
        const drawable = fields.filter(function (item) {
            return item.start != null && item.end != null;
        });
        if (!drawable.length) {
            ruler.innerHTML = "<span class=\"hint\">Sin rangos numéricos — agregue campos con inicio/fin o longitud.</span>";
            return;
        }

        ruler.innerHTML = drawable.map(function (item, index) {
            const color = SEGMENT_COLORS[index % SEGMENT_COLORS.length];
            const width = fieldLength(item) + "ch";
            return (
                "<span class=\"field-seg\" style=\"width:" + width + ";border-color:" + color + ";color:" + color + "\">"
                + item.start + "-" + item.end + " " + escapeHtml(item.name)
                + "</span>"
            );
        }).join("");
    }

    function render() {
        renderTable();
        renderPreview();
    }

    function saveFieldsToServer() {
        return persistFields().catch(function (err) {
            const message = err.message || "No se pudo guardar en el servidor.";
            showErrors([message]);
            if (window.dmsSourceProfile && typeof window.dmsSourceProfile.showUserMessage === "function") {
                window.dmsSourceProfile.showUserMessage("error", message);
            } else if (typeof window.dwShowMessage === "function") {
                window.dwShowMessage("error", message);
            }
            throw err;
        });
    }

    function syncPatternField() {
        if (!patternWrap) {
            return;
        }
        const type = document.getElementById("field-content-type").value;
        patternWrap.hidden = type !== "custom";
    }

    function syncDateFormatField() {
        if (!dateFormatWrap) {
            return;
        }
        const type = document.getElementById("field-content-type").value;
        dateFormatWrap.hidden = !isDateType(type);
    }

    function syncConditionalFields() {
        syncPatternField();
        syncDateFormatField();
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
            label: data.label,
            content_type: data.content_type,
            required: data.required,
            pattern: data.pattern,
            date_format: data.date_format,
            position_mode: data.position_mode,
        };
        if (data.start != null) {
            payload.start = data.start;
        }
        if (data.end != null) {
            payload.end = data.end;
        }
        if (data.length != null) {
            payload.length = data.length;
        }
        if (data.char) {
            payload.char = data.char;
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

        fields.sort(function (a, b) {
            const as = a.start != null ? a.start : 999999;
            const bs = b.start != null ? b.start : 999999;
            return as - bs;
        });
        render();
        saveFieldsToServer().then(function () {
            if (result.warnings.length && window.dmsSourceProfile) {
                window.dmsSourceProfile.showUserMessage("warning", result.warnings.join(" "));
            }
            openCreate();
        });
    }

    function deleteField(index) {
        const name = fields[index].name;
        const doDelete = function () {
            fields.splice(index, 1);
            render();
            saveFieldsToServer().then(function () {
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

    document.getElementById("field-content-type").addEventListener("change", syncConditionalFields);
    document.getElementById("field-position-mode").addEventListener("change", syncPositionModeUi);

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        saveField();
    });

    render();
    openCreate();
})();
