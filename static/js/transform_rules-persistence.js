/**
 * Persistencia — Transform Rules (transform_pipeline)
 * Mensajes: docs/definition_app/UI_MESSAGES.md
 */
(function () {
    "use strict";

    const MSG_SESSION_EXPIRED =
        "Su sesión ha expirado. Cierre la sesión e inicie sesión de nuevo para continuar.";
    const MSG_UNEXPECTED_RESPONSE =
        "No se pudo completar la operación. Intente más tarde.";
    const MSG_SAVE_FAILED =
        "Ocurrió un error al guardar. Si persiste, contacte al administrador.";

    const dataNode = document.getElementById("dms-transform-rules-data");
    const configNode = document.getElementById("dms-transform-rules-config");
    if (!dataNode || !configNode) {
        return;
    }

    let rows = [];
    try {
        rows = JSON.parse(dataNode.textContent || "[]");
        if (!Array.isArray(rows)) {
            rows = [];
        }
    } catch (_err) {
        rows = [];
    }

    const saveUrl = configNode.dataset.saveUrl;
    const previewUrl = configNode.dataset.previewUrl;

    function readCsrfToken() {
        const configured = (configNode.dataset.csrfToken || "").trim();
        if (configured) {
            return configured;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function getRows() {
        return rows;
    }

    function setRows(next) {
        rows = Array.isArray(next) ? next : [];
        dataNode.textContent = JSON.stringify(rows);
    }

    function pipelinesPayload() {
        const pipelines = {};
        rows.forEach(function (row) {
            pipelines[row.target_field] = row.transform_pipeline || [];
        });
        return { pipelines: pipelines };
    }

    function makeError(message, options) {
        const opts = options || {};
        const error = new Error(message);
        error.errorCode = opts.errorCode || "unexpected";
        error.status = opts.status;
        error.errors = opts.errors || {};
        return error;
    }

    function showUserMessage(tags, text) {
        if (typeof window.dwShowMessage === "function") {
            window.dwShowMessage(tags, text);
            return;
        }
        if (window.console && typeof window.console.warn === "function") {
            window.console.warn(text);
        }
    }

    async function parseJsonResponse(response) {
        const text = await response.text();
        if (!text) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (_err) {
            const looksLikeHtml = /^\s*</.test(text);
            if (response.status === 403 || response.status === 401 || looksLikeHtml) {
                throw makeError(MSG_SESSION_EXPIRED, {
                    errorCode: "session_expired",
                    status: response.status,
                });
            }
            throw makeError(MSG_UNEXPECTED_RESPONSE, {
                errorCode: "unexpected",
                status: response.status,
            });
        }
    }

    async function save(options) {
        const opts = options || {};
        const csrfToken = readCsrfToken();
        if (!csrfToken) {
            throw makeError(MSG_SESSION_EXPIRED, { errorCode: "session_expired" });
        }
        if (!saveUrl) {
            throw makeError(MSG_SAVE_FAILED, { errorCode: "unexpected" });
        }

        const body = new URLSearchParams();
        body.set("pipelines_payload", JSON.stringify(pipelinesPayload()));
        if (opts.strict) {
            body.set("strict", "1");
        }

        const response = await fetch(saveUrl, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            body: body.toString(),
            credentials: "same-origin",
        });

        const data = await parseJsonResponse(response);
        if (!response.ok || !data.ok) {
            if (response.status === 401 || response.status === 403) {
                throw makeError(data.message || MSG_SESSION_EXPIRED, {
                    errorCode: "session_expired",
                    status: response.status,
                    errors: data.errors || {},
                });
            }
            throw makeError(data.message || MSG_SAVE_FAILED, {
                errorCode: data.error_code || "validation_form",
                status: response.status,
                errors: data.errors || {},
            });
        }

        if (Array.isArray(data.mappings)) {
            const byTarget = {};
            data.mappings.forEach(function (item) {
                byTarget[item.target_field] = item.transform_pipeline || [];
            });
            rows = rows.map(function (row) {
                const next = Object.assign({}, row);
                if (Object.prototype.hasOwnProperty.call(byTarget, row.target_field)) {
                    next.transform_pipeline = byTarget[row.target_field];
                    next.ops_label = (next.transform_pipeline || [])
                        .map(function (step) {
                            return step.op;
                        })
                        .join(" → ");
                    if (!next.ops_label) {
                        next.ops_label = "(sin reglas)";
                    }
                }
                return next;
            });
            setRows(rows);
        }

        const warningList = Array.isArray(data.warnings) ? data.warnings : [];
        if (warningList.length) {
            showUserMessage("warning", warningList.join(" "));
        }
        return data;
    }

    async function preview(sample, steps, options) {
        const opts = options || {};
        const csrfToken = readCsrfToken();
        if (!csrfToken) {
            throw makeError(MSG_SESSION_EXPIRED, { errorCode: "session_expired" });
        }
        if (!previewUrl) {
            throw makeError(MSG_UNEXPECTED_RESPONSE, { errorCode: "unexpected" });
        }
        const body = new URLSearchParams();
        body.set("sample", sample == null ? "" : String(sample));
        body.set("pipeline_payload", JSON.stringify(steps || []));
        if (opts.fromSample) {
            body.set("from_sample", "1");
            body.set("target_field", opts.targetField || "");
        }

        const response = await fetch(previewUrl, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            body: body.toString(),
            credentials: "same-origin",
        });
        const data = await parseJsonResponse(response);
        if (!response.ok || !data.ok) {
            throw makeError(data.message || MSG_UNEXPECTED_RESPONSE, {
                errorCode: "validation_form",
                status: response.status,
                errors: data.errors || {},
            });
        }
        return data;
    }

    window.dmsTransformRules = {
        getRows: getRows,
        setRows: setRows,
        save: save,
        preview: preview,
        showUserMessage: showUserMessage,
        canEdit: configNode.dataset.canEdit === "1",
        hasSample: configNode.dataset.hasSample === "1",
    };
})();
