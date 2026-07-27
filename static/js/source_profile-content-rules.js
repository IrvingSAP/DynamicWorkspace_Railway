/**
 * SourceProfile — Paso 5 reglas globales de contenido
 * Persistencia en servidor vía dmsSourceProfile.save.
 */
(function () {
    "use strict";

    const root = document.getElementById("content-rules-root");
    if (!root) {
        return;
    }

    const defaultNode = document.getElementById("content-rules-default");
    const defaults = defaultNode
        ? JSON.parse(defaultNode.textContent || "{}")
        : {};
    const statusEl = document.getElementById("content-rules-status");
    const previewEl = document.getElementById("content-rules-preview");
    const btnSave = document.getElementById("btn-save-content-rules");
    const btnNext = document.getElementById("btn-content-rules-next");
    const form = document.getElementById("content-rules-form");

    const fields = {
        trim_lines: document.getElementById("trim_lines"),
        skip_empty_lines: document.getElementById("skip_empty_lines"),
        comment_prefix: document.getElementById("comment_prefix"),
        allowed_chars: document.getElementById("allowed_chars"),
        excluded_chars: document.getElementById("excluded_chars"),
        forbidden_patterns: document.getElementById("forbidden_patterns"),
    };

    function linesToList(text) {
        return String(text || "")
            .split(/\r?\n/)
            .map(function (line) { return line.trim(); })
            .filter(function (line) { return line.length > 0; });
    }

    function listToLines(items) {
        return (items || []).join("\n");
    }

    function readForm() {
        return {
            trim_lines: Boolean(fields.trim_lines && fields.trim_lines.checked),
            skip_empty_lines: Boolean(fields.skip_empty_lines && fields.skip_empty_lines.checked),
            comment_prefix: (fields.comment_prefix && fields.comment_prefix.value || "").trim(),
            allowed_chars: (fields.allowed_chars && fields.allowed_chars.value || "").trim(),
            excluded_chars: linesToList(fields.excluded_chars && fields.excluded_chars.value),
            forbidden_patterns: linesToList(fields.forbidden_patterns && fields.forbidden_patterns.value),
        };
    }

    function writeForm(data) {
        if (fields.trim_lines) {
            fields.trim_lines.checked = Boolean(data.trim_lines);
        }
        if (fields.skip_empty_lines) {
            fields.skip_empty_lines.checked = Boolean(data.skip_empty_lines);
        }
        if (fields.comment_prefix) {
            fields.comment_prefix.value = data.comment_prefix || "";
        }
        if (fields.allowed_chars) {
            fields.allowed_chars.value = data.allowed_chars || "";
        }
        if (fields.excluded_chars) {
            fields.excluded_chars.value = listToLines(data.excluded_chars);
        }
        if (fields.forbidden_patterns) {
            fields.forbidden_patterns.value = listToLines(data.forbidden_patterns);
        }
        updatePreview();
    }

    function loadRules() {
        const saved = window.dmsSourceProfile
            ? (window.dmsSourceProfile.getSource().content_rules || {})
            : {};
        return Object.assign({}, defaults, saved);
    }

    function setStatus(message, isError) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message;
        statusEl.classList.toggle("is-error", Boolean(isError));
    }

    function updatePreview() {
        if (!previewEl) {
            return;
        }
        const payload = { content_rules: readForm() };
        previewEl.textContent = JSON.stringify(payload, null, 2);
    }

    function saveRules(options) {
        const opts = options || {};
        const nextUrl = opts.nextUrl || "";
        const showMessage = Boolean(opts.showMessage);
        const data = readForm();
        if (!window.dmsSourceProfile) {
            updatePreview();
            if (nextUrl) {
                window.location.href = nextUrl;
            }
            return Promise.resolve();
        }
        setStatus("Guardando…", false);
        return window.dmsSourceProfile.save({ content_rules: data }).then(function () {
            updatePreview();
            if (showMessage && !nextUrl) {
                setStatus("Borrador guardado en el servidor.", false);
            }
            if (nextUrl) {
                window.location.href = nextUrl;
            }
        }).catch(function (err) {
            const message = err.message || "No se pudo guardar.";
            setStatus(message, true);
            if (window.dmsSourceProfile && typeof window.dmsSourceProfile.showUserMessage === "function") {
                window.dmsSourceProfile.showUserMessage("error", message);
            } else if (typeof window.dwShowMessage === "function") {
                window.dwShowMessage("error", message);
            }
        });
    }

    writeForm(loadRules());
    setStatus("Los cambios se guardan al pulsar «Guardar borrador» o «Siguiente».", false);

    if (btnSave) {
        btnSave.addEventListener("click", function (e) {
            e.preventDefault();
            saveRules({ showMessage: true });
        });
    }

    if (btnNext) {
        btnNext.addEventListener("click", function (e) {
            e.preventDefault();
            saveRules({ nextUrl: btnNext.dataset.next || "" });
        });
    }

    if (form) {
        form.addEventListener("input", function () {
            updatePreview();
            setStatus("Cambios sin guardar.", false);
        });
        form.addEventListener("change", function () {
            updatePreview();
            setStatus("Cambios sin guardar.", false);
        });
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            saveRules({ showMessage: true });
        });
    }
})();
