/**
 * Vista previa en vivo del formulario de apariencia (record_expand_display).
 */
(function () {
    "use strict";

    var form = document.getElementById("expand-theme-form");
    if (!form) {
        return;
    }

    var preview = document.getElementById("theme-preview");
    var previewTable = document.getElementById("preview-table");
    var classStringEl = document.getElementById("preview-class-string");
    var pageLengthEl = document.getElementById("preview-page-length");

    var defaults = {
        header_bg: "#e8eef4",
        header_color: "#1a1d21",
        header_border: "#c5cdd8",
        cell_border: "#d4d9e0",
        stripe_bg: "#f7f9fb",
        hover_bg: "#e8eef4",
        page_length: "25",
        grid_cell_border: true,
        layout_compact: true,
        row_stripe: true,
        row_hover: true,
        column_order_highlight: true,
        cell_nowrap: true
    };

    var colorPairs = [
        ["header_bg", "header_bg_picker"],
        ["header_color", "header_color_picker"],
        ["header_border", "header_border_picker"],
        ["cell_border", "cell_border_picker"],
        ["stripe_bg", "stripe_bg_picker"],
        ["hover_bg", "hover_bg_picker"]
    ];

    function isHex(value) {
        return /^#[0-9A-Fa-f]{6}$/.test(value);
    }

    function syncPickerToText(name, pickerId) {
        var text = document.getElementById(name);
        var picker = document.getElementById(pickerId);
        if (!text || !picker) {
            return;
        }
        picker.addEventListener("input", function () {
            text.value = picker.value;
            updatePreview();
        });
        text.addEventListener("input", function () {
            if (isHex(text.value)) {
                picker.value = text.value;
            }
            updatePreview();
        });
    }

    function tableClassString() {
        var classes = ["dw-datatable", "display"];
        var map = [
            ["grid_cell_border", "cell-border"],
            ["layout_compact", "compact"],
            ["row_stripe", "stripe"],
            ["row_hover", "hover"],
            ["column_order_highlight", "order-column"],
            ["cell_nowrap", "nowrap"]
        ];
        map.forEach(function (entry) {
            var checkbox = document.getElementById(entry[0]);
            if (checkbox && checkbox.checked) {
                classes.push(entry[1]);
            }
        });
        return classes.join(" ");
    }

    function updatePreview() {
        if (!preview) {
            return;
        }
        colorPairs.forEach(function (pair) {
            var input = document.getElementById(pair[0]);
            if (input && isHex(input.value)) {
                var cssName = pair[0].replace(/_/g, "-");
                preview.style.setProperty("--theme-" + cssName, input.value);
            }
        });

        if (classStringEl) {
            classStringEl.textContent = tableClassString();
        }

        var pageLength = document.getElementById("page_length");
        if (pageLengthEl && pageLength) {
            pageLengthEl.textContent = pageLength.value || defaults.page_length;
        }

        if (previewTable) {
            previewTable.className = "theme-preview-table " + tableClassString();
            var stripes = previewTable.querySelectorAll("tbody tr.is-stripe");
            var stripeToggle = document.getElementById("row_stripe");
            stripes.forEach(function (row) {
                row.style.background = stripeToggle && stripeToggle.checked
                    ? getComputedStyle(preview).getPropertyValue("--theme-stripe-bg").trim()
                    : "";
            });
        }
    }

    colorPairs.forEach(function (pair) {
        syncPickerToText(pair[0], pair[1]);
    });

    ["grid_cell_border", "layout_compact", "row_stripe", "row_hover", "column_order_highlight", "cell_nowrap", "page_length"].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", updatePreview);
            el.addEventListener("change", updatePreview);
        }
    });

    var resetBtn = document.getElementById("btn-reset-defaults");
    if (resetBtn) {
        resetBtn.addEventListener("click", function () {
            Object.keys(defaults).forEach(function (key) {
                var el = document.getElementById(key);
                if (!el) {
                    return;
                }
                if (el.type === "checkbox") {
                    el.checked = defaults[key];
                } else {
                    el.value = defaults[key];
                    var picker = document.getElementById(key + "_picker");
                    if (picker && isHex(defaults[key])) {
                        picker.value = defaults[key];
                    }
                }
            });
            updatePreview();
        });
    }

    updatePreview();
})();
