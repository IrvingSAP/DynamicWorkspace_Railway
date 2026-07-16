/**
 * File intake — muestra y producción (file_intake.md)
 * Mensajes: docs/definition_app/UI_MESSAGES.md
 */
(function () {
    "use strict";

    const MSG_SESSION_EXPIRED =
        "Su sesión ha expirado. Cierre la sesión e inicie sesión de nuevo para continuar.";
    const MSG_UNEXPECTED =
        "No se pudo completar la operación. Intente más tarde.";

    const config = document.getElementById("dms-file-intake-config");
    if (!config) {
        return;
    }

    const state = {
        sample: null,
        production: null,
    };

    function readCsrf() {
        const configured = (config.dataset.csrfToken || "").trim();
        if (configured) {
            return configured;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function showMessage(tags, text) {
        if (typeof window.dwShowMessage === "function") {
            window.dwShowMessage(tags, text);
            return;
        }
        if (window.console) {
            window.console.warn(text);
        }
    }

    function humanSize(bytes) {
        let value = Number(bytes) || 0;
        const units = ["B", "KB", "MB", "GB"];
        for (let i = 0; i < units.length; i += 1) {
            if (value < 1024 || i === units.length - 1) {
                return i === 0 ? value + " " + units[i] : value.toFixed(1) + " " + units[i];
            }
            value /= 1024;
        }
        return bytes + " B";
    }

    function allowedExts() {
        return (config.dataset.accept || "")
            .split(",")
            .map(function (part) {
                return part.trim().toLowerCase();
            })
            .filter(Boolean);
    }

    function extensionOf(name) {
        const lower = String(name || "").toLowerCase();
        const idx = lower.lastIndexOf(".");
        return idx >= 0 ? lower.slice(idx) : "";
    }

    function validateClient(file, context) {
        if (!file) {
            return "Seleccione un archivo.";
        }
        const ext = extensionOf(file.name);
        const allowed = allowedExts();
        if (allowed.length && allowed.indexOf(ext) < 0) {
            return "Tipo de archivo no permitido para este proyecto.";
        }
        const max =
            context === "sample"
                ? Number(config.dataset.sampleMaxBytes || 0)
                : Number(config.dataset.productionMaxBytes || 0);
        if (max && file.size > max) {
            return "El archivo supera el límite de " + humanSize(max) + ".";
        }
        if (file.size === 0) {
            return "El archivo está vacío.";
        }
        return "";
    }

    function setMeta(context, text) {
        const node = document.querySelector(
            '[data-role="file-meta"][data-context="' + context + '"]'
        );
        if (node) {
            node.textContent = text;
        }
    }

    function setButtons(context, hasFile) {
        document
            .querySelectorAll(
                '[data-action="clear"][data-context="' +
                    context +
                    '"], [data-action="upload"][data-context="' +
                    context +
                    '"]'
            )
            .forEach(function (btn) {
                btn.disabled = !hasFile;
            });
    }

    function setErrors(context, text) {
        const node = document.getElementById("fi-" + context + "-errors");
        if (!node) {
            return;
        }
        if (!text) {
            node.hidden = true;
            node.textContent = "";
            return;
        }
        node.hidden = false;
        node.textContent = text;
    }

    function setProgress(context, percent) {
        const wrap = document.querySelector(
            '[data-role="progress"][data-context="' + context + '"]'
        );
        const bar = wrap ? wrap.querySelector('[data-role="progress-bar"]') : null;
        if (!wrap || !bar) {
            return;
        }
        if (percent == null) {
            wrap.hidden = true;
            bar.style.width = "0%";
            return;
        }
        wrap.hidden = false;
        bar.style.width = Math.max(0, Math.min(100, percent)) + "%";
    }

    function assignFile(context, file) {
        const error = validateClient(file, context);
        if (error) {
            state[context] = null;
            setMeta(context, "Ningún archivo seleccionado");
            setButtons(context, false);
            setErrors(context, error);
            showMessage("error", error);
            return;
        }
        state[context] = file;
        setMeta(context, file.name + " · " + humanSize(file.size));
        setButtons(context, true);
        setErrors(context, "");
    }

    function clearFile(context) {
        state[context] = null;
        const input = document.getElementById(
            context === "sample" ? "fi-sample-input" : "fi-production-input"
        );
        if (input) {
            input.value = "";
        }
        setMeta(context, "Ningún archivo seleccionado");
        setButtons(context, false);
        setErrors(context, "");
        setProgress(context, null);
    }

    function renderResult(context, data) {
        const node = document.getElementById("fi-" + context + "-result");
        if (!node) {
            return;
        }
        const suggestions = data.suggestions || {};
        const preview = data.preview_rows || [];
        let html =
            "<strong>" +
            (data.original_filename || "") +
            "</strong> · " +
            (data.size_label || "") +
            "<br>Sugerencias: " +
            (suggestions.file_type_code || "—") +
            " / " +
            (suggestions.encoding_code || "—") +
            " / " +
            (suggestions.line_ending_code || "—");
        if (suggestions.delimiter) {
            html += " · delim " + JSON.stringify(suggestions.delimiter);
        }
        if (data.job_id) {
            html += "<br>Job: " + data.job_id + " (uploaded)";
        }
        if (preview.length) {
            html +=
                "<br><br><pre style='margin:0;white-space:pre-wrap;font-size:12px'>" +
                preview
                    .slice(0, 8)
                    .map(function (row) {
                        return String(row.line).padStart(3, " ") + " | " + (row.raw || "");
                    })
                    .join("\n") +
                "</pre>";
        }
        node.innerHTML = html;
        node.hidden = false;
    }

    function upload(context) {
        const file = state[context];
        const url =
            context === "sample"
                ? config.dataset.sampleUploadUrl
                : config.dataset.productionUploadUrl;
        if (!file || !url) {
            return;
        }
        if (context === "production" && config.dataset.hasPublished !== "1") {
            const msg = "Publique una versión antes de ejecutar.";
            setErrors(context, msg);
            showMessage("error", msg);
            return;
        }
        const csrf = readCsrf();
        if (!csrf) {
            showMessage("error", MSG_SESSION_EXPIRED);
            return;
        }

        const form = new FormData();
        form.append("file", file);

        const xhr = new XMLHttpRequest();
        xhr.open("POST", url);
        xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        xhr.setRequestHeader("X-CSRFToken", csrf);
        xhr.withCredentials = true;

        xhr.upload.onprogress = function (event) {
            if (event.lengthComputable) {
                setProgress(context, (event.loaded / event.total) * 100);
            } else {
                setProgress(context, 50);
            }
        };

        xhr.onload = function () {
            setProgress(context, 100);
            let data = {};
            try {
                data = JSON.parse(xhr.responseText || "{}");
            } catch (_err) {
                if (xhr.status === 403 || /^\s*</.test(xhr.responseText || "")) {
                    showMessage("error", MSG_SESSION_EXPIRED);
                    setErrors(context, MSG_SESSION_EXPIRED);
                    return;
                }
                showMessage("error", MSG_UNEXPECTED);
                setErrors(context, MSG_UNEXPECTED);
                return;
            }
            if (xhr.status >= 200 && xhr.status < 300 && data.ok) {
                setErrors(context, "");
                showMessage("success", data.message || "Archivo subido correctamente.");
                renderResult(context, data);
                window.setTimeout(function () {
                    window.location.reload();
                }, 700);
                return;
            }
            if (xhr.status === 401 || xhr.status === 403) {
                showMessage("error", data.message || MSG_SESSION_EXPIRED);
                setErrors(context, data.message || MSG_SESSION_EXPIRED);
                return;
            }
            const details =
                data.errors && data.errors.file ? data.errors.file.join(" ") : "";
            const text = details || data.message || MSG_UNEXPECTED;
            setErrors(context, text);
            showMessage("error", text);
            setProgress(context, null);
        };

        xhr.onerror = function () {
            setProgress(context, null);
            showMessage("error", MSG_UNEXPECTED);
            setErrors(context, MSG_UNEXPECTED);
        };

        setProgress(context, 5);
        xhr.send(form);
    }

    async function previewSample(sampleId) {
        const url =
            "/app/filepipe/proyectos/" +
            encodeURIComponent(location.pathname.split("/")[4] || "") +
            "/archivo/muestras/" +
            encodeURIComponent(sampleId) +
            "/preview/";
        // Prefer data from list item URL pattern via template — rebuild from config path
        const base = config.dataset.sampleUploadUrl || "";
        const previewUrl = base.replace(/muestras\/subir\/?$/, "muestras/" + sampleId + "/preview/");
        try {
            const response = await fetch(previewUrl || url, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const text = await response.text();
            let data;
            try {
                data = JSON.parse(text);
            } catch (_err) {
                showMessage("error", MSG_UNEXPECTED);
                return;
            }
            if (!response.ok || !data.ok) {
                showMessage("error", data.message || MSG_UNEXPECTED);
                return;
            }
            const dialog = document.getElementById("fi-preview-dialog");
            const title = document.getElementById("fi-preview-title");
            const body = document.getElementById("fi-preview-body");
            if (title) {
                title.textContent = data.original_filename || "Preview";
            }
            if (body) {
                const suggestions = data.suggestions || {};
                const lines = (data.preview_rows || [])
                    .map(function (row) {
                        return String(row.line).padStart(4, " ") + " | " + (row.raw || "");
                    })
                    .join("\n");
                body.textContent =
                    "Sugerencias: " +
                    JSON.stringify(suggestions) +
                    "\n\n" +
                    lines;
            }
            if (dialog && typeof dialog.showModal === "function") {
                dialog.showModal();
            }
        } catch (_err) {
            showMessage("error", MSG_UNEXPECTED);
        }
    }

    async function deleteSample(sampleId) {
        const base = config.dataset.sampleUploadUrl || "";
        const deleteUrl = base.replace(
            /muestras\/subir\/?$/,
            "muestras/" + sampleId + "/eliminar/"
        );
        const run = async function () {
            const csrf = readCsrf();
            if (!csrf) {
                showMessage("error", MSG_SESSION_EXPIRED);
                return;
            }
            const response = await fetch(deleteUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrf,
                },
            });
            const data = await response.json().catch(function () {
                return {};
            });
            if (!response.ok || !data.ok) {
                showMessage("error", data.message || MSG_UNEXPECTED);
                return;
            }
            showMessage("success", data.message || "Archivo muestra eliminado correctamente.");
            window.location.reload();
        };
        if (typeof window.dwConfirmWarning === "function") {
            window.dwConfirmWarning("¿Eliminar este archivo muestra?", run, {
                title: "Eliminar muestra",
                okLabel: "Eliminar",
            });
        } else if (window.confirm("¿Eliminar este archivo muestra?")) {
            run();
        }
    }

    function bindDropzone(context) {
        const zone = document.querySelector(
            '.fi-dropzone[data-context="' + context + '"]'
        );
        const input = document.getElementById(
            context === "sample" ? "fi-sample-input" : "fi-production-input"
        );
        if (!zone || !input) {
            return;
        }
        zone.addEventListener("dragover", function (event) {
            event.preventDefault();
            zone.classList.add("is-dragover");
        });
        zone.addEventListener("dragleave", function () {
            zone.classList.remove("is-dragover");
        });
        zone.addEventListener("drop", function (event) {
            event.preventDefault();
            zone.classList.remove("is-dragover");
            const file = event.dataTransfer && event.dataTransfer.files[0];
            if (file) {
                assignFile(context, file);
            }
        });
        input.addEventListener("change", function () {
            const file = input.files && input.files[0];
            if (file) {
                assignFile(context, file);
            }
        });
    }

    document.querySelectorAll("[data-action='browse']").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const context = btn.getAttribute("data-context");
            const input = document.getElementById(
                context === "sample" ? "fi-sample-input" : "fi-production-input"
            );
            if (input) {
                input.click();
            }
        });
    });
    document.querySelectorAll("[data-action='clear']").forEach(function (btn) {
        btn.addEventListener("click", function () {
            clearFile(btn.getAttribute("data-context"));
        });
    });
    document.querySelectorAll("[data-action='upload']").forEach(function (btn) {
        btn.addEventListener("click", function () {
            upload(btn.getAttribute("data-context"));
        });
    });
    document.querySelectorAll("[data-action='preview-sample']").forEach(function (btn) {
        btn.addEventListener("click", function () {
            previewSample(btn.getAttribute("data-id"));
        });
    });
    document.querySelectorAll("[data-action='delete-sample']").forEach(function (btn) {
        btn.addEventListener("click", function () {
            deleteSample(btn.getAttribute("data-id"));
        });
    });
    const closeBtn = document.getElementById("fi-preview-close");
    if (closeBtn) {
        closeBtn.addEventListener("click", function () {
            const dialog = document.getElementById("fi-preview-dialog");
            if (dialog) {
                dialog.close();
            }
        });
    }

    bindDropzone("sample");
    bindDropzone("production");
})();
