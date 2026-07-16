/**
 * Publicar versión DmsMappingVersion (borrador → published)
 * Mensajes: docs/definition_app/UI_MESSAGES.md
 */
(function () {
    "use strict";

    /** @see UI_MESSAGES.md §3.4 session_expired */
    const MSG_SESSION_EXPIRED =
        "Su sesión ha expirado. Cierre la sesión e inicie sesión de nuevo para continuar.";
    const MSG_UNEXPECTED_RESPONSE =
        "No se pudo completar la operación. Intente más tarde.";
    const MSG_PUBLISH_FAILED =
        "Ocurrió un error al guardar. Si persiste, contacte al administrador.";

    const configNode = document.getElementById("dms-source-publish-config");
    if (!configNode) {
        return;
    }

    const publishUrl = configNode.dataset.publishUrl;

    function readCsrfToken() {
        const configured = (configNode.dataset.csrfToken || "").trim();
        if (configured) {
            return configured;
        }
        if (window.dmsSourceProfile && typeof window.dmsSourceProfile.readCsrfToken === "function") {
            return window.dmsSourceProfile.readCsrfToken();
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function showUserMessage(tags, text) {
        if (window.dmsSourceProfile && typeof window.dmsSourceProfile.showUserMessage === "function") {
            window.dmsSourceProfile.showUserMessage(tags, text);
            return;
        }
        if (typeof window.dwShowMessage === "function") {
            window.dwShowMessage(tags, text);
        }
    }

    function formatErrors(errors) {
        if (!errors || typeof errors !== "object") {
            return "";
        }
        const messages = [];
        Object.keys(errors).forEach(function (key) {
            (errors[key] || []).forEach(function (item) {
                messages.push(item);
            });
        });
        return messages.join(" ");
    }

    function makeError(message, options) {
        const opts = options || {};
        const error = new Error(message);
        error.errorCode = opts.errorCode || "unexpected";
        error.status = opts.status;
        error.errors = opts.errors || {};
        return error;
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

    async function publishVersion(options) {
        const opts = options || {};
        const csrfToken = readCsrfToken();
        if (!csrfToken) {
            throw makeError(MSG_SESSION_EXPIRED, { errorCode: "session_expired" });
        }
        const body = new URLSearchParams();
        if (opts.next) {
            body.set("next", opts.next);
        }

        const response = await fetch(publishUrl, {
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
            throw makeError(data.message || MSG_PUBLISH_FAILED, {
                errorCode: data.error_code || "unexpected",
                status: response.status,
                errors: data.errors || {},
            });
        }
        return data;
    }

    function bindButton(button, statusEl) {
        if (!button) {
            return;
        }

        button.addEventListener("click", function (e) {
            e.preventDefault();
            const next = button.dataset.next || "";
            const draftLabel = button.dataset.draftLabel || "el borrador actual";
            const message = (
                "¿Publicar " + draftLabel + "? "
                + "La definición quedará congelada para ejecución y se creará un nuevo borrador."
            );

            const runPublish = function () {
                if (statusEl) {
                    statusEl.textContent = "Publicando…";
                    statusEl.classList.remove("step-save-status--error", "is-error");
                }
                button.disabled = true;
                publishVersion({ next: next }).then(function (data) {
                    if (statusEl) {
                        statusEl.textContent = data.message || "Versión publicada.";
                    }
                    const warningList = Array.isArray(data.warnings) ? data.warnings : [];
                    if (warningList.length) {
                        showUserMessage("warning", warningList.join(" "));
                    }
                    if (next) {
                        window.location.href = next;
                    } else {
                        window.location.reload();
                    }
                }).catch(function (err) {
                    const detail = formatErrors(err.errors);
                    const text = detail || err.message || "No se pudo publicar.";
                    if (statusEl) {
                        statusEl.textContent = text;
                        statusEl.classList.add("step-save-status--error");
                    }
                    showUserMessage("error", text);
                    button.disabled = false;
                });
            };

            if (typeof window.dwConfirmWarning === "function") {
                window.dwConfirmWarning(
                    message,
                    runPublish,
                    { title: "Publicar versión", okLabel: "Publicar" }
                );
            } else if (window.confirm(message)) {
                runPublish();
            }
        });
    }

    document.querySelectorAll("[data-action='publish-version']").forEach(function (button) {
        const statusId = button.dataset.statusTarget;
        const statusEl = statusId ? document.getElementById(statusId) : null;
        bindButton(button, statusEl);
    });

    window.dmsSourcePublish = {
        publish: publishVersion,
    };
})();
