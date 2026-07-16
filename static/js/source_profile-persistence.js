/**
 * Persistencia servidor — DmsSourceProfile
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
    const MSG_SAVE_FAILED = "Ocurrió un error al guardar. Si persiste, contacte al administrador.";

    const dataNode = document.getElementById("dms-source-profile-data");
    const configNode = document.getElementById("dms-source-save-config");
    if (!dataNode || !configNode) {
        return;
    }

    let current = {};
    try {
        current = JSON.parse(dataNode.textContent || "{}");
    } catch (_err) {
        current = {};
    }

    const saveUrl = configNode.dataset.saveUrl;

    function readCsrfToken() {
        const configured = (configNode.dataset.csrfToken || "").trim();
        if (configured) {
            return configured;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function getSource() {
        return current;
    }

    function setSource(next) {
        current = next || {};
        dataNode.textContent = JSON.stringify(current);
    }

    function merge(partial) {
        const merged = JSON.parse(JSON.stringify(current));
        const replaceKeys = ["capture_start", "capture_end"];
        const mergeKeys = ["content_rules", "processing_report", "config"];
        Object.keys(partial || {}).forEach(function (key) {
            const value = partial[key];
            if (replaceKeys.includes(key) && value && typeof value === "object" && !Array.isArray(value)) {
                merged[key] = Object.assign({}, value);
            } else if (mergeKeys.includes(key) && value && typeof value === "object" && !Array.isArray(value)) {
                merged[key] = Object.assign({}, merged[key] || {}, value);
            } else {
                merged[key] = value;
            }
        });
        return merged;
    }

    function makeError(message, options) {
        const opts = options || {};
        const error = new Error(message);
        error.errorCode = opts.errorCode || "unexpected";
        error.status = opts.status;
        error.errors = opts.errors || {};
        return error;
    }

    /**
     * Muestra feedback operativo en el modal del shell (`dw-modals.js`).
     * Validación por campo sigue siendo responsabilidad del paso (inline).
     */
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

    async function save(partial, options) {
        const opts = options || {};
        const csrfToken = readCsrfToken();
        if (!csrfToken) {
            throw makeError(MSG_SESSION_EXPIRED, { errorCode: "session_expired" });
        }
        if (!saveUrl) {
            throw makeError(MSG_SAVE_FAILED, { errorCode: "unexpected" });
        }

        const payload = partial || {};
        const body = new URLSearchParams();
        body.set("source_payload", JSON.stringify(payload));
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
                throw makeError(
                    data.message || MSG_SESSION_EXPIRED,
                    {
                        errorCode: "session_expired",
                        status: response.status,
                        errors: data.errors || {},
                    }
                );
            }
            throw makeError(data.message || MSG_SAVE_FAILED, {
                errorCode: data.error_code || "unexpected",
                status: response.status,
                errors: data.errors || {},
            });
        }
        if (data.source) {
            setSource(data.source);
        } else {
            setSource(merge(partial));
        }
        const warningList = Array.isArray(data.warnings) ? data.warnings : [];
        if (warningList.length) {
            showUserMessage("warning", warningList.join(" "));
        }
        return data;
    }

    window.dmsSourceProfile = {
        getSource: getSource,
        setSource: setSource,
        merge: merge,
        save: save,
        readCsrfToken: readCsrfToken,
        showUserMessage: showUserMessage,
        MSG_SESSION_EXPIRED: MSG_SESSION_EXPIRED,
    };
})();
