/**
 * SourceProfile — Paso 6 configuración del informe de procesamiento
 */
(function () {
    "use strict";

    const root = document.getElementById("processing-report-root");
    if (!root) {
        return;
    }

    const statusEl = document.getElementById("processing-report-status");
    const previewEl = document.getElementById("processing-report-preview");
    const btnSave = document.getElementById("btn-save-processing-report");
    const btnSaveProfile = document.getElementById("btn-save-source-profile");
    const form = document.getElementById("processing-report-form");

    const fields = {
        report_enabled: document.getElementById("report_enabled"),
        include_summary: document.getElementById("include_summary"),
        include_row_errors: document.getElementById("include_row_errors"),
        reject_alert_threshold: document.getElementById("reject_alert_threshold"),
        reject_alert_threshold_unit: document.getElementById("reject_alert_threshold_unit"),
        report_format: document.getElementById("report_format"),
    };

    const SAMPLE_REPORT = {
        status: "partial",
        summary: {
            rows_read: 1000,
            rows_ok: 985,
            rows_rejected: 15,
            reject_rate_percent: 1.5,
        },
        messages: [
            {
                level: "warning",
                text: "15 registros no cumplieron con lo requerido",
            },
        ],
        row_errors: [
            {
                line: 42,
                field: "salario",
                code: "CONTENT_TYPE_MISMATCH",
                value: "ABC",
            },
        ],
    };

    function readForm() {
        const thresholdRaw = fields.reject_alert_threshold
            ? parseInt(fields.reject_alert_threshold.value, 10)
            : 0;
        return {
            report_enabled: Boolean(fields.report_enabled && fields.report_enabled.checked),
            include_summary: Boolean(fields.include_summary && fields.include_summary.checked),
            include_row_errors: Boolean(fields.include_row_errors && fields.include_row_errors.checked),
            reject_alert_threshold: Number.isFinite(thresholdRaw) ? thresholdRaw : 0,
            reject_alert_threshold_unit: fields.reject_alert_threshold_unit
                ? fields.reject_alert_threshold_unit.value
                : "count",
            report_format: fields.report_format ? fields.report_format.value : "json",
        };
    }

    function writeForm(data) {
        if (fields.report_enabled) {
            fields.report_enabled.checked = Boolean(data.report_enabled);
        }
        if (fields.include_summary) {
            fields.include_summary.checked = Boolean(data.include_summary);
        }
        if (fields.include_row_errors) {
            fields.include_row_errors.checked = Boolean(data.include_row_errors);
        }
        if (fields.reject_alert_threshold) {
            fields.reject_alert_threshold.value = data.reject_alert_threshold ?? 10;
        }
        if (fields.reject_alert_threshold_unit) {
            fields.reject_alert_threshold_unit.value = data.reject_alert_threshold_unit || "count";
        }
        if (fields.report_format) {
            fields.report_format.value = data.report_format || "json";
        }
        syncDependentFields();
        updatePreview();
    }

    function loadConfig() {
        if (window.dmsSourceProfile) {
            return window.dmsSourceProfile.getSource().processing_report || {};
        }
        return {};
    }

    function setStatus(message, isError) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message;
        statusEl.classList.toggle("is-error", Boolean(isError));
    }

    function buildSampleOutput(config) {
        const output = {
            status: SAMPLE_REPORT.status,
        };

        if (config.include_summary) {
            output.summary = { ...SAMPLE_REPORT.summary };
        }
        if (config.report_enabled) {
            output.messages = SAMPLE_REPORT.messages.slice();
        }
        if (config.include_row_errors) {
            output.row_errors = SAMPLE_REPORT.row_errors.slice();
        }

        if (!config.report_enabled) {
            return {
                processing_report: config,
                sample_output: {
                    note: "Informe deshabilitado (report_enabled = false).",
                },
            };
        }

        return {
            processing_report: config,
            sample_output: output,
        };
    }

    function syncDependentFields() {
        const enabled = Boolean(fields.report_enabled && fields.report_enabled.checked);
        ["include_summary", "include_row_errors", "reject_alert_threshold", "reject_alert_threshold_unit", "report_format"].forEach(function (id) {
            const el = document.getElementById(id);
            if (el) {
                el.disabled = !enabled;
            }
        });
    }

    function updatePreview() {
        if (!previewEl) {
            return;
        }
        const config = readForm();
        previewEl.textContent = JSON.stringify(buildSampleOutput(config), null, 2);
    }

    function saveConfig(showMessage, strict) {
        const data = readForm();
        if (!window.dmsSourceProfile) {
            updatePreview();
            return Promise.resolve();
        }
        return window.dmsSourceProfile.save(
            { processing_report: data },
            { strict: Boolean(strict) }
        ).then(function (result) {
            updatePreview();
            if (showMessage) {
                setStatus(result.message || "Borrador guardado en el servidor.", false);
            }
            return result;
        }).catch(function (err) {
            const message = err.message || "No se pudo guardar.";
            setStatus(message, true);
            if (window.dmsSourceProfile && typeof window.dmsSourceProfile.showUserMessage === "function") {
                window.dmsSourceProfile.showUserMessage("error", message);
            } else if (typeof window.dwShowMessage === "function") {
                window.dwShowMessage("error", message);
            }
            throw err;
        });
    }

    writeForm(loadConfig());
    setStatus("Borrador cargado desde el servidor.", false);

    if (fields.report_enabled) {
        fields.report_enabled.addEventListener("change", function () {
            syncDependentFields();
            updatePreview();
            setStatus("Cambios sin guardar.", false);
        });
    }

    if (btnSave) {
        btnSave.addEventListener("click", function (e) {
            e.preventDefault();
            saveConfig(true);
        });
    }

    if (btnSaveProfile) {
        btnSaveProfile.addEventListener("click", function (e) {
            e.preventDefault();
            saveConfig(true, true).catch(function () {
                /* mensaje ya mostrado */
            });
        });
    }

    const btnPublish = document.getElementById("btn-publish-version");
    if (btnPublish && window.dmsSourcePublish) {
        btnPublish.addEventListener("click", function (e) {
            e.preventDefault();
            const next = btnPublish.dataset.next || "";
            const draftLabel = btnPublish.dataset.draftLabel || "el borrador actual";
            const message = (
                "¿Publicar " + draftLabel + "? "
                + "Se validará el perfil completo, se congelará la versión y se creará un nuevo borrador."
            );

            const runPublish = function () {
                setStatus("Validando y publicando…", false);
                btnPublish.disabled = true;
                saveConfig(false, true).then(function () {
                    return window.dmsSourcePublish.publish({ next: next });
                }).then(function (data) {
                    setStatus(data.message || "Versión publicada.", false);
                    if (next) {
                        window.location.href = next;
                    } else {
                        window.location.reload();
                    }
                }).catch(function (err) {
                    const message = err.message || "No se pudo publicar.";
                    setStatus(message, true);
                    if (window.dmsSourceProfile && typeof window.dmsSourceProfile.showUserMessage === "function") {
                        window.dmsSourceProfile.showUserMessage("error", message);
                    } else if (typeof window.dwShowMessage === "function") {
                        window.dwShowMessage("error", message);
                    }
                    btnPublish.disabled = false;
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

    if (form) {
        form.addEventListener("input", function () {
            updatePreview();
            setStatus("Cambios sin guardar.", false);
        });
        form.addEventListener("change", function () {
            syncDependentFields();
            updatePreview();
            setStatus("Cambios sin guardar.", false);
        });
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            saveConfig(true);
        });
    }
})();
