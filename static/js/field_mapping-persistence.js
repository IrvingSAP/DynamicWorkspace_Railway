/**
 * Persistencia servidor — DmsFieldMappingSet
 * Mensajes: docs/definition_app/UI_MESSAGES.md
 */
(function () {
    "use strict";

    /** @see UI_MESSAGES.md §3.4 session_expired */
    const MSG_SESSION_EXPIRED =
        "Su sesión ha expirado. Cierre la sesión e inicie sesión de nuevo para continuar.";
    /** @see UI_MESSAGES.md §3.1 */
    const MSG_UNEXPECTED_RESPONSE =
        "No se pudo completar la operación. Intente más tarde.";
    const MSG_SAVE_FAILED =
        "Ocurrió un error al guardar. Si persiste, contacte al administrador.";

    const dataNode = document.getElementById("dms-field-mappings-data");
    const configNode = document.getElementById("dms-field-mapping-save-config");
    if (!dataNode || !configNode) {
        return;
    }

    let current = [];
    try {
        current = JSON.parse(dataNode.textContent || "[]");
        if (!Array.isArray(current)) {
            current = [];
        }
    } catch (_err) {
        current = [];
    }

    const saveUrl = configNode.dataset.saveUrl;
    const previewUrl = configNode.dataset.previewUrl || "";

    function readCsrfToken() {
        const configured = (configNode.dataset.csrfToken || "").trim();
        if (configured) {
            return configured;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function getMappings() {
        return current.slice();
    }

    function setMappings(next) {
        current = Array.isArray(next) ? next.slice() : [];
        dataNode.textContent = JSON.stringify(current);
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

    async function save(mappings, options) {
        const opts = options || {};
        const csrfToken = readCsrfToken();
        if (!csrfToken) {
            throw makeError(MSG_SESSION_EXPIRED, { errorCode: "session_expired" });
        }
        if (!saveUrl) {
            throw makeError(MSG_SAVE_FAILED, { errorCode: "unexpected" });
        }

        const body = new URLSearchParams();
        body.set("mappings_payload", JSON.stringify({ mappings: mappings || [] }));
        if (opts.strict) {
            body.set("strict", "1");
        }
        if (opts.next) {
            body.set("next", opts.next);
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
            setMappings(data.mappings);
        } else {
            setMappings(mappings || []);
        }
        const warningList = Array.isArray(data.warnings) ? data.warnings : [];
        if (warningList.length) {
            showUserMessage("warning", warningList.join(" "));
        }
        return data;
    }

    async function preview(mappings, sourceRow, rowNumber) {
        const csrfToken = readCsrfToken();
        if (!csrfToken) {
            throw makeError(MSG_SESSION_EXPIRED, { errorCode: "session_expired" });
        }
        if (!previewUrl) {
            throw makeError(MSG_UNEXPECTED_RESPONSE, { errorCode: "unexpected" });
        }
        const body = new URLSearchParams();
        body.set("mappings_payload", JSON.stringify({ mappings: mappings || [] }));
        body.set("source_row", JSON.stringify(sourceRow || {}));
        body.set("row_number", String(rowNumber || 1));

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
            if (response.status === 401 || response.status === 403) {
                throw makeError(data.message || MSG_SESSION_EXPIRED, {
                    errorCode: "session_expired",
                    status: response.status,
                    errors: data.errors || {},
                });
            }
            throw makeError(data.message || MSG_UNEXPECTED_RESPONSE, {
                errorCode: data.error_code || "unexpected",
                status: response.status,
                errors: data.errors || {},
            });
        }
        return data;
    }

    window.dmsFieldMapping = {
        getMappings: getMappings,
        setMappings: setMappings,
        save: save,
        preview: preview,
        readCsrfToken: readCsrfToken,
        showUserMessage: showUserMessage,
        canEdit: configNode.dataset.canEdit === "1",
        MSG_SESSION_EXPIRED: MSG_SESSION_EXPIRED,
    };
})();
