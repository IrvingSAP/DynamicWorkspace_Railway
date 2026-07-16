/**
 * Transform execution UI (transform_execution.md)
 */
(function () {
    "use strict";

    const MSG_SESSION =
        "Su sesión ha expirado. Cierre la sesión e inicie sesión de nuevo para continuar.";
    const MSG_UNEXPECTED = "No se pudo completar la operación. Intente más tarde.";

    const config = document.getElementById("dms-transform-execution-config");
    if (!config) {
        return;
    }

    function csrf() {
        const token = (config.dataset.csrfToken || "").trim();
        if (token) {
            return token;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function show(tags, text) {
        if (typeof window.dwShowMessage === "function") {
            window.dwShowMessage(tags, text);
        }
    }

    function urlFor(template, jobId) {
        return String(template || "").replace(
            "00000000-0000-0000-0000-000000000000",
            jobId
        );
    }

    function setStatus(text, isError) {
        const node = document.getElementById("te-status");
        if (!node) {
            return;
        }
        node.textContent = text || "";
        node.classList.toggle("step-save-status--error", !!isError);
    }

    function setErrors(text) {
        const node = document.getElementById("te-errors");
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

    async function post(url) {
        const token = csrf();
        if (!token) {
            throw new Error(MSG_SESSION);
        }
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": token,
            },
        });
        const text = await response.text();
        let data = {};
        try {
            data = JSON.parse(text || "{}");
        } catch (_err) {
            if (response.status === 403 || /^\s*</.test(text || "")) {
                throw new Error(MSG_SESSION);
            }
            throw new Error(MSG_UNEXPECTED);
        }
        if (!response.ok || !data.ok) {
            if (response.status === 401 || response.status === 403) {
                throw new Error(data.message || MSG_SESSION);
            }
            throw new Error(data.message || MSG_UNEXPECTED);
        }
        return data;
    }

    function renderPreview(data) {
        const panel = document.getElementById("te-preview-panel");
        const summary = document.getElementById("te-preview-summary");
        const head = document.getElementById("te-preview-head");
        const body = document.getElementById("te-preview-body");
        const errors = document.getElementById("te-preview-errors");
        if (!panel) {
            return;
        }
        panel.hidden = false;
        if (summary) {
            summary.textContent =
                "Leídas: " +
                data.rows_read +
                " · OK: " +
                data.rows_ok +
                " · Rechazadas: " +
                data.rows_rejected;
        }
        const targetFields = data.target_fields || [];
        if (head) {
            head.innerHTML =
                "<tr><th>Línea</th>" +
                targetFields
                    .map(function (name) {
                        return "<th>" + name + "</th>";
                    })
                    .join("") +
                "</tr>";
        }
        if (body) {
            body.innerHTML = "";
            (data.preview_rows || []).forEach(function (row) {
                const tr = document.createElement("tr");
                let html = "<td>" + row.line + "</td>";
                targetFields.forEach(function (name) {
                    const value =
                        row.target && row.target[name] != null ? row.target[name] : "";
                    html += "<td>" + String(value) + "</td>";
                });
                tr.innerHTML = html;
                body.appendChild(tr);
            });
        }
        if (errors) {
            const list = data.row_errors || [];
            errors.textContent = list.length
                ? list
                      .map(function (err) {
                          return (
                              "L" +
                              err.line +
                              " " +
                              (err.field || "") +
                              " [" +
                              (err.code || "") +
                              "] " +
                              (err.message || "")
                          );
                      })
                      .join("\n")
                : "(sin errores)";
        }
    }

    function renderResult(data) {
        const panel = document.getElementById("te-result-panel");
        const summary = document.getElementById("te-result-summary");
        const links = document.getElementById("te-result-links");
        if (!panel) {
            return;
        }
        panel.hidden = false;
        if (summary) {
            summary.textContent =
                (data.message || "") +
                " Estado: " +
                (data.status || "") +
                " · OK " +
                (data.rows_ok || 0) +
                " · rej " +
                (data.rows_rejected || 0) +
                " · " +
                (data.output_filename || "");
        }
        if (links) {
            links.innerHTML = "";
            const downloads = data.downloads || {};
            ["output", "report", "errors"].forEach(function (kind) {
                if (!downloads[kind]) {
                    return;
                }
                const a = document.createElement("a");
                a.className = "btn btn-secondary";
                a.href = downloads[kind];
                a.textContent =
                    kind === "output"
                        ? "Descargar salida"
                        : kind === "report"
                          ? "Descargar informe"
                          : "Descargar errores";
                links.appendChild(a);
            });
            const hist = document.createElement("a");
            hist.className = "btn btn-primary";
            hist.href = location.pathname.replace(/\/?$/, "/") + "historial/";
            // Fix: hub path ends with ejecutar/
            hist.href = location.pathname.replace(/\/?$/, "/") + "historial/";
            hist.textContent = "Ver historial";
            links.appendChild(hist);
        }
    }

    async function onPreview(jobId) {
        setErrors("");
        setStatus("Generando preview…");
        try {
            const data = await post(urlFor(config.dataset.previewTemplate, jobId));
            setStatus(data.message || "Preview listo.");
            show("success", data.message || "Preview generado correctamente.");
            renderPreview(data);
        } catch (err) {
            setStatus(err.message || MSG_UNEXPECTED, true);
            setErrors(err.message || MSG_UNEXPECTED);
            show("error", err.message || MSG_UNEXPECTED);
        }
    }

    async function onRun(jobId) {
        const run = async function () {
            setErrors("");
            setStatus("Ejecutando transformación…");
            try {
                const data = await post(urlFor(config.dataset.runTemplate, jobId));
                setStatus(data.message || "Listo.");
                show("success", data.message || "Transformación finalizada.");
                renderResult(data);
                window.setTimeout(function () {
                    window.location.reload();
                }, 1200);
            } catch (err) {
                setStatus(err.message || MSG_UNEXPECTED, true);
                setErrors(err.message || MSG_UNEXPECTED);
                show("error", err.message || MSG_UNEXPECTED);
            }
        };
        const message =
            "¿Ejecutar transformación del job seleccionado? Se generará el archivo destino.";
        if (typeof window.dwConfirmWarning === "function") {
            window.dwConfirmWarning(message, run, {
                title: "Ejecutar transformación",
                okLabel: "Ejecutar",
            });
        } else if (window.confirm(message)) {
            run();
        }
    }

    document.querySelectorAll("[data-action='preview']").forEach(function (btn) {
        btn.addEventListener("click", function () {
            onPreview(btn.getAttribute("data-job-id"));
        });
    });
    document.querySelectorAll("[data-action='run']").forEach(function (btn) {
        btn.addEventListener("click", function () {
            onRun(btn.getAttribute("data-job-id"));
        });
    });
})();
