/**
 * Persistencia AJAX — gate_policy FILE GATE
 */
(function () {
    "use strict";

    const MSG_UNEXPECTED = "No se pudo completar la operación. Intente más tarde.";
    const MSG_SESSION =
        "Su sesión ha expirado. Cierre la sesión e inicie sesión de nuevo para continuar.";

    const configNode = document.getElementById("fg-policy-save-config");
    if (!configNode) {
        return;
    }

    const saveUrl = configNode.dataset.saveUrl || "";

    function csrfToken() {
        const configured = (configNode.dataset.csrfToken || "").trim();
        if (configured) {
            return configured;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function showMessage(level, text) {
        if (typeof window.dwShowMessage === "function") {
            window.dwShowMessage(level, text);
            return;
        }
        window.alert(text);
    }

    function setStatus(message, isError) {
        const el = document.getElementById("step-save-status");
        if (!el) {
            return;
        }
        el.textContent = message || "";
        el.classList.toggle("step-save-status--error", Boolean(isError));
    }

    function readPartialFromForm() {
        const root = document.getElementById("policy-step-root");
        if (!root) {
            return {};
        }
        const step = root.dataset.step;
        if (step === "1") {
            const onError = document.querySelector('input[name="on_error"]:checked');
            const maxErrors = document.getElementById("max_errors");
            return {
                on_error: onError ? onError.value : "collect_all",
                abort_on_first_fatal: true,
                max_errors: maxErrors ? maxErrors.value : 500,
            };
        }
        if (step === "2") {
            const mode = document.querySelector('input[name="threshold_mode"]:checked');
            const value = document.getElementById("threshold_value");
            return {
                abort_on_first_fatal: true,
                reject_threshold: {
                    mode: mode ? mode.value : "percent",
                    value: value ? value.value : 1,
                },
            };
        }
        return { abort_on_first_fatal: true };
    }

    function savePolicy(options) {
        const opts = options || {};
        const partial = opts.partial || readPartialFromForm();
        const body = new URLSearchParams();
        body.set("policy_payload", JSON.stringify(partial));
        if (opts.next) {
            body.set("next", opts.next);
        }

        return fetch(saveUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrfToken(),
            },
            body: body.toString(),
            credentials: "same-origin",
        }).then(function (response) {
            if (response.status === 403) {
                showMessage("error", MSG_SESSION);
                return Promise.reject(new Error("session"));
            }
            return response.json().then(function (data) {
                if (!response.ok || !data.ok) {
                    const message = (data && data.message) || MSG_UNEXPECTED;
                    showMessage("error", message);
                    setStatus(message, true);
                    return Promise.reject(data || {});
                }
                setStatus(data.message || "Guardado.", false);
                (data.warnings || []).forEach(function (warning) {
                    showMessage("warning", warning);
                });
                return data;
            });
        });
    }

    window.fgGatePolicy = {
        save: savePolicy,
        readPartialFromForm: readPartialFromForm,
    };

    document.addEventListener("click", function (event) {
        const saveBtn = event.target.closest("[data-action='save-policy']");
        if (!saveBtn) {
            return;
        }
        event.preventDefault();
        if (saveBtn.dataset.canEdit === "0") {
            return;
        }
        saveBtn.disabled = true;
        savePolicy({ next: saveBtn.dataset.next || "" })
            .then(function (data) {
                const next = saveBtn.dataset.next;
                if (next) {
                    window.location.href = next;
                    return;
                }
                showMessage("success", data.message || "Política guardada.");
            })
            .catch(function () {})
            .finally(function () {
                saveBtn.disabled = false;
            });
    });
})();
