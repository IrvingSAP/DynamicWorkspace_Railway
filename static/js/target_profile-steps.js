/**
 * TargetProfile wizard — pasos 1–3, 5–6: lectura del formulario y persistencia servidor
 */
(function () {
    "use strict";

    const root = document.getElementById("target-step-root");
    if (!root || !window.dmsTargetProfile) {
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
        if (window.dmsTargetProfile && typeof window.dmsTargetProfile.showUserMessage === "function") {
            window.dmsTargetProfile.showUserMessage("error", message);
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
        if (!node || node.value === "") {
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

    function checkboxValue(id, fallback) {
        const node = document.getElementById(id);
        if (!node) {
            return fallback;
        }
        return node.checked;
    }

    function readStep1() {
        return {
            file_type_code: checkedValue("file_type") || "csv",
        };
    }

    function readStep2() {
        const lineEndingCode = selectValue("line_ending_code", "lf");
        const payload = {
            encoding_code: selectValue("encoding_code", "utf-8"),
            line_ending_code: lineEndingCode,
        };
        if (lineEndingCode === "custom") {
            payload.line_ending_custom = textValue("line_ending_custom");
        } else {
            payload.line_ending_custom = null;
        }
        return payload;
    }

    function layoutVariant() {
        return root.dataset.layoutVariant || "";
    }

    function fileTypeCode() {
        const target = window.dmsTargetProfile.getTarget() || {};
        return target.file_type_code || "";
    }

    function readLayout() {
        const variant = layoutVariant();
        const code = fileTypeCode();
        const layout = {
            output_filename_pattern: textValue("output_filename_pattern"),
        };

        if (variant === "xlsx" || code === "xlsx") {
            layout.sheet_name = textValue("sheet_name") || "Hoja1";
            layout.include_header = checkboxValue("include_header", true);
            layout.freeze_header_row = checkboxValue("freeze_header_row", true);
            layout.column_width_auto = checkboxValue("column_width_auto", true);
            return { layout: layout };
        }

        if (variant === "json" || code === "json") {
            layout.root_type = selectValue("root_type", "array") || "array";
            layout.records_path = textValue("records_path");
            layout.pretty_print = checkboxValue("pretty_print", true);
            layout.indent = intValue("indent", 2);
            layout.include_bom = checkboxValue("include_bom", false);
            return { layout: layout };
        }

        if (variant === "xml" || code === "xml") {
            layout.root_element = textValue("root_element") || "records";
            layout.record_element = textValue("record_element") || "record";
            layout.namespace = textValue("namespace");
            layout.declaration = checkboxValue("declaration", true);
            return { layout: layout };
        }

        layout.include_bom = checkboxValue("include_bom", false);

        if (variant === "fixed" || code === "txt_fixed") {
            const recordLength = intValue("record_length", null);
            layout.record_length = recordLength;
            layout.trailing_newline = checkboxValue("trailing_newline", true);
            return { layout: layout };
        }

        let delimiter = selectValue("delimiter", ",");
        if (delimiter === "tab") {
            delimiter = "\t";
        }
        layout.delimiter = delimiter;
        layout.quote_char = (textValue("quote_char") || '"').slice(0, 1);
        layout.escape_char = (textValue("escape_char") || "\\").slice(0, 1);
        layout.include_header = checkboxValue("include_header", true);
        return { layout: layout };
    }

    function readSerialization() {
        return {
            serialization: {
                trim_before_write: checkboxValue("trim_before_write", true),
                default_truncate: selectValue("default_truncate", "right"),
                date_format: textValue("date_format") || "YYYY-MM-DD",
                boolean_format: selectValue("boolean_format", "1_0"),
                null_representation: document.getElementById("null_representation")
                    ? document.getElementById("null_representation").value
                    : "",
                decimal_places: intValue("decimal_places", 2),
                decimal_separator: selectValue("decimal_separator", "."),
            },
        };
    }

    function readWriteValidation() {
        return {
            write_validation: {
                policy: selectValue("policy", "reject_row"),
                on_type_mismatch: selectValue("on_type_mismatch", "reject_row"),
                on_length_exceeded: selectValue("on_length_exceeded", "truncate"),
                on_required_empty: selectValue("on_required_empty", "reject_row"),
            },
        };
    }

    function readCurrentStep() {
        if (step === "1") {
            return readStep1();
        }
        if (step === "2") {
            return readStep2();
        }
        if (step === "3") {
            return readLayout();
        }
        if (step === "5") {
            return readSerialization();
        }
        if (step === "6") {
            return readWriteValidation();
        }
        return {};
    }

    function hydrateFromTarget() {
        const target = window.dmsTargetProfile.getTarget() || {};

        if (step === "1") {
            const fileType = target.file_type_code || "csv";
            const fileRadio = document.querySelector('input[name="file_type"][value="' + fileType + '"]');
            if (fileRadio && !fileRadio.disabled) {
                fileRadio.checked = true;
            }
            return;
        }

        if (step === "2") {
            const encoding = document.getElementById("encoding_code");
            if (encoding && target.encoding_code) {
                encoding.value = target.encoding_code;
            }
            const lineEnding = document.getElementById("line_ending_code");
            if (lineEnding && target.line_ending_code) {
                lineEnding.value = target.line_ending_code;
                lineEnding.dispatchEvent(new Event("change"));
            }
            const customEnding = document.getElementById("line_ending_custom");
            if (customEnding && target.line_ending_custom) {
                customEnding.value = target.line_ending_custom;
            }
            return;
        }

        if (step === "3") {
            const layout = target.layout || {};
            const pattern = document.getElementById("output_filename_pattern");
            if (pattern && layout.output_filename_pattern != null) {
                pattern.value = layout.output_filename_pattern;
            }
            const includeBom = document.getElementById("include_bom");
            if (includeBom) {
                includeBom.checked = Boolean(layout.include_bom);
            }

            const delimiterSelect = document.getElementById("delimiter");
            if (delimiterSelect) {
                const stored = layout.delimiter || ",";
                delimiterSelect.value = stored === "\t" ? "tab" : stored;
            }
            const quoteChar = document.getElementById("quote_char");
            if (quoteChar) {
                quoteChar.value = layout.quote_char || '"';
            }
            const escapeChar = document.getElementById("escape_char");
            if (escapeChar) {
                escapeChar.value = layout.escape_char || "\\";
            }
            const includeHeader = document.getElementById("include_header");
            if (includeHeader) {
                includeHeader.checked = layout.include_header !== false;
            }

            const recordLength = document.getElementById("record_length");
            if (recordLength && layout.record_length != null) {
                recordLength.value = layout.record_length;
            }
            const trailingNewline = document.getElementById("trailing_newline");
            if (trailingNewline) {
                trailingNewline.checked = layout.trailing_newline !== false;
            }

            const sheetName = document.getElementById("sheet_name");
            if (sheetName) {
                sheetName.value = layout.sheet_name || "Hoja1";
            }
            const freezeHeader = document.getElementById("freeze_header_row");
            if (freezeHeader) {
                freezeHeader.checked = layout.freeze_header_row !== false;
            }
            const columnWidthAuto = document.getElementById("column_width_auto");
            if (columnWidthAuto) {
                columnWidthAuto.checked = layout.column_width_auto !== false;
            }

            const rootType = document.getElementById("root_type");
            if (rootType) {
                rootType.value = layout.root_type === "object" ? "object" : "array";
            }
            const recordsPath = document.getElementById("records_path");
            if (recordsPath && layout.records_path != null) {
                recordsPath.value = layout.records_path;
            }
            const prettyPrint = document.getElementById("pretty_print");
            if (prettyPrint) {
                prettyPrint.checked = layout.pretty_print !== false;
            }
            const indent = document.getElementById("indent");
            if (indent && layout.indent != null) {
                indent.value = layout.indent;
            }
            const rootElement = document.getElementById("root_element");
            if (rootElement) {
                rootElement.value = layout.root_element || "records";
            }
            const recordElement = document.getElementById("record_element");
            if (recordElement) {
                recordElement.value = layout.record_element || "record";
            }
            const namespace = document.getElementById("namespace");
            if (namespace && layout.namespace != null) {
                namespace.value = layout.namespace;
            }
            const declaration = document.getElementById("declaration");
            if (declaration) {
                declaration.checked = layout.declaration !== false;
            }
            return;
        }

        if (step === "5") {
            const ser = target.serialization || {};
            const trimBefore = document.getElementById("trim_before_write");
            if (trimBefore) {
                trimBefore.checked = ser.trim_before_write !== false;
            }
            const truncate = document.getElementById("default_truncate");
            if (truncate && ser.default_truncate) {
                truncate.value = ser.default_truncate;
            }
            const dateFormat = document.getElementById("date_format");
            if (dateFormat && ser.date_format) {
                dateFormat.value = ser.date_format;
            }
            const booleanFormat = document.getElementById("boolean_format");
            if (booleanFormat && ser.boolean_format) {
                booleanFormat.value = ser.boolean_format;
            }
            const nullRep = document.getElementById("null_representation");
            if (nullRep && ser.null_representation != null) {
                nullRep.value = ser.null_representation;
            }
            const decimalPlaces = document.getElementById("decimal_places");
            if (decimalPlaces && ser.decimal_places != null) {
                decimalPlaces.value = ser.decimal_places;
            }
            const decimalSep = document.getElementById("decimal_separator");
            if (decimalSep && ser.decimal_separator) {
                decimalSep.value = ser.decimal_separator;
            }
            return;
        }

        if (step === "6") {
            const wv = target.write_validation || {};
            ["policy", "on_type_mismatch", "on_length_exceeded", "on_required_empty"].forEach(function (id) {
                const node = document.getElementById(id);
                if (node && wv[id]) {
                    node.value = wv[id];
                }
            });
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
            await window.dmsTargetProfile.save(readCurrentStep());
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

    hydrateFromTarget();

    if (btnSave) {
        btnSave.addEventListener("click", function () {
            saveStep("");
        });
    }

    if (btnNext) {
        btnNext.addEventListener("click", function (e) {
            e.preventDefault();
            saveStep(btnNext.dataset.next || root.dataset.nextUrl || "");
        });
    }
})();
