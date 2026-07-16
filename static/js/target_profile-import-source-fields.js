/**
 * TargetProfile paso 4 — importar campos desde SourceProfile
 * Emite: document "dms:target-fields-imported" { detail: { fields, message, warnings } }
 */
(function () {
    "use strict";

    const btn = document.getElementById("btn-import-from-source");
    if (!btn || !window.dmsTargetProfile) {
        return;
    }

    const importUrl = btn.dataset.importUrl || "";
    if (!importUrl) {
        return;
    }

    function currentFieldsCount() {
        const target = window.dmsTargetProfile.getTarget() || {};
        const fields = target.fields;
        return Array.isArray(fields) ? fields.length : 0;
    }

    function runImport() {
        btn.disabled = true;
        const csrf =
            (window.dmsTargetProfile.readCsrfToken && window.dmsTargetProfile.readCsrfToken()) ||
            (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value ||
            "";

        return fetch(importUrl, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrf,
            },
            credentials: "same-origin",
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { okHttp: response.ok, data: data || {} };
                });
            })
            .then(function (result) {
                const data = result.data;
                if (!result.okHttp || !data.ok) {
                    const message = data.message || "No se pudieron importar los campos desde el origen.";
                    if (typeof window.dwShowMessage === "function") {
                        window.dwShowMessage("error", message);
                    }
                    throw new Error(message);
                }

                if (window.dmsTargetProfile.setTarget && data.target) {
                    window.dmsTargetProfile.setTarget(data.target);
                }

                document.dispatchEvent(
                    new CustomEvent("dms:target-fields-imported", {
                        detail: {
                            fields: data.fields || [],
                            message: data.message || "",
                            warnings: data.warnings || [],
                        },
                    })
                );

                if (typeof window.dwShowMessage === "function") {
                    window.dwShowMessage("success", data.message || "Campos importados correctamente.");
                    (data.warnings || []).forEach(function (warning) {
                        window.dwShowMessage("warning", warning);
                    });
                }
            })
            .catch(function (err) {
                if (err && err.message) {
                    return;
                }
                if (typeof window.dwShowMessage === "function") {
                    window.dwShowMessage("error", "No se pudieron importar los campos desde el origen.");
                }
            })
            .finally(function () {
                btn.disabled = false;
            });
    }

    btn.addEventListener("click", function () {
        const count = currentFieldsCount();
        const message =
            count > 0
                ? "Ya hay " +
                  count +
                  " campo(s) destino. ¿Reemplazarlos con los campos del origen?"
                : "¿Cargar los campos definidos en el perfil de origen?";

        if (typeof window.dwConfirmWarning === "function") {
            window.dwConfirmWarning(
                message,
                function () {
                    runImport();
                },
                {
                    title: "Importar desde origen",
                    okLabel: "Cargar",
                }
            );
            return;
        }
        if (window.confirm(message)) {
            runImport();
        }
    });
})();
