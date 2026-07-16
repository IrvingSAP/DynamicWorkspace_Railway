/**
 * SourceProfile wizard — pasos 1–3: lectura del formulario y persistencia servidor
 */
(function () {
    "use strict";

    const root = document.getElementById("source-step-root");
    if (!root || !window.dmsSourceProfile) {
        return;
    }

    const step = root.dataset.step;
    const canEdit = root.dataset.canEdit === "1";
    const statusEl = document.getElementById("step-save-status");
    const btnSave = document.getElementById("btn-save-step");
    const btnNext = document.getElementById("btn-step-next");

    function setStatus(message, isError) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message || "";
        statusEl.classList.toggle("step-save-status--error", Boolean(isError));
    }

    function showErrorModal(message) {
        if (window.dmsSourceProfile && typeof window.dmsSourceProfile.showUserMessage === "function") {
            window.dmsSourceProfile.showUserMessage("error", message);
            return;
        }
        if (typeof window.dwShowMessage === "function") {
            window.dwShowMessage("error", message);
        }
    }

    function checkedValue(name) {
        const input = document.querySelector('input[name="' + name + '"]:checked');
        return input ? input.value : "";
    }

    function intValue(id, fallback) {
        const node = document.getElementById(id);
        if (!node) {
            return fallback;
        }
        const parsed = parseInt(node.value, 10);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function textValue(id) {
        const node = document.getElementById(id);
        return node ? node.value.trim() : "";
    }

    function selectValue(id, fallback) {
        const node = document.getElementById(id);
        return node ? node.value : fallback;
    }

    function readStep1() {
        const lineEndingCode = selectValue("line_ending_code", "lf");
        const payload = {
            file_type_code: checkedValue("file_type"),
            encoding_code: selectValue("encoding_code", "latin-1"),
            line_ending_code: lineEndingCode,
        };
        if (lineEndingCode === "custom") {
            payload.line_ending_custom = textValue("line_ending_custom");
        } else {
            payload.line_ending_custom = null;
        }
        return payload;
    }

    function readCaptureStart() {
        const mode = checkedValue("capture_start_mode");
        const capture = { mode: mode };
        if (mode === "line_number") {
            capture.line = intValue("start_line", 1);
        } else if (mode === "after_header_block") {
            capture.skip_lines = intValue("skip_lines", 0);
        } else if (mode === "marker_start") {
            capture.marker = textValue("marker_start");
        } else if (mode === "after_pattern") {
            capture.pattern = textValue("start_pattern");
        } else if (mode === "after_blank_run") {
            capture.blank_count = intValue("start_blank_count", 1);
        }
        return { capture_start: capture };
    }

    function readCaptureEnd() {
        const mode = checkedValue("capture_end_mode");
        const capture = { mode: mode };
        if (mode === "line_number" || mode === "line_or_eof") {
            const fieldId = mode === "line_number" ? "end_line" : "line_or_eof";
            capture.line = intValue(fieldId, 1);
        } else if (mode === "percent") {
            capture.value = intValue("percent_value", 80);
        } else if (mode === "max_rows") {
            capture.max_rows = intValue("max_rows", 1000);
        } else if (mode === "marker_end") {
            capture.marker = textValue("marker_end");
        } else if (mode === "before_pattern") {
            capture.pattern = textValue("end_pattern");
        } else if (mode === "blank_run") {
            capture.blank_count = intValue("end_blank_count", 1);
        }
        return { capture_end: capture };
    }

    function readCurrentStep() {
        if (step === "1") {
            return readStep1();
        }
        if (step === "2") {
            return readCaptureStart();
        }
        if (step === "3") {
            return readCaptureEnd();
        }
        return {};
    }

    function hydrateFromSource() {
        const source = window.dmsSourceProfile.getSource() || {};

        if (step === "1") {
            const fileType = source.file_type_code || "txt_fixed";
            const fileRadio = document.querySelector('input[name="file_type"][value="' + fileType + '"]');
            if (fileRadio && !fileRadio.disabled) {
                fileRadio.checked = true;
            }
            const encoding = document.getElementById("encoding_code");
            if (encoding && source.encoding_code) {
                encoding.value = source.encoding_code;
            }
            const lineEnding = document.getElementById("line_ending_code");
            if (lineEnding && source.line_ending_code) {
                lineEnding.value = source.line_ending_code;
                lineEnding.dispatchEvent(new Event("change"));
            }
            const customEnding = document.getElementById("line_ending_custom");
            if (customEnding && source.line_ending_custom) {
                customEnding.value = source.line_ending_custom;
            }
            return;
        }

        if (step === "2") {
            const capture = source.capture_start || {};
            const mode = capture.mode || "line_number";
            const radio = document.querySelector('input[name="capture_start_mode"][value="' + mode + '"]');
            if (radio && !radio.disabled) {
                radio.checked = true;
                radio.dispatchEvent(new Event("change"));
            }
            if (capture.line != null) {
                const startLine = document.getElementById("start_line");
                if (startLine) {
                    startLine.value = capture.line;
                }
            }
            if (capture.skip_lines != null) {
                const skipLines = document.getElementById("skip_lines");
                if (skipLines) {
                    skipLines.value = capture.skip_lines;
                }
            }
            if (capture.marker) {
                const marker = document.getElementById("marker_start");
                if (marker) {
                    marker.value = capture.marker;
                }
            }
            if (capture.pattern) {
                const pattern = document.getElementById("start_pattern");
                if (pattern) {
                    pattern.value = capture.pattern;
                }
            }
            if (capture.blank_count != null) {
                const blankCount = document.getElementById("start_blank_count");
                if (blankCount) {
                    blankCount.value = capture.blank_count;
                }
            }
            return;
        }

        if (step === "3") {
            const capture = source.capture_end || {};
            const mode = capture.mode || "eof";
            const radio = document.querySelector('input[name="capture_end_mode"][value="' + mode + '"]');
            if (radio && !radio.disabled) {
                radio.checked = true;
                radio.dispatchEvent(new Event("change"));
            }
            if (capture.line != null) {
                const endLine = document.getElementById("end_line");
                const lineOrEof = document.getElementById("line_or_eof");
                if (mode === "line_or_eof" && lineOrEof) {
                    lineOrEof.value = capture.line;
                } else if (endLine) {
                    endLine.value = capture.line;
                }
            }
            if (capture.value != null) {
                const percent = document.getElementById("percent_value");
                if (percent) {
                    percent.value = capture.value;
                }
            }
            if (capture.max_rows != null) {
                const maxRows = document.getElementById("max_rows");
                if (maxRows) {
                    maxRows.value = capture.max_rows;
                }
            }
            if (capture.marker) {
                const markerEnd = document.getElementById("marker_end");
                if (markerEnd) {
                    markerEnd.value = capture.marker;
                }
            }
            if (capture.pattern) {
                const endPattern = document.getElementById("end_pattern");
                if (endPattern) {
                    endPattern.value = capture.pattern;
                }
            }
            if (capture.blank_count != null) {
                const blankCount = document.getElementById("end_blank_count");
                if (blankCount) {
                    blankCount.value = capture.blank_count;
                }
            }
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

    async function saveStep(nextUrl) {
        if (!canEdit) {
            if (nextUrl) {
                window.location.href = nextUrl;
            }
            return;
        }

        setStatus("Guardando…", false);
        try {
            await window.dmsSourceProfile.save(readCurrentStep());
            setStatus("Borrador guardado.", false);
            if (nextUrl) {
                window.location.href = nextUrl;
            }
        } catch (err) {
            const detail = formatErrors(err.errors);
            const message = detail || err.message || "No se pudo guardar.";
            setStatus(message, true);
            showErrorModal(message);
        }
    }

    hydrateFromSource();

    if (btnSave) {
        btnSave.addEventListener("click", function () {
            saveStep("");
        });
    }

    if (btnNext) {
        btnNext.addEventListener("click", function () {
            saveStep(btnNext.dataset.next || root.dataset.nextUrl || "");
        });
    }
})();
